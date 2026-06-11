import urllib.parse
import streamlit as st
import pandas as pd
from components.helpers.data_prep import (
    _mapa_empleados, _cerrados_set, _datos_centros, _pct, _norm_key, _norm_nombre,
)
from components.widgets.tanque import _tanque, C_VERDE_OSC


def _cards_choferes_tanque(
    df_rec: pd.DataFrame,
    df_locales: pd.DataFrame,
    data_comp: pd.DataFrame,
    key_prefix: str = "",
    cols_por_fila: int = 4,
):
    if data_comp.empty or "Chofer" not in data_comp.columns:
        st.info("Sin datos de choferes para hoy.")
        return

    mapa_nombre = _mapa_empleados()

    # Todos los cruces por nombre usan la clave normalizada (_norm_key): el
    # nombre del sheet puede diferir del de PostgreSQL en mayúsculas/tildes
    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = pd.to_numeric(df_loc["Chofer"], errors="coerce").map(mapa_nombre).fillna(df_loc["Chofer"].astype(str))
        df_loc["_key"] = _norm_key(df_loc["NombreChofer"].astype(str))
        df_loc["EsAlta"] = (
            df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
            if "Prioridad" in df_loc.columns else False
        )

    cerrados_norm = {_norm_nombre(c) for c in _cerrados_set(df_rec)}

    no_alc_ch: dict[str, int] = {}
    no_alc_alta_ch: dict[str, int] = {}
    if not df_rec.empty and "Razon" in df_rec.columns and "Chofer" in df_rec.columns:
        _cols_dd = ["Chofer", "idLocalSistema"] if "idLocalSistema" in df_rec.columns else ["Chofer"]
        _df_na = df_rec[df_rec["Razon"] == 11].drop_duplicates(subset=_cols_dd).copy()
        if not _df_na.empty:
            _df_na["NombreChofer"] = pd.to_numeric(_df_na["Chofer"], errors="coerce").map(mapa_nombre).fillna(_df_na["Chofer"].astype(str))
            _df_na["_key"] = _norm_key(_df_na["NombreChofer"].astype(str))
            no_alc_ch = _df_na.groupby("_key").size().to_dict()
            if not df_loc.empty and "ID_Local" in df_loc.columns and "idLocalSistema" in _df_na.columns:
                _alta_ids = set(df_loc[df_loc["EsAlta"]]["ID_Local"].astype(int).tolist())
                _df_na_alta = _df_na[_df_na["idLocalSistema"].dropna().astype(int).isin(_alta_ids)]
                no_alc_alta_ch = _df_na_alta.groupby("_key").size().to_dict()

    data_sorted = data_comp.sort_values("Pct", ascending=False).reset_index(drop=True)

    cards_html = []
    for _, fila in data_sorted.iterrows():
        nombre = fila["Chofer"]
        litros_hoy = float(fila.get("LitrosHoy", 0))
        prom = float(fila.get("Prom", 0))
        pct_lit = _pct(litros_hoy, prom)

        key = _norm_nombre(str(nombre))
        pct_loc = pct_alta = no_alc_pct_loc = no_alc_pct_alta = 0
        sub_loc = sub_alta = "—"
        if not df_loc.empty and "_key" in df_loc.columns:
            grp = df_loc[df_loc["_key"] == key]
            if not grp.empty:
                t_tot = len(grp)
                r_tot = int((grp["Estado"] == "Realizado").sum())
                no_alc = no_alc_ch.get(key, 0)
                r_exitosos = max(0, r_tot - no_alc)
                pct_loc = _pct(r_exitosos, t_tot)
                no_alc_pct_loc = _pct(no_alc, t_tot)
                sub_loc = f"{r_exitosos}/{t_tot}"
                grp_alta = grp[grp["EsAlta"]]
                if not grp_alta.empty:
                    t_alt = len(grp_alta)
                    r_alt = int((grp_alta["Estado"] == "Realizado").sum())
                    no_alc_alt = no_alc_alta_ch.get(key, 0)
                    r_alt_exit = max(0, r_alt - no_alc_alt)
                    pct_alta = _pct(r_alt_exit, t_alt)
                    no_alc_pct_alta = _pct(no_alc_alt, t_alt)
                    sub_alta = f"{r_alt_exit}/{t_alt}"

        cerrado = key in cerrados_norm
        candado = "🔒 " if cerrado else ""
        bg = "#f0f4f0" if cerrado else "#f9fdf9"
        sub_lit = f"{int(litros_hoy):,} / {int(prom):,} L"

        ruta = fila.get("Ruta")
        ruta = str(ruta).strip() if pd.notna(ruta) and str(ruta).strip() else ""
        # En la misma línea del nombre para no aumentar el alto de la card
        ruta_html = (
            f'<span style="font-weight:400;font-size:12px;color:#777;margin-left:5px">'
            f'🗺️ {ruta}</span>'
        ) if ruta else ""

        t_lit = _tanque(pct_lit, "💧", "Litros", sub_lit, compact=True)
        t_loc = _tanque(pct_loc, "🏪", "Locales", sub_loc, compact=True, no_alc_pct=no_alc_pct_loc)
        t_alt = _tanque(pct_alta, "⭐", "Alta", sub_alta, compact=True, no_alc_pct=no_alc_pct_alta) if sub_alta != "—" else ""
        tanques = f'<div style="display:flex;gap:5px">{t_lit}{t_loc}{t_alt}</div>'

        cards_html.append(f"""
        <div style="border:1px solid #c8e6c9;border-radius:7px;padding:5px 6px 4px;
                    background:{bg};box-shadow:0 1px 4px rgba(0,0,0,0.04);margin:2px">
            <div style="font-weight:700;font-size:14px;color:{C_VERDE_OSC};margin-bottom:4px;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                        border-bottom:1px solid #e0f0e0;padding-bottom:3px"
                 title="{nombre} — {ruta}">{candado}<a href="?nav_carrusel={urllib.parse.quote(nombre)}" style="text-decoration:none;color:{C_VERDE_OSC}">{nombre}</a>{ruta_html}</div>
            {tanques}
        </div>""")

    for i in range(0, len(cards_html), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, card in enumerate(cards_html[i:i + cols_por_fila]):
            cols[j].markdown(card, unsafe_allow_html=True)


def _desempeno_centros(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame):
    centros = _datos_centros(df_rec, data_comp, df_locales)
    if not centros:
        return

    cols_por_fila = max(3, -(-len(centros) // 2))
    for i in range(0, len(centros), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, c in enumerate(centros[i:i + cols_por_fila]):
            tanque_litros = _tanque(_pct(c["litros"], c["prom"]), "💧", "Litros",
                                    f"{int(c['litros']):,} / {int(c['prom']):,} L")
            tanque_locales = _tanque(_pct(c["realizados"], c["total"]), "🏪", "Locales",
                                     f"{c['realizados']} / {c['total']}")

            cols[j].markdown(f"""
            <div style="border:1px solid #c8e6c9;border-radius:10px;padding:12px 12px 10px;
                        background:#f9fdf9;box-shadow:0 1px 6px rgba(0,0,0,0.05)">
                <div style="font-weight:700;font-size:12px;margin-bottom:10px;color:{C_VERDE_OSC};
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                            border-bottom:1px solid #e0f0e0;padding-bottom:6px"
                     title="{c['centro']}">{c['centro']}</div>
                <div style="display:flex;gap:10px">
                    {tanque_litros}
                    {tanque_locales}
                </div>
            </div>
            """, unsafe_allow_html=True)
