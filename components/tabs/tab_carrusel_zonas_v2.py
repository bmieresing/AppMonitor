# Carrusel Zonas v2/v3: espejo del Carrusel Zonas v1 pero ciclando las vistas
# v2 (Global → Santiago → Regiones). Misma navegación: ◀/▶, puntos y
# auto-avance cada INTERVALO_ZONAS_SEG. Con keys_ns="czv3" + emoji_lado=True
# se monta la variante v3 (emoji a la izquierda de la dona) con estado propio.
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from config import INTERVALO_ZONAS_SEG


@st.fragment
def mostrar_carrusel_zonas_v2(
    df_rec: pd.DataFrame,
    df_rec_stgo: pd.DataFrame,
    df_rec_reg: pd.DataFrame,
    choferes_todos: set,
    choferes_stgo: set,
    choferes_reg: set,
    data_comp_todos: pd.DataFrame,
    data_comp_stgo: pd.DataFrame,
    data_comp_reg: pd.DataFrame,
    keys_ns: str = "czv2",
    emoji_lado: bool = False,
):
    from components.tabs.tab_v2 import mostrar_tab_v2

    ns = keys_ns
    kp = f"{ns}_"

    VISTAS = [
        ("Global",   lambda: mostrar_tab_v2(
            df_rec, choferes_filter=choferes_todos,
            data_comp=data_comp_todos, tab_nombre="Global",
            data_comp_centros=data_comp_stgo, key_prefix=kp,
            emoji_lado=emoji_lado,
        )),
        ("Santiago", lambda: mostrar_tab_v2(
            df_rec_stgo, choferes_filter=choferes_stgo,
            data_comp=data_comp_stgo, tab_nombre="Santiago",
            key_prefix=kp, emoji_lado=emoji_lado,
        )),
        ("Regiones", lambda: mostrar_tab_v2(
            df_rec_reg, choferes_filter=choferes_reg,
            data_comp=data_comp_reg, tab_nombre="Regiones",
            key_prefix=kp, emoji_lado=emoji_lado,
        )),
    ]
    n = len(VISTAS)

    for key, val in [(f"{ns}_idx", 0), (f"{ns}_tick_prev", 0), (f"{ns}_auto", False)]:
        if key not in st.session_state:
            st.session_state[key] = val

    idx = st.session_state[f"{ns}_idx"] % n

    VISTAS[idx][1]()

    c_prev, c_ind, c_next, c_auto = st.columns([1, 8, 1, 3])
    with c_prev:
        if st.button("◀", key=f"{ns}_prev", width='stretch'):
            st.session_state[f"{ns}_idx"] = (idx - 1) % n
            st.rerun()
    with c_ind:
        dots = "  ".join(
            f'<span style="color:#1a472a;font-size:18px">⬤</span>' if i == idx
            else f'<span style="color:#ccc;font-size:18px">⬤</span>'
            for i in range(n)
        )
        labels = "  ·  ".join(
            f'<strong>{v[0]}</strong>' if i == idx else f'<span style="color:#aaa">{v[0]}</span>'
            for i, v in enumerate(VISTAS)
        )
        st.markdown(
            f'<div style="text-align:center;padding:4px 0">{dots}<br>'
            f'<span style="font-size:12px">{labels}</span></div>',
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("▶", key=f"{ns}_next", width='stretch'):
            st.session_state[f"{ns}_idx"] = (idx + 1) % n
            st.rerun()
    with c_auto:
        auto = st.toggle("Auto-avanzar", key=f"{ns}_auto")
        if auto:
            tick = st_autorefresh(interval=INTERVALO_ZONAS_SEG * 1000, key=f"{ns}_tick")
            if tick != st.session_state[f"{ns}_tick_prev"]:
                st.session_state[f"{ns}_idx"] = (st.session_state[f"{ns}_idx"] + 1) % n
                st.session_state[f"{ns}_tick_prev"] = tick
