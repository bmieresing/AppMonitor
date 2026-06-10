import pandas as pd
from connectors.mysql import cargar_usuarios_vehiculos
from connectors.postgres import cargar_empleados, cargar_vehiculos

_EXCLUIR_LITROS = {"Latas", "Desengrasante"}


def _litros(df: pd.DataFrame) -> pd.DataFrame:
    """df_rec filtrado: excluye productos que no cuentan como litros de aceite."""
    if "Producto" not in df.columns or df.empty:
        return df
    return df[~df["Producto"].isin(_EXCLUIR_LITROS)]


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


def _preparar_datos(df_sheets: pd.DataFrame, df_mysql: pd.DataFrame) -> pd.DataFrame | None:
    col_prom = next((c for c in df_sheets.columns if "PROM" in c.upper()), None)
    col_patente = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
    if not col_prom or not col_patente:
        return None

    prom_df = df_sheets[[col_patente, col_prom]].copy()
    prom_df["Prom"] = pd.to_numeric(
        prom_df[col_prom].astype(str).str.replace(".", "").str.replace(",", "."),
        errors="coerce",
    )
    prom_df = prom_df[[col_patente, "Prom"]].rename(columns={col_patente: "Patente"})
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

    df_mysql_lit = (
        df_mysql[~df_mysql["Producto"].isin(_EXCLUIR_LITROS)]
        if "Producto" in df_mysql.columns else df_mysql
    )
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


def _preparar_datos_regiones(df_reg: pd.DataFrame, df_rec: pd.DataFrame) -> pd.DataFrame:
    """data_comp para Regiones: une nombre chofer del sheet con litros reales del día."""
    col_chofer = next((c for c in df_reg.columns if "CHOFER" in c.upper()), None)
    col_prom = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
    if not col_chofer or df_reg.empty:
        return pd.DataFrame()

    prom_s = df_reg[[col_chofer]].copy()
    prom_s.columns = ["Chofer"]
    prom_s["Prom"] = df_reg[col_prom].fillna(0) if col_prom else 0.0
    prom_s = prom_s[prom_s["Chofer"].notna()].copy()
    prom_s["_key"] = prom_s["Chofer"].str.strip().str.lower()

    if not df_rec.empty and "NombreChofer" in df_rec.columns:
        lit_s = (
            _litros(df_rec)
            .groupby("NombreChofer")["Litros"]
            .sum()
            .reset_index()
            .rename(columns={"NombreChofer": "Chofer_rec", "Litros": "LitrosHoy"})
        )
        lit_s["_key"] = lit_s["Chofer_rec"].str.strip().str.lower()
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
