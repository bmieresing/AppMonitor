import streamlit as st
import pandas as pd
from connectors.mysql import cargar_estado_locales
from components.helpers.data_prep import _preparar_datos
from components.widgets.donuts import _donuts_global
from components.widgets.cards import _desempeno_centros
from components.widgets.layout import _css, _header


def mostrar_dashboard(
    df_sheets: pd.DataFrame,
    df_rec: pd.DataFrame,
    choferes_filter: set,
    key_prefix: str = "",
    tab_nombre: str = "",
    mostrar_centros: bool = True,
):
    result = _preparar_datos(df_sheets, df_rec)
    data_comp = result if result is not None else pd.DataFrame()
    df_locales = cargar_estado_locales()
    df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]
    _css()
    _header(tab_nombre, key_prefix=key_prefix)
    _donuts_global(df_rec, df_locales, data_comp, tab_nombre=tab_nombre)
    st.divider()
    if mostrar_centros:
        _desempeno_centros(df_rec, data_comp, df_locales)
