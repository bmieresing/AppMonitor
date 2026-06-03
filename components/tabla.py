import streamlit as st
import pandas as pd


def _estilo(df: pd.DataFrame):
    col_litros_fis = next((c for c in df.columns if "LITROS FÍS" in c.upper() or "LITROS FIS" in c.upper()), None)

    def highlight(row):
        estilos = [""] * len(row)
        # Fila con KM vacíos → fondo naranja claro
        col_km = next((c for c in df.columns if "KM DÍA" in c.upper() or "KM DIA" in c.upper()), None)
        if col_km and pd.isna(row.get(col_km)):
            estilos = ["background-color: #ffe0cc"] * len(row)
        # Celda Litros Físicos vacía → amarillo
        if col_litros_fis and pd.isna(row.get(col_litros_fis)):
            idx = list(df.columns).index(col_litros_fis)
            estilos[idx] = "background-color: #ffff00"
        return estilos

    return df.style.apply(highlight, axis=1)


def mostrar_tabla(df: pd.DataFrame):
    if df.empty:
        st.warning("Sin datos disponibles.")
        return
    st.dataframe(_estilo(df), use_container_width=True, hide_index=True)
