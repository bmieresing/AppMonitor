# Carrusel v2: espejo del Carrusel v1 usando solo componentes nativos de
# Streamlit (containers, columns, Plotly, st.metric, st.dataframe con barras).
# La lógica de datos es la misma de v1: helpers/carrusel_data.py.
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

from components.helpers.carrusel_data import datos_chofer, lista_choferes
from components.helpers.data_prep import _cerrados_set, hora_actualizacion
from connectors.estado_carga import falla_reciente, detalle_falla, forzar_ciclo
from components.tabs.tab_carrusel import _mini_kpis
from components.tabs.tab_v2 import _mini_metrica, _css_responsive
from components.widgets.tanque import C_VERDE_OSC
from config import INTERVALO_CARRUSEL_SEG

_NO_ALC = "No alcanzamos a pasar"
_NO_ALC_COLOR = "#e53935"
_REDS_OTROS = ["#c0392b", "#922b21", "#7b241c", "#641e16", "#4a0e0e"]
_CFG = {"displayModeBar": False}


def _donut_desglose(exitosas: int, pend_alta: int, pend_normal: int,
                    razon_counts: pd.DataFrame) -> tuple[go.Figure, str]:
    """Mismo desglose que el donut Altair de v1 (exitosas, razones de fallo,
    pendientes), renderizado con Plotly. Retorna (figura, leyenda HTML): la
    leyenda va FUERA del gráfico porque Plotly recalcula mal la posición de
    su leyenda al redimensionar la ventana en caliente (quedaba montada sobre
    la dona hasta el siguiente re-render completo) — el v1 usa leyenda HTML
    y por eso nunca se rompe."""
    razones = razon_counts["NombreRazon"].tolist() if not razon_counts.empty else []
    labels = ["Exitosas"] + razones + ["Pend. Alta", "Pend. Baja/Media"]
    values = (
        [exitosas]
        + [int(n) for n in (razon_counts["N"].tolist() if not razon_counts.empty else [])]
        + [pend_alta, pend_normal]
    )
    _oi = 0
    colores_razones = []
    for r in razones:
        if r == _NO_ALC:
            colores_razones.append(_NO_ALC_COLOR)
        else:
            colores_razones.append(_REDS_OTROS[_oi % len(_REDS_OTROS)])
            _oi += 1
    colors = ["#28a745"] + colores_razones + ["#555555", "#95a5a6"]

    visibles = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not visibles:
        visibles = [("Sin datos", 1, "#e0e0e0")]
    labels, values, colors = (list(x) for x in zip(*visibles))

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=colors,
        hole=0.55,
        sort=False,
        direction="clockwise",
        textinfo="value",
        textfont_size=11,
        hovertemplate="<b>%{label}</b><br>%{value} locales<br>%{percent:.0%}<extra></extra>",
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    leyenda = (
        '<div style="display:flex;flex-wrap:wrap;gap:4px 14px;justify-content:center;'
        'font-size:12px;color:#444;margin:2px 0 6px">'
        + "".join(
            f'<span style="white-space:nowrap"><span style="display:inline-block;'
            f'width:10px;height:10px;background:{c};border-radius:2px;'
            f'margin-right:5px"></span>{l}</span>'
            for l, c in zip(labels, colors)
        )
        + '</div>'
    )
    return fig, leyenda


def _tabla_top(lit_local: pd.DataFrame, titulo: str, ascendente: bool):
    st.markdown(f"**{titulo}**")
    # Chequear vacío ANTES de nlargest/nsmallest (truenan con dtype object)
    if lit_local.empty:
        st.caption("Sin datos")
        return
    top = lit_local.nsmallest(5, "Litros") if ascendente else lit_local.nlargest(5, "Litros")
    st.dataframe(
        top[["Local", "Litros"]],
        column_config={
            "Local": st.column_config.TextColumn("Local"),
            "Litros": st.column_config.ProgressColumn(
                "Litros", format="%d L",
                min_value=0, max_value=float(top["Litros"].max()),
            ),
        },
        hide_index=True,
        width='stretch',
    )


