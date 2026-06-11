import unicodedata

import pandas as pd
from connectors.mysql import cargar_usuarios_vehiculos
from connectors.postgres import cargar_empleados, cargar_vehiculos
from connectors.sheets import cargar_datos_regiones
from config import EXCLUIR_LITROS


def _litros(df: pd.DataFrame) -> pd.DataFrame:
    """df_rec filtrado: excluye productos que no cuentan como litros de aceite."""
    if "Producto" not in df.columns or df.empty:
        return df
    return df[~df["Producto"].isin(EXCLUIR_LITROS)]


def _norm_key(s: pd.Series) -> pd.Series:
    """Clave de join por nombre: minúsculas, sin tildes, espacios colapsados.
    El sheet y PostgreSQL no siempre escriben el nombre exactamente igual."""
    return (
        s.astype(str).str.strip().str.lower()
        .str.replace(r"\s+", " ", regex=True)
        .map(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode())
    )


def _norm_nombre(s) -> str:
    """Versión escalar de _norm_key — clave de match para un solo nombre."""
    return _norm_key(pd.Series([str(s)])).iloc[0]


def _pct(r, t) -> int:
    return int(r / t * 100) if t > 0 else 0


def _mapa_empleados(str_idx: bool = False) -> pd.Series:
    """Devuelve Series id → nombre. str_idx=True convierte el índice a str (evita mismatch MySQL/PG)."""
    emp = cargar_empleados()
    if emp.empty:
        return pd.Series(dtype=str)
    key = emp["id"].astype(str) if str_idx else emp["id"]
    return emp.set_index(key)["nombre"]


def _cerrados_set(df_rec: pd.DataFrame) -> set:
    """Conjunto de NombreChofer que ya tienen FechaObservacion (ruta cerrada en app)."""
    if df_rec.empty or "FechaObservacion" not in df_rec.columns or "NombreChofer" not in df_rec.columns:
        return set()
    return set(
        df_rec.groupby("NombreChofer")["FechaObservacion"]
        .apply(lambda x: x.notna().any())
        .pipe(lambda s: s[s].index)
    )


def _col_ruta(df: pd.DataFrame) -> str | None:
    """Columna RUTA del sheet, excluyendo "PROM RUTA"."""
    return next(
        (c for c in df.columns if "RUTA" in c.upper() and "PROM" not in c.upper()),
        None,
    )


