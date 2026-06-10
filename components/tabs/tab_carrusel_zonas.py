import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from components.helpers.data_prep import _preparar_datos_regiones

INTERVALO_ZONAS_SEG = 20


@st.fragment
def mostrar_carrusel_zonas(
    df_sheets: pd.DataFrame,
    df_rec: pd.DataFrame,
    df_rec_stgo: pd.DataFrame,
    df_rec_reg: pd.DataFrame,
    df_regiones: pd.DataFrame,
    choferes_todos: set,
    choferes_stgo: set,
    choferes_reg: set,
):
    from components.tabs.tab_global import mostrar_dashboard
    from components.tabs.tab_zonas import mostrar_cards_choferes

    _data_comp_reg = _preparar_datos_regiones(df_regiones, df_rec_reg)

    VISTAS = [
        ("Global",    lambda: mostrar_dashboard(
            df_sheets, df_rec, choferes_filter=choferes_todos,
            key_prefix="cz_global_", tab_nombre="Global",
        )),
        ("Santiago",  lambda: mostrar_cards_choferes(
            df_sheets, df_rec_stgo, choferes_filter=choferes_stgo,
            key_prefix="cz_stgo_cards_", tab_nombre="Santiago",
        )),
        ("Regiones",  lambda: mostrar_cards_choferes(
            df_regiones, df_rec_reg, choferes_filter=choferes_reg,
            key_prefix="cz_reg_cards_", tab_nombre="Regiones",
            data_comp_override=_data_comp_reg,
        )),
    ]
    n = len(VISTAS)

    for key, val in [("cz_idx", 0), ("cz_tick_prev", 0), ("cz_auto", False)]:
        if key not in st.session_state:
            st.session_state[key] = val

    idx = st.session_state.cz_idx % n

    VISTAS[idx][1]()

    c_prev, c_ind, c_next, c_auto = st.columns([1, 8, 1, 3])
    with c_prev:
        if st.button("◀", key="cz_prev", width='stretch'):
            st.session_state.cz_idx = (idx - 1) % n
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
        if st.button("▶", key="cz_next", width='stretch'):
            st.session_state.cz_idx = (idx + 1) % n
            st.rerun()
    with c_auto:
        auto = st.toggle("Auto-avanzar", key="cz_auto")
        if auto:
            tick = st_autorefresh(interval=INTERVALO_ZONAS_SEG * 1000, key="cz_tick")
            if tick != st.session_state.cz_tick_prev:
                st.session_state.cz_idx = (st.session_state.cz_idx + 1) % n
                st.session_state.cz_tick_prev = tick