def _tabla_productos(prod: pd.DataFrame):
    st.markdown("**🧴 Por producto**")
    if prod.empty:
        st.caption("Sin datos")
        return
    st.dataframe(
        prod[["Producto", "Visitas", "Litros"]],
        column_config={
            "Producto": st.column_config.TextColumn("Producto"),
            "Visitas": st.column_config.NumberColumn("Visitas"),
            "Litros": st.column_config.ProgressColumn(
                "Litros", format="%d L",
                min_value=0, max_value=float(prod["Litros"].max()),
            ),
        },
        hide_index=True,
        width='stretch',
    )


@st.fragment
def mostrar_carrusel_v2(
    df_rec: pd.DataFrame,
    data_comp: pd.DataFrame | None = None,
    keys_ns: str = "carrusel2",
):
    """keys_ns: namespace de las keys de session_state/widgets — permite montar
    el mismo carrusel en más de una vista (v2, v3) con estado independiente."""
    ns = keys_ns
    # Incluye también a los choferes del sheet que aún no suben recolecciones
    choferes = lista_choferes(df_rec, data_comp)
    if not choferes:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    # CSS base v2: columnas con wrap + fix de hover de Plotly
    _css_responsive()

    n = len(choferes)

    for key, val in [(f"{ns}_idx", 0), (f"{ns}_tick_prev", 0)]:
        if key not in st.session_state:
            st.session_state[key] = val

    # Fecha de actualización + botón ↺ chico, arriba del selector de choferes
    ahora = hora_actualizacion()
    st.markdown(f"""
    <style>
        .st-key-{ns}_fecha button {{
            min-height: 24px !important;
            height: 24px !important;
            padding: 0 8px !important;
            font-size: 13px !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    # gap=None: el botón ↺ queda pegado a la fecha
    with st.container(horizontal=True, vertical_alignment="center",
                      gap=None, key=f"{ns}_fecha"):
        _falla = falla_reciente()
        _txt = f"Última actualización: {ahora.strftime('%d/%m/%Y %H:%M')}"
        if _falla:
            _txt += f" · :red[⚠ falla {_falla.strftime('%H:%M')}]"
        st.caption(_txt, help=detalle_falla() if _falla else None)
        if st.button("↺", key=f"{ns}_refresh",
                     help="Recarga todos los datos desde MySQL, PostgreSQL y Google Sheets"):
            forzar_ciclo()  # el próximo run ejecuta un ciclo completo
            # scope="app": el carrusel es un fragment; el ciclo corre en app.py
            st.rerun(scope="app")

    c_slicer, c_toggle = st.columns([8, 1])
    with c_toggle:
        auto = st.toggle("Auto", value=False, key=f"{ns}_auto")
    if auto:
        tick = st_autorefresh(interval=INTERVALO_CARRUSEL_SEG * 1000, key=f"{ns}_tick")
        if tick != st.session_state[f"{ns}_tick_prev"]:
            st.session_state[f"{ns}_idx"] = (st.session_state[f"{ns}_idx"] + 1) % n
            st.session_state[f"{ns}_tick_prev"] = tick

    idx = st.session_state[f"{ns}_idx"] % n

    # Candado en el selector para ver de un vistazo quién ya cerró ruta
    cerrados = _cerrados_set(df_rec)
    labels = [f"🔒 {c}" if c in cerrados else c for c in choferes]

    with c_slicer:
        selected = st.pills(
            "Chofer",
            options=labels,
            default=labels[idx],
            label_visibility="collapsed",
            key=f"{ns}_slicer",
        )

    if selected and selected in labels:
        new_idx = labels.index(selected)
        if new_idx != st.session_state[f"{ns}_idx"]:
            st.session_state[f"{ns}_idx"] = new_idx
            st.rerun()
        chofer = choferes[new_idx]
    else:
        chofer = choferes[idx]

    d = datos_chofer(df_rec, chofer, data_comp)

    # Banner del chofer: container nativo con key → la clase .st-key-* permite
    # darle el mismo degradado del banner v1 sin envolver HTML a mano
    st.markdown(f"""
    <style>
        .st-key-{ns}_banner {{
            background: linear-gradient(135deg, {C_VERDE_OSC}, #1a6b8a);
            border-radius: 14px;
            padding: 16px 24px;
        }}
        /* Textos de las mini métricas dentro del banner, legibles sobre fondo oscuro */
        .st-key-{ns}_banner p {{ color: rgba(255,255,255,0.85) !important; }}
    </style>
    """, unsafe_allow_html=True)
    with st.container(key=f"{ns}_banner"):
        c_nombre, c_metricas = st.columns([2, 3])
        with c_nombre:
            ruta_html = (
                f"<div style='font-size:12px;color:rgba(255,255,255,0.75);margin-top:6px'>"
                f"🗺️ {d['ruta']}</div>"
            ) if d["ruta"] else ""
            candado = "🔒 " if chofer in cerrados else ""
            st.markdown(
                f"<div style='font-size:12px;text-transform:uppercase;letter-spacing:2px;"
                f"color:rgba(255,255,255,0.65)'>Chofer</div>"
                f"<div style='font-size:34px;font-weight:900;color:white;"
                f"line-height:1.1'>{candado}{chofer}</div>"
                f"{ruta_html}",
                unsafe_allow_html=True,
            )
        with c_metricas:
            # grande=True: números protagonistas (20px), como los tanques del banner v1
            n_m = 2 + (1 if d["tiene_alta"] else 0) + (1 if d["emerg_total"] > 0 else 0)
            mcols = st.columns(n_m)
            _mini_metrica(mcols[0], "💧", "Litros", d["pct_lit"], d["sub_lit"],
                          grande=True)
            _mini_metrica(mcols[1], "🏪", "Locales", d["pct_loc"], d["sub_loc"],
                          no_alc_pct=d["no_alc_pct_loc"], grande=True)
            _col = 2
            if d["tiene_alta"]:
                _mini_metrica(mcols[_col], "⭐", "Alta", d["pct_alta"], d["sub_alta"],
                              no_alc_pct=d["no_alc_pct_alta"], grande=True)
                _col += 1
            if d["emerg_total"] > 0:
                _mini_metrica(mcols[_col], "🚨", "Emergencias", d["pct_emerg"],
                              d["sub_emerg"], grande=True)

    # Responsive como el Carrusel v1: cada bloque (dona, tablas top, productos)
    # tiene un ancho mínimo legible y salta de fila cuando no cabe, en vez de
    # comprimir las tablas hasta truncarlas. Aplica también a las columnas
    # anidadas (tops | productos dentro de la derecha), pisando el min-width:0
    # global de _css_responsive.
    st.markdown(f"""
    <style>
        .st-key-{ns}_cuerpo div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; }}
        .st-key-{ns}_cuerpo div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        .st-key-{ns}_cuerpo div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
            min-width: 280px !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    with st.container(key=f"{ns}_cuerpo"):
        col_iz, col_der = st.columns([2, 3])

        with col_iz:
            with st.container(border=True):
                fig_donut, leyenda_html = _donut_desglose(
                    d["exitosas"], d["pend_alta"], d["pend_normal"], d["razon_counts"],
                )
                st.plotly_chart(fig_donut, width='stretch', config=_CFG,
                                key=f"{ns}_donut")
                # Leyenda HTML (no de Plotly): inmune a los redimensionados
                st.markdown(leyenda_html, unsafe_allow_html=True)
            # Mismas 4 cajas de colores del Carrusel v1 (widget compartido)
            _mini_kpis(d["exitosas"], d["fallidas"], d["pend_alta"], d["pend_normal"])

        with col_der:
            c_tops, c_prod = st.columns([1, 1])
            with c_tops:
                with st.container(border=True):
                    _tabla_top(d["lit_local"], "🏆 Top 5 — Más litros", ascendente=False)
                with st.container(border=True):
                    _tabla_top(d["lit_local"], "⚠️ Top 5 — Menos litros", ascendente=True)
            with c_prod:
                with st.container(border=True):
                    _tabla_productos(d["productos"])
