import streamlit as st
import pandas as pd


def _estilo(df: pd.DataFrame):
    col_prom = next((c for c in df.columns if "PROM" in c.upper()), None)

    def highlight(row):
        estilos = [""] * len(row)
        # Fila sin PROM RUTA → fondo amarillo claro
        if col_prom and pd.isna(row.get(col_prom)):
            estilos = ["background-color: #fffbcc"] * len(row)
        return estilos

    return df.style.apply(highlight, axis=1)


def mostrar_tabla(df: pd.DataFrame):
    if df.empty:
        st.warning("Sin datos para hoy.")
        return
    st.dataframe(_estilo(df), use_container_width=True, hide_index=True)
