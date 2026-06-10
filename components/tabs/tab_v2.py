import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

from connectors.mysql import cargar_estado_locales
from components.helpers.data_prep import _pct, _mapa_empleados, _cerrados_set
from components.helpers.kpis import calcular_kpis
from config import UMBRAL_VERDE, UMBRAL_AMARILLO

TZ = ZoneInfo("America/Santiago")


def _color_pct(pct: int) -> str:
    return "#2d7a2d" if pct >= UMBRAL_VERDE else "#c0392b" if pct < UMBRAL_AMARILLO else "#e67e22"


def _metricas_choferes(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame) -> list[dict]:
    mapa    = _mapa_empleados()
    cerrados = _cerrados_set(df_rec)

    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = pd.to_numeric(df_loc["Chofer"], errors="coerce").map(mapa).fillna(df_loc["Chofer"].astype(str))
        df_loc["EsAlta"] = (
            df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
            if "Prioridad" in df_loc.columns else False
        )

    no_alc_ch: dict[str, int] = {}
    no_alc_alta_ch: dict[str, int] = {}
    if not df_rec.empty and "Razon" in df_rec.columns and "Chofer" in df_rec.columns:
        cols_dd = ["Chofer", "idLocalSistema"] if "idLocalSistema" in df_rec.columns else ["Chofer"]
        df_na = df_rec[df_rec["Razon"] == 11].drop_duplicates(subset=cols_dd).copy()
        if not df_na.empty:
            df_na["NombreChofer"] = pd.to_numeric(df_na["Chofer"], errors="coerce").map(mapa).fillna(df_na["Chofer"].astype(str))
            no_alc_ch = df_na.groupby("NombreChofer").size().to_dict()
            if not df_loc.empty and "ID_Local" in df_loc.columns and "idLocalSistema" in df_na.columns:
                alta_ids = set(df_loc[df_loc["EsAlta"]]["ID_Local"].astype(int))
                df_na_alta = df_na[df_na["idLocalSistema"].dropna().astype(int).isin(alta_ids)]
                no_alc_alta_ch = df_na_alta.groupby("NombreChofer").size().to_dict()

    rows = []
    for _, fila in data_comp.sort_values("Pct", ascending=False).iterrows():
        nombre     = fila["Chofer"]
        litros_hoy = float(fila.get("LitrosHoy", 0))
        prom       = float(fila.get("Prom", 0))
        pct_lit    = _pct(litros_hoy, prom)

        pct_loc = pct_alta = 0
        sub_loc = sub_alta = None

        if not df_loc.empty and "NombreChofer" in df_loc.columns:
            grp = df_loc[df_loc["NombreChofer"] == nombre]
            if not grp.empty:
                t = len(grp)
                r = int((grp["Estado"] == "Realizado").sum())
                na = no_alc_ch.get(nombre, 0)
                r_exit = max(0, r - na)
                pct_loc = _pct(r_exit, t)
                sub_loc = f"{r_exit}/{t}"

                grp_alta = grp[grp["EsAlta"]]
                if not grp_alta.empty:
                    t_a = len(grp_alta)
                    r_a = int((grp_alta["Estado"] == "Realizado").sum())
                    na_a = no_alc_alta_ch.get(nombre, 0)
                    r_a_exit = max(0, r_a - na_a)
                    pct_alta = _pct(r_a_exit, t_a)
                    sub_alta = f"{r_a_exit}/{t_a}"

        rows.append(dict(
            nombre=nombre,
            cerrado=nombre in cerrados,
            litros_hoy=litros_hoy, prom=prom, pct_lit=pct_lit,
            pct_loc=pct_loc, sub_loc=sub_loc,
            pct_alta=pct_alta, sub_alta=sub_alta,
        ))
    return rows


