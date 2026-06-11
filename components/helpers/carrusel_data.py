# Lógica de datos del carrusel por chofer. Única fuente compartida por
# Carrusel v1 (HTML) y Carrusel v2 (componentes nativos): los tabs solo renderizan.
import pandas as pd

from connectors.mysql import cargar_estado_locales
from connectors.postgres import cargar_razones, cargar_empleados
from components.helpers.data_prep import _litros, _pct, _norm_key
from components.helpers.kpis import exitosas_fallidas, RAZON_NO_ALC


def lista_choferes(df_rec: pd.DataFrame, data_comp: pd.DataFrame | None = None) -> list[str]:
    """Choferes a mostrar en el carrusel: los que tienen recolecciones hoy
    UNIDOS a los de la comparativa (sheet) — así un chofer con match pero
    que aún no sube nada también aparece (en cero)."""
    ch = (
        set(df_rec["NombreChofer"].dropna())
        if not df_rec.empty and "NombreChofer" in df_rec.columns else set()
    )
    if data_comp is not None and not data_comp.empty and "Chofer" in data_comp.columns:
        ch |= set(data_comp["Chofer"].dropna())
    return sorted(ch)


def datos_chofer(df_rec: pd.DataFrame, chofer: str, data_comp: pd.DataFrame | None = None) -> dict:
    """Todas las métricas del carrusel para un chofer:
    tanques (litros/locales/alta con no-alc), donut de desglose, mini KPIs,
    litros por local (tops 5) y desglose por producto."""
    df_c = (
        df_rec[df_rec["NombreChofer"] == chofer].copy()
        if not df_rec.empty and "NombreChofer" in df_rec.columns else pd.DataFrame()
    )
    id_col = "idLocalSistema" if "idLocalSistema" in df_c.columns else None
    if id_col and "idProducto" in df_c.columns:
        df_c = df_c.drop_duplicates(subset=[id_col, "idProducto"])

    litros_tot = int(_litros(df_c)["Litros"].sum()) if not df_c.empty else 0
    exitosas, fallidas = exitosas_fallidas(df_c)

    df_locales_all = cargar_estado_locales()
    chofer_id = df_c["Chofer"].iloc[0] if not df_c.empty and "Chofer" in df_c.columns else None
    if chofer_id is None:
        # Chofer sin recolecciones hoy: resolver su ID por nombre normalizado
        # para igual mostrar sus locales pendientes
        emp = cargar_empleados()
        if not emp.empty:
            mapa_ids = dict(zip(_norm_key(emp["nombre"]), emp["id"]))
            chofer_id = mapa_ids.get(_norm_key(pd.Series([chofer])).iloc[0])
    if chofer_id is not None and not df_locales_all.empty and "Chofer" in df_locales_all.columns:
        df_loc_ch = df_locales_all[df_locales_all["Chofer"] == chofer_id]
        if df_loc_ch.empty:
            # Fallback por tipo: MySQL puede entregar el ID como texto y PG como int
            df_loc_ch = df_locales_all[df_locales_all["Chofer"].astype(str) == str(chofer_id)]
    else:
        df_loc_ch = pd.DataFrame()

    pendientes = df_loc_ch[df_loc_ch["Estado"] != "Realizado"] if not df_loc_ch.empty else pd.DataFrame()
    if not pendientes.empty and "Prioridad" in pendientes.columns:
        es_alta = pendientes["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
        pend_alta = int(es_alta.sum())
        pend_normal = len(pendientes) - pend_alta
    else:
        pend_alta = pend_normal = 0

    # Razones de fallo por local único (alimenta el donut de desglose)
    razones_df = cargar_razones()
    mapa_razones = razones_df.set_index("id")["name"] if not razones_df.empty else pd.Series(dtype=str)
    if not df_c.empty and "Razon" in df_c.columns and df_c["Razon"].notna().any():
        df_fall = df_c[df_c["Razon"].notna()].copy()
        if id_col:
            df_fall = df_fall.drop_duplicates(subset=id_col)
        df_fall["NombreRazon"] = df_fall["Razon"].map(mapa_razones).fillna("Desconocida")
        razon_counts = (
            df_fall.groupby("NombreRazon").size()
            .reset_index(name="N")
            .sort_values("N", ascending=False)
        )
    else:
        razon_counts = pd.DataFrame(columns=["NombreRazon", "N"])

    # Tanque Litros (vs promedio esperado de data_comp) + ruta del sheet
    pct_lit = 0
    sub_lit = f"{litros_tot:,} L"
    ruta = None
    if data_comp is not None and not data_comp.empty and "Chofer" in data_comp.columns:
        fila = data_comp[data_comp["Chofer"] == chofer]
        if not fila.empty:
            _lh = float(fila.iloc[0].get("LitrosHoy", litros_tot))
            _pr = float(fila.iloc[0].get("Prom", 0))
            pct_lit = int(_lh / _pr * 100) if _pr > 0 else 0
            sub_lit = f"{int(_lh):,} / {int(_pr):,} L"
            _ruta = fila.iloc[0].get("Ruta")
            ruta = str(_ruta).strip() if pd.notna(_ruta) and str(_ruta).strip() else None

    # Tanques Locales/Alta: misma lógica que las cards de choferes
    # (Estado == "Realizado" descontando "no alcanzamos a pasar")
    no_alc_df = pd.DataFrame()
    if not df_c.empty and "Razon" in df_c.columns and id_col:
        no_alc_df = df_c[df_c["Razon"] == RAZON_NO_ALC].drop_duplicates(subset=id_col)
    no_alc_loc = len(no_alc_df)

    pct_loc = pct_alta = no_alc_pct_loc = no_alc_pct_alta = 0
    sub_loc = sub_alta = "—"
    tiene_alta = False
    if not df_loc_ch.empty:
        t = len(df_loc_ch)
        r = int((df_loc_ch["Estado"] == "Realizado").sum())
        r_exit = max(0, r - no_alc_loc)
        pct_loc = _pct(r_exit, t)
        no_alc_pct_loc = _pct(no_alc_loc, t)
        sub_loc = f"{r_exit}/{t}"
        if "Prioridad" in df_loc_ch.columns:
            alta = df_loc_ch[df_loc_ch["Prioridad"].astype(str).str.upper().str.startswith("ALTA")]
            t_a = len(alta)
            if t_a > 0:
                r_a = int((alta["Estado"] == "Realizado").sum())
                no_alc_alta = 0
                if not no_alc_df.empty and "ID_Local" in alta.columns:
                    alta_ids = set(alta["ID_Local"].astype(int).tolist())
                    no_alc_alta = int(no_alc_df[id_col].dropna().astype(int).isin(alta_ids).sum())
                ra_exit = max(0, r_a - no_alc_alta)
                pct_alta = _pct(ra_exit, t_a)
                no_alc_pct_alta = _pct(no_alc_alta, t_a)
                sub_alta = f"{ra_exit}/{t_a}"
                tiene_alta = True

    # Litros por local (para los tops 5)
    base = (
        df_c[df_c["Litros"] > 0].copy()
        if not df_c.empty and "Litros" in df_c.columns else pd.DataFrame()
    )
    if not base.empty and id_col and "Local" in base.columns:
        lit_local = (
            base.groupby(id_col)
            .agg(Local=("Local", "first"), Litros=("Litros", "sum"))
            .reset_index(drop=True)
        )
    elif not base.empty and "Local" in base.columns:
        lit_local = base[["Local", "Litros"]]
    else:
        # Vacío tipado: con columns=[...] Litros queda dtype object y
        # nlargest/nsmallest lanzan TypeError
        lit_local = pd.DataFrame({"Local": pd.Series(dtype=str),
                                  "Litros": pd.Series(dtype=float)})

    # Desglose por producto
    if not df_c.empty and "Producto" in df_c.columns:
        productos = (
            df_c[df_c["Litros"] > 0]
            .groupby("Producto")
            .agg(Visitas=("Litros", "count"), Litros=("Litros", "sum"))
            .reset_index()
            .sort_values("Litros", ascending=False)
        )
    else:
        productos = pd.DataFrame(columns=["Producto", "Visitas", "Litros"])

    return dict(
        df_c=df_c, litros_tot=litros_tot,
        exitosas=exitosas, fallidas=fallidas,
        pend_alta=pend_alta, pend_normal=pend_normal,
        razon_counts=razon_counts,
        ruta=ruta,
        pct_lit=pct_lit, sub_lit=sub_lit,
        pct_loc=pct_loc, sub_loc=sub_loc, no_alc_pct_loc=no_alc_pct_loc,
        pct_alta=pct_alta, sub_alta=sub_alta, no_alc_pct_alta=no_alc_pct_alta,
        tiene_alta=tiene_alta,
        lit_local=lit_local, productos=productos,
    )
