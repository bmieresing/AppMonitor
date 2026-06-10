# Cálculo centralizado de los KPIs del dashboard. Los donuts CSS (v1),
# los donuts Plotly (v2) y el carrusel deben leer de acá, para que un
# mismo indicador nunca se calcule distinto según el tab.
import pandas as pd

from components.helpers.data_prep import _litros, _pct, _cerrados_set

# id de "No alcanzamos a pasar" en visits_visitfailurereason
RAZON_NO_ALC = 11


def exitosas_fallidas(df_rec: pd.DataFrame) -> tuple[int, int]:
    """Cuenta por local único: exitosa si la suma de litros del local > 0;
    fallida si tiene razón de fallo y no juntó litros. Mutuamente excluyentes,
    e inmune al orden de las filas por producto de VistaMonitor."""
    if df_rec.empty or "Litros" not in df_rec.columns:
        return 0, 0
    tiene_razon = (
        df_rec["Razon"].notna() if "Razon" in df_rec.columns
        else pd.Series(False, index=df_rec.index)
    )
    if "idLocalSistema" in df_rec.columns:
        litros_loc = df_rec.groupby("idLocalSistema")["Litros"].sum()
        razon_loc = tiene_razon.groupby(df_rec["idLocalSistema"]).any()
        exitosas = int((litros_loc > 0).sum())
        fallidas = int((razon_loc & (litros_loc <= 0)).sum())
    else:
        exitosas = int((df_rec["Litros"] > 0).sum())
        fallidas = int((tiene_razon & (df_rec["Litros"] <= 0)).sum())
    return exitosas, fallidas


def no_alcanzados(df_rec: pd.DataFrame, df_locales: pd.DataFrame) -> tuple[int, int]:
    """Locales únicos marcados "No alcanzamos a pasar": (total, de prioridad alta)."""
    no_alc_loc = no_alc_alta = 0
    if not df_rec.empty and "Razon" in df_rec.columns and "idLocalSistema" in df_rec.columns:
        df_na = df_rec[df_rec["Razon"] == RAZON_NO_ALC].drop_duplicates(subset="idLocalSistema")
        no_alc_loc = len(df_na)
        if not df_locales.empty and "Prioridad" in df_locales.columns and "ID_Local" in df_locales.columns:
            alta_ids = set(
                df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
                ["ID_Local"].astype(int)
            )
            no_alc_alta = int(df_na["idLocalSistema"].dropna().astype(int).isin(alta_ids).sum())
    return no_alc_loc, no_alc_alta


def calcular_kpis(
    df_rec: pd.DataFrame,
    df_locales: pd.DataFrame,
    data_comp: pd.DataFrame,
    prom_total: float | None = None,
) -> dict:
    """Los 5 KPIs globales del dashboard. prom_total permite sobreescribir el
    esperado (p. ej. Global = Santiago + Regiones); por defecto usa data_comp."""
    n_rutas = df_locales["Chofer"].nunique() if not df_locales.empty else 0
    cerradas = len(_cerrados_set(df_rec))

    no_alc_loc, no_alc_alta = no_alcanzados(df_rec, df_locales)
    exitosas, fallidas = exitosas_fallidas(df_rec)

    df_lit = _litros(df_rec)
    litros = df_lit["Litros"].sum() if not df_lit.empty else 0
    if prom_total is None:
        prom_total = (
            data_comp["Prom"].sum()
            if not data_comp.empty and "Prom" in data_comp.columns else 0
        )

    total_loc = len(df_locales)
    realizados = int((df_locales["Estado"] == "Realizado").sum()) if not df_locales.empty else 0
    exitosos_loc = max(0, realizados - no_alc_loc)

    total_alta = exitosos_alta = 0
    if not df_locales.empty and "Prioridad" in df_locales.columns:
        df_alta = df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
        total_alta = len(df_alta)
        real_alta = int((df_alta["Estado"] == "Realizado").sum())
        exitosos_alta = max(0, real_alta - no_alc_alta)

    return dict(
        litros=litros, esperado=prom_total, pct_lit=_pct(litros, prom_total),
        exitosos_loc=exitosos_loc, total_loc=total_loc,
        pct_loc=_pct(exitosos_loc, total_loc), no_alc_loc=no_alc_loc,
        exitosos_alta=exitosos_alta, total_alta=total_alta,
        pct_alta=_pct(exitosos_alta, total_alta), no_alc_alta=no_alc_alta,
        exitosas=exitosas, fallidas=fallidas,
        pct_exit=_pct(exitosas, exitosas + fallidas),
        cerradas=cerradas, n_rutas=n_rutas,
        pct_cerradas=_pct(cerradas, n_rutas),
    )
