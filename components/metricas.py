import streamlit as st
import pandas as pd


def mostrar_metricas(df: pd.DataFrame):
    col_km = next((c for c in df.columns if "KM DÍA" in c.upper() or "KM DIA" in c.upper()), None)
    col_litros_rep = next((c for c in df.columns if "LITROS REP" in c.upper()), None)
    col_litros_fis = next((c for c in df.columns if "LITROS FÍS" in c.upper() or "LITROS FIS" in c.upper()), None)
    col_obs = next((c for c in df.columns if "OBSERV" in c.upper()), None)

    total_rutas = len(df)
    rutas_activas = int(df[col_km].notna().sum()) if col_km else 0

    def sumar(col):
        if col is None:
            return 0
        return pd.to_numeric(df[col].str.replace(".", "").str.replace(",", "."), errors="coerce").sum()

    km_total = sumar(col_km)
    litros_rep = sumar(col_litros_rep)
    litros_fis = sumar(col_litros_fis)
    con_obs = int(df[col_obs].notna().sum()) if col_obs else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rutas", f"{rutas_activas} / {total_rutas}")
    c2.metric("KM Día", f"{km_total:,.0f}")
    c3.metric("Litros Reportados", f"{litros_rep:,.0f}")
    c4.metric("Litros Físicos", f"{litros_fis:,.0f}")
    c5.metric("Con observaciones", con_obs)