def _donut_fig(
    pct: int,
    color_fill: str,
    color_bg: str = "#e0e0e0",
    segmento_alerta: int = 0,
    color_alerta: str = "#e53935",
) -> go.Figure:
    """Solo el anillo visual. El texto va con componentes nativos de Streamlit."""
    pct_clamp    = min(pct, 100)
    pct_alerta   = min(segmento_alerta, max(0, 100 - pct_clamp))
    pct_restante = 100 - pct_clamp - pct_alerta

    fig = go.Figure(go.Pie(
        labels=["Realizado", "No alc.", "Restante"],
        values=[pct_clamp, pct_alerta, pct_restante],
        marker_colors=[color_fill, color_alerta, color_bg],
        hole=0.72,
        sort=False,
        direction="clockwise",
        textinfo="none",
        hovertemplate="%{label}: %{value}%<extra></extra>",
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(t=0, b=0, l=0, r=0),
        height=130,
        annotations=[
            dict(text=f"<b>{pct}%</b>", x=0.5, y=0.5,
                 font_size=22, showarrow=False, font_color="#1a472a"),
        ],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _mini_metrica(col, emoji: str, label: str, pct: int, sub: str | None):
    color = _color_pct(pct)
    fill  = ("rgba(45,122,45,0.22)" if pct >= UMBRAL_VERDE
             else "rgba(192,57,43,0.22)" if pct < UMBRAL_AMARILLO
             else "rgba(230,126,34,0.22)")
    h     = min(pct, 100)
    with col:
        st.markdown(
            f'<div style="position:relative;height:52px;border:1px solid {color};'
            f'border-radius:4px;overflow:hidden;background:#fafafa">'
            f'  <div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;background:{fill}"></div>'
            f'  <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">'
            f'    <span style="font-size:18px;font-weight:900;color:{color}">{pct}%</span>'
            f'  </div>'
            f'</div>'
            f'<p style="font-size:0.65rem;color:#888;margin:4px 0 0;text-align:center">{emoji} {label}</p>'
            f'<p style="font-size:0.65rem;color:#999;margin:1px 0 0;text-align:center">{sub or "—"}</p>',
            unsafe_allow_html=True,
        )


def _card_chofer(ch: dict):
    with st.container(border=True):
        prefijo = "🔒 " if ch["cerrado"] else ""
        st.markdown(f"**{prefijo}{ch['nombre']}**")

        has_alta = bool(ch["sub_alta"])
        cols = st.columns(3 if has_alta else 2)

        _mini_metrica(cols[0], "💧", "Litros", ch["pct_lit"],
                      f"{int(ch['litros_hoy']):,} / {int(ch['prom']):,} L")
        _mini_metrica(cols[1], "🏪", "Locales", ch["pct_loc"], ch["sub_loc"])
        if has_alta:
            _mini_metrica(cols[2], "⭐", "Alta", ch["pct_alta"], ch["sub_alta"])


def mostrar_tab_v2(
    df_rec: pd.DataFrame,
    choferes_filter: set,
    data_comp: pd.DataFrame,
    tab_nombre: str = "Santiago",
):
    df_locales = cargar_estado_locales()
    if not df_locales.empty:
        df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]

    col_titulo, col_btn = st.columns([10, 1])
    with col_titulo:
        ahora = datetime.now(TZ)
        st.subheader(f"Dashboard Operacional – Recolección de Aceite | {tab_nombre}")
        st.caption(f"Última actualización: {ahora.strftime('%d/%m/%Y %H:%M')}  ●  EN VIVO")
    with col_btn:
        if st.button("↺ Actualizar", key=f"v2_refresh_{tab_nombre}", width='stretch'):
            st.cache_data.clear()
            st.rerun()

    k = calcular_kpis(df_rec, df_locales, data_comp)
    _cfg = {"displayModeBar": False}

    c1, c2, c3, c4, c5 = st.columns(5)

    def _kpi_col(col, emoji, label, valor, pct, color_fill, key,
                 color_bg="#e0e0e0", segmento_alerta=0, nota="", leyenda=None):
        with col:
            with st.container(border=True):
                col_emoji, col_donut = st.columns([2, 3])
                with col_emoji:
                    st.markdown(f'<p style="font-size:72px;line-height:1;margin-top:20px">{emoji}</p>',
                                unsafe_allow_html=True)
                with col_donut:
                    st.plotly_chart(
                        _donut_fig(pct, color_fill, color_bg=color_bg,
                                   segmento_alerta=segmento_alerta),
                        width='stretch', config=_cfg, key=key,
                    )
                dots = " &nbsp; ".join(
                    f'<span style="color:{c}">●</span> {l}'
                    for c, l in (leyenda or [])
                )
                st.markdown(
                    f'<p style="font-size:0.72rem;color:#999;text-transform:uppercase;'
                    f'letter-spacing:0.07em;margin:0">{label}</p>'
                    f'<p style="font-size:1.4rem;font-weight:700;color:#1a472a;margin:2px 0 0">{valor}</p>'
                    + (f'<p style="font-size:0.72rem;color:#888;margin:4px 0 0">{dots}</p>' if dots else ""),
                    unsafe_allow_html=True,
                )
                if nota:
                    st.caption(nota)

    _kpi_col(c1, "💧", "Litros vs Esperado",
             f"{k['litros']:,.0f} / {k['esperado']:,.0f} L",
             k["pct_lit"], "#2d7a2d", key=f"v2_donut_lit_{tab_nombre}",
             leyenda=[("#2d7a2d", "Recolectado"), ("#e0e0e0", "Restante")])

    _kpi_col(c2, "🏪", "Locales Realizados",
             f"{k['exitosos_loc']:,} / {k['total_loc']:,}",
             k["pct_loc"], "#2d7a2d", key=f"v2_donut_loc_{tab_nombre}",
             segmento_alerta=k["no_alc_loc"] * 100 // max(k["total_loc"], 1),
             nota=f"{k['no_alc_loc']} no alc." if k["no_alc_loc"] else "",
             leyenda=[("#2d7a2d", "Realizados"), ("#e53935", "No alc."), ("#e0e0e0", "Pendientes")])

    _kpi_col(c3, "⭐", "Prioridad Alta",
             f"{k['exitosos_alta']:,} / {k['total_alta']:,}",
             k["pct_alta"], "#2d7a2d", key=f"v2_donut_alta_{tab_nombre}",
             segmento_alerta=k["no_alc_alta"] * 100 // max(k["total_alta"], 1),
             nota=f"{k['no_alc_alta']} no alc." if k["no_alc_alta"] else "",
             leyenda=[("#2d7a2d", "Realizados"), ("#e53935", "No alc."), ("#e0e0e0", "Pendientes")])

    _kpi_col(c4, "✅", "Recolecciones",
             f"{k['exitosas']:,} exit. / {k['fallidas']:,} fall.",
             k["pct_exit"], "#28a745", key=f"v2_donut_rec_{tab_nombre}",
             color_bg="#dc3545",
             leyenda=[("#28a745", "Exitosas"), ("#dc3545", "Fallidas")])

    _kpi_col(c5, "🚦", "Rutas Cerradas",
             f"{k['cerradas']:,} / {k['n_rutas']:,}",
             k["pct_cerradas"], "#1a6b8a", key=f"v2_donut_rut_{tab_nombre}",
             leyenda=[("#1a6b8a", "Cerradas"), ("#e0e0e0", "Abiertas")])

    st.divider()

    if data_comp.empty or "Chofer" not in data_comp.columns:
        st.info("Sin datos de choferes para hoy.")
        return

    choferes = _metricas_choferes(df_rec, df_locales, data_comp)
    COLS = 6
    for i in range(0, len(choferes), COLS):
        cols = st.columns(COLS)
        for j, ch in enumerate(choferes[i : i + COLS]):
            with cols[j]:
                _card_chofer(ch)
