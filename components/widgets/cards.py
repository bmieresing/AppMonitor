import urllib.parse
import streamlit as st
import pandas as pd
from connectors.mysql import cargar_estado_locales
from connectors.sheets import cargar_datos_regiones
from components.helpers.data_prep import _mapa_empleados, _cerrados_set, _litros, _pct
from components.widgets.tanque import _tanque, C_VERDE, C_VERDE_OSC


def _grid_choferes(
    df_rec: pd.DataFrame,
    df_locales: pd.DataFrame,
    data_comp: pd.DataFrame | None = None,
    tab_nombre: str = "",
    key_prefix: str = "",
):
    mapa = _mapa_empleados()

    if data_comp is not None and not data_comp.empty and "LitrosHoy" in data_comp.columns:
        litros_ch = data_comp.set_index("Chofer")["LitrosHoy"].to_dict()
        prom_ch   = data_comp.set_index("Chofer")["Prom"].to_dict()
        pct_ch    = {n: _pct(l, prom_ch.get(n, 0)) for n, l in litros_ch.items()}
    else:
        df_lit = _litros(df_rec).copy() if not df_rec.empty else pd.DataFrame()
        if not df_lit.empty and "Chofer" in df_lit.columns:
            if "NombreChofer" not in df_lit.columns:
                df_lit["NombreChofer"] = pd.to_numeric(df_lit["Chofer"], errors="coerce").map(mapa).fillna(df_lit["Chofer"].astype(str))
            litros_ch = df_lit.groupby("NombreChofer")["Litros"].sum().to_dict()
        else:
            litros_ch = {}
        pct_ch = {n: 0 for n in litros_ch}

    locales_ch: dict[str, dict] = {}
    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = pd.to_numeric(df_loc["Chofer"], errors="coerce").map(mapa).fillna(df_loc["Chofer"].astype(str))
        df_loc["EsAlta"] = (
            df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
            if "Prioridad" in df_loc.columns else False
        )
        for nombre, grp in df_loc.groupby("NombreChofer"):
            grp_alta = grp[grp["EsAlta"]]
            locales_ch[nombre] = {
                "total": (int((grp["Estado"] == "Realizado").sum()), len(grp)),
                "alta":  (int((grp_alta["Estado"] == "Realizado").sum()), len(grp_alta)),
            }

    cerrados = _cerrados_set(df_rec)

    choferes = sorted(
        set(list(litros_ch.keys()) + list(locales_ch.keys())),
        key=lambda n: pct_ch.get(n, 0), reverse=True,
    )
    if not choferes:
        return

    def _barra(pct_fill: int, pct_label: int, sub: str, mostrar_pct: bool = True) -> str:
        color = C_VERDE if pct_label >= 80 else C_ROJO
        if not mostrar_pct:
            color = "#1565c0"
        w = min(pct_fill, 100)
        pct_span = f'<span style="font-weight:700;color:{color}">{pct_label}%</span>' if mostrar_pct else ""
        return (
            f'<div style="margin-bottom:2px">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#666;margin-bottom:1px">'
            f'<span>{sub}</span>{pct_span}'
            f'</div>'
            f'<div style="height:4px;border-radius:2px;background:#e8e8e8;overflow:hidden">'
            f'<div style="height:100%;width:{w}%;background:{color};border-radius:2px"></div>'
            f'</div></div>'
        )

    cards = []
    for nombre in choferes:
        litros = litros_ch.get(nombre, 0)
        pct_lit = pct_ch.get(nombre, 0)
        barra_lit = _barra(min(pct_lit, 100), pct_lit, f"💧 {int(litros):,} L")

        barras_loc = ""
        if nombre in locales_ch:
            r_tot, t_tot = locales_ch[nombre]["total"]
            r_alt, t_alt = locales_ch[nombre]["alta"]
            barras_loc = _barra(_pct(r_tot, t_tot), _pct(r_tot, t_tot), f"📋 {r_tot}/{t_tot}")
            if t_alt > 0:
                p = _pct(r_alt, t_alt)
                barras_loc += _barra(p, p, f"⭐ {r_alt}/{t_alt}")

        cerrado = nombre in cerrados
        candado = (
            '<span style="font-size:12px;margin-left:3px;vertical-align:middle;flex-shrink:0;'
            'font-family:\'Apple Color Emoji\',\'Segoe UI Emoji\',\'Noto Color Emoji\',sans-serif">🔒</span>'
        ) if cerrado else ''
        bg = '#f0f4f0' if cerrado else '#f9fdf9'
        link = f'?nav_carrusel={urllib.parse.quote(nombre)}'
        cards.append(
            f'<div style="border:1px solid #c8e6c9;border-radius:5px;padding:5px 7px;'
            f'background:{bg};box-shadow:0 1px 3px rgba(0,0,0,0.04)">'
            f'<div style="display:flex;align-items:center;font-weight:700;font-size:12px;'
            f'color:{C_VERDE_OSC};margin-bottom:3px;overflow:hidden" title="{nombre}">'
            f'<a href="{link}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            f'text-decoration:none;color:{C_VERDE_OSC}">{nombre}</a>'
            f'{candado}</div>'
            f'{barra_lit}{barras_loc}</div>'
        )

    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:6px;padding:2px 0">'
        f'{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


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

    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = pd.to_numeric(df_loc["Chofer"], errors="coerce").map(mapa_nombre).fillna(df_loc["Chofer"].astype(str))
        df_loc["EsAlta"] = (
            df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
            if "Prioridad" in df_loc.columns else False
        )

    cerrados = _cerrados_set(df_rec)

    no_alc_ch: dict[str, int] = {}
    no_alc_alta_ch: dict[str, int] = {}
    if not df_rec.empty and "Razon" in df_rec.columns and "Chofer" in df_rec.columns:
        _cols_dd = ["Chofer", "idLocalSistema"] if "idLocalSistema" in df_rec.columns else ["Chofer"]
        _df_na = df_rec[df_rec["Razon"] == 11].drop_duplicates(subset=_cols_dd).copy()
        if not _df_na.empty:
            _df_na["NombreChofer"] = pd.to_numeric(_df_na["Chofer"], errors="coerce").map(mapa_nombre).fillna(_df_na["Chofer"].astype(str))
            no_alc_ch = _df_na.groupby("NombreChofer").size().to_dict()
            if not df_loc.empty and "ID_Local" in df_loc.columns and "idLocalSistema" in _df_na.columns:
                _alta_ids = set(df_loc[df_loc["EsAlta"]]["ID_Local"].astype(int).tolist())
                _df_na_alta = _df_na[_df_na["idLocalSistema"].dropna().astype(int).isin(_alta_ids)]
                no_alc_alta_ch = _df_na_alta.groupby("NombreChofer").size().to_dict()

    data_sorted = data_comp.sort_values("Pct", ascending=False).reset_index(drop=True)

    cards_html = []
    for nombre in data_sorted["Chofer"].tolist():
        fila = data_sorted[data_sorted["Chofer"] == nombre].iloc[0]
        litros_hoy = float(fila.get("LitrosHoy", 0))
        prom = float(fila.get("Prom", 0))
        pct_lit = _pct(litros_hoy, prom)

        pct_loc = pct_alta = no_alc_pct_loc = no_alc_pct_alta = 0
        sub_loc = sub_alta = "—"
        if not df_loc.empty and "NombreChofer" in df_loc.columns:
            grp = df_loc[df_loc["NombreChofer"] == nombre]
            if not grp.empty:
                t_tot = len(grp)
                r_tot = int((grp["Estado"] == "Realizado").sum())
                no_alc = no_alc_ch.get(nombre, 0)
                r_exitosos = max(0, r_tot - no_alc)
                pct_loc = _pct(r_exitosos, t_tot)
                no_alc_pct_loc = _pct(no_alc, t_tot)
                sub_loc = f"{r_exitosos}/{t_tot}"
                grp_alta = grp[grp["EsAlta"]]
                if not grp_alta.empty:
                    t_alt = len(grp_alta)
                    r_alt = int((grp_alta["Estado"] == "Realizado").sum())
                    no_alc_alt = no_alc_alta_ch.get(nombre, 0)
                    r_alt_exit = max(0, r_alt - no_alc_alt)
                    pct_alta = _pct(r_alt_exit, t_alt)
                    no_alc_pct_alta = _pct(no_alc_alt, t_alt)
                    sub_alta = f"{r_alt_exit}/{t_alt}"

        cerrado = nombre in cerrados
        candado = "🔒 " if cerrado else ""
        bg = "#f0f4f0" if cerrado else "#f9fdf9"
        sub_lit = f"{int(litros_hoy):,} / {int(prom):,} L"

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
                 title="{nombre}">{candado}<a href="?nav_carrusel={urllib.parse.quote(nombre)}" style="text-decoration:none;color:{C_VERDE_OSC}">{nombre}</a></div>
            {tanques}
        </div>""")

    for i in range(0, len(cards_html), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, card in enumerate(cards_html[i:i + cols_por_fila]):
            cols[j].markdown(card, unsafe_allow_html=True)


def _desempeno_centros(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame):
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

    local_stats = pd.DataFrame()
    if not df_locales.empty and "CentroAcopio" in df_locales.columns:
        local_stats = (
            df_locales.groupby("CentroAcopio")
            .agg(Total=("ID_Local", "count"),
                 Realizados=("Estado", lambda x: (x == "Realizado").sum()))
            .reset_index()
        )

    centros = sorted(set(list(prom_zona.keys()) + (local_stats["CentroAcopio"].tolist() if not local_stats.empty else [])))
    centros = [c for c in centros if c and str(c) != "nan"]
    if not centros:
        return

    cols_por_fila = max(3, -(-len(centros) // 2))
    for i in range(0, len(centros), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, centro in enumerate(centros[i:i + cols_por_fila]):
            litros = litros_zona.get(centro, 0)
            prom = prom_zona.get(centro, 0)

            fila_loc = local_stats[local_stats["CentroAcopio"] == centro] if not local_stats.empty else pd.DataFrame()
            realizados_loc = int(fila_loc["Realizados"].iloc[0]) if not fila_loc.empty else 0
            total_loc = int(fila_loc["Total"].iloc[0]) if not fila_loc.empty else 0

            tanque_litros = _tanque(_pct(litros, prom), "💧", "Litros", f"{int(litros):,} / {int(prom):,} L")
            tanque_locales = _tanque(_pct(realizados_loc, total_loc), "🏪", "Locales", f"{realizados_loc} / {total_loc}")

            cols[j].markdown(f"""
            <div style="border:1px solid #c8e6c9;border-radius:10px;padding:12px 12px 10px;
                        background:#f9fdf9;box-shadow:0 1px 6px rgba(0,0,0,0.05)">
                <div style="font-weight:700;font-size:12px;margin-bottom:10px;color:{C_VERDE_OSC};
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                            border-bottom:1px solid #e0f0e0;padding-bottom:6px"
                     title="{centro}">{centro}</div>
                <div style="display:flex;gap:10px">
                    {tanque_litros}
                    {tanque_locales}
                </div>
            </div>
            """, unsafe_allow_html=True)