def _preparar_datos(df_sheets: pd.DataFrame, df_mysql: pd.DataFrame) -> pd.DataFrame | None:
    col_prom = next((c for c in df_sheets.columns if "PROM" in c.upper()), None)
    col_patente = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
    if not col_prom or not col_patente:
        return None
    col_ruta = _col_ruta(df_sheets)

    cols = [col_patente, col_prom] + ([col_ruta] if col_ruta else [])
    prom_df = df_sheets[cols].copy()
    prom_df["Prom"] = pd.to_numeric(
        prom_df[col_prom].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    keep = [col_patente, "Prom"] + ([col_ruta] if col_ruta else [])
    renombres = {col_patente: "Patente"}
    if col_ruta:
        renombres[col_ruta] = "Ruta"
    prom_df = prom_df[keep].rename(columns=renombres)
    prom_df = prom_df[prom_df["Prom"] > 0]

    usuarios = cargar_usuarios_vehiculos()
    vehiculos = cargar_vehiculos()
    empleados = cargar_empleados()
    chofer_por_patente = pd.DataFrame()
    if not usuarios.empty and not vehiculos.empty and not empleados.empty:
        mapa_placa = vehiculos.set_index("id")["plate"]
        mapa_nombre = empleados.set_index("id")["nombre"]
        usuarios = usuarios.copy()
        usuarios["Patente"] = usuarios["Vehiculo"].map(mapa_placa)
        usuarios["NombreChofer"] = usuarios["Chofer"].map(mapa_nombre)
        chofer_por_patente = (
            usuarios[["Patente", "NombreChofer"]]
            .dropna()
            .drop_duplicates("Patente")
        )

    df_mysql_lit = _litros(df_mysql)
    litros_por_patente = (
        df_mysql_lit[df_mysql_lit["Litros"] > 0]
        .groupby("Patente_Real")["Litros"]
        .sum()
        .reset_index()
        .rename(columns={"Patente_Real": "Patente", "Litros": "LitrosHoy"})
    ) if not df_mysql_lit.empty and "Patente_Real" in df_mysql_lit.columns else pd.DataFrame()

    data = prom_df.copy()
    if not chofer_por_patente.empty:
        data = data.merge(chofer_por_patente, on="Patente", how="left")
    else:
        data["NombreChofer"] = None
    if not litros_por_patente.empty:
        data = data.merge(litros_por_patente, on="Patente", how="left")
    else:
        data["LitrosHoy"] = 0

    data["LitrosHoy"] = data["LitrosHoy"].fillna(0)
    data["Chofer"] = data["NombreChofer"].fillna(data["Patente"])
    data["Pct"] = (data["LitrosHoy"] / data["Prom"] * 100).round(1)
    data["SobreMeta"] = data["LitrosHoy"] >= data["Prom"]
    return data.sort_values("Pct", ascending=False)


def _datos_centros(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame) -> list[dict]:
    """Métricas por centro de acopio: litros vs prom y locales realizados/total.
    Regiones: prom por Zona desde el sheet. Santiago: litros/prom desde data_comp
    (debe ser la comparativa de Santiago, no la global). Lógica compartida entre
    las cards HTML (v1) y las nativas (v2)."""
    df_rec = _litros(df_rec)

    df_reg = cargar_datos_regiones()
    prom_zona: dict = {}
    if not df_reg.empty and "Zona" in df_reg.columns:
        col_prom = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
        if col_prom:
            for zona, grp in df_reg[df_reg["Zona"].notna()].groupby("Zona"):
                prom_zona[zona] = grp[col_prom].sum()

    litros_zona: dict = {}
    if not df_rec.empty and not df_locales.empty and "CentroAcopio" in df_locales.columns and "Chofer" in df_locales.columns:
        chofer_centro = df_locales.drop_duplicates("Chofer").set_index("Chofer")["CentroAcopio"]
        df_tmp = df_rec.copy()
        df_tmp["CentroAcopio"] = df_tmp["Chofer"].map(chofer_centro)
        litros_zona = df_tmp.groupby("CentroAcopio")["Litros"].sum().to_dict()

    if not data_comp.empty and "LitrosHoy" in data_comp.columns:
        stgo_litros = data_comp["LitrosHoy"].sum()
        stgo_prom = data_comp["Prom"].sum() if "Prom" in data_comp.columns else 0
        stgo_centros = set()
        if not df_locales.empty and "CentroAcopio" in df_locales.columns:
            stgo_centros = {c for c in df_locales["CentroAcopio"].dropna().unique()
                            if "santiago" in str(c).lower()}
        for c in stgo_centros | {k for k in prom_zona if "santiago" in str(k).lower()}:
            litros_zona[c] = stgo_litros
            if stgo_prom > 0:
                prom_zona[c] = stgo_prom

    local_stats: dict = {}
    if not df_locales.empty and "CentroAcopio" in df_locales.columns:
        for centro, grp in df_locales.groupby("CentroAcopio"):
            local_stats[centro] = (int((grp["Estado"] == "Realizado").sum()), len(grp))

    centros = sorted(set(list(prom_zona) + list(local_stats)))
    centros = [c for c in centros if c and str(c) != "nan"]
    return [
        dict(
            centro=c,
            litros=litros_zona.get(c, 0),
            prom=prom_zona.get(c, 0),
            realizados=local_stats.get(c, (0, 0))[0],
            total=local_stats.get(c, (0, 0))[1],
        )
        for c in centros
    ]


def _preparar_datos_regiones(df_reg: pd.DataFrame, df_rec: pd.DataFrame) -> pd.DataFrame:
    """data_comp para Regiones: une nombre chofer del sheet con litros reales del día."""
    col_chofer = next((c for c in df_reg.columns if "CHOFER" in c.upper()), None)
    col_prom = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
    if not col_chofer or df_reg.empty:
        return pd.DataFrame()

    prom_s = df_reg[[col_chofer]].copy()
    prom_s.columns = ["Chofer"]
    prom_s["Prom"] = df_reg[col_prom].fillna(0) if col_prom else 0.0
    col_ruta = _col_ruta(df_reg)
    if col_ruta:
        prom_s["Ruta"] = df_reg[col_ruta]
    if "_FilaSheet" in df_reg.columns:
        prom_s["_FilaSheet"] = df_reg["_FilaSheet"]
    prom_s = prom_s[prom_s["Chofer"].notna()].copy()
    prom_s["_key"] = _norm_key(prom_s["Chofer"])

    if not df_rec.empty and "NombreChofer" in df_rec.columns:
        lit_s = (
            _litros(df_rec)
            .groupby("NombreChofer")["Litros"]
            .sum()
            .reset_index()
            .rename(columns={"NombreChofer": "Chofer_rec", "Litros": "LitrosHoy"})
        )
        lit_s["_key"] = _norm_key(lit_s["Chofer_rec"])
        result = prom_s.merge(lit_s[["_key", "LitrosHoy"]], on="_key", how="outer")
        name_by_key = lit_s.set_index("_key")["Chofer_rec"].to_dict()
        mask = result["Chofer"].isna()
        result.loc[mask, "Chofer"] = result.loc[mask, "_key"].map(name_by_key)
    else:
        result = prom_s.copy()
        result["LitrosHoy"] = 0.0

    result = result.drop(columns=["_key"]).copy()
    result["LitrosHoy"] = result["LitrosHoy"].fillna(0)
    result["Prom"] = result["Prom"].fillna(0)
    result["Pct"] = (result["LitrosHoy"] / result["Prom"] * 100).where(result["Prom"] > 0, 0).round(1)
    return result.sort_values("LitrosHoy", ascending=False).reset_index(drop=True)
