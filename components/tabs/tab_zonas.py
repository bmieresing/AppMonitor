import streamlit as st
import pandas as pd
from connectors.mysql import cargar_estado_locales
from components.helpers.data_prep import _preparar_datos
from components.widgets.donuts import _donuts_global
from components.widgets.cards import _cards_choferes_tanque
from components.widgets.layout import _css, _header


def mostrar_cards_choferes(
    df_sheets: pd.DataFrame,
    df_rec: pd.DataFrame,
    choferes_filter: set,
    key_prefix: str = "",
    tab_nombre: str = "",
    data_comp_override: pd.DataFrame | None = None,
):
    """Tab con tarjetas tipo tanque por chofer (sin gráficos de barras)."""
    data_comp = pd.DataFrame()
    if data_comp_override is not None:
        data_comp = data_comp_override
    elif not df_sheets.empty and not df_rec.empty:
        result = _preparar_datos(df_sheets, df_rec)
        data_comp = result if result is not None else pd.DataFrame()

    df_locales = cargar_estado_locales()
    df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]

    n_choferes = len(data_comp) if not data_comp.empty else 0
    cols = 6 if n_choferes > 12 else 5 if n_choferes > 6 else 4

    _css()
    _header(tab_nombre, key_prefix=key_prefix)
    _donuts_global(df_rec, df_locales, data_comp, tab_nombre=tab_nombre)
    st.divider()
    _cards_choferes_tanque(df_rec, df_locales, data_comp, key_prefix=key_prefix, cols_por_fila=cols)
