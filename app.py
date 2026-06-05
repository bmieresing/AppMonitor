import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Santiago")

from connectors.sheets import cargar_datos
from connectors.mysql import cargar_recolecciones
from components.recolecciones import resolver_recolecciones
from components.dashboard import mostrar_dashboard
from components.rendimiento import mostrar_rendimiento
from components.carrusel import mostrar_carrusel

st.set_page_config(layout="wide", page_title="App Monitor")

# Auth
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("App Monitor")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets["app_password"]:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

# Auto-refresh
intervalo = int(st.secrets.get("refresh_interval_seconds", 300)) * 1000
st_autorefresh(interval=intervalo, key="refresh")

# Cargar datos una sola vez
df_sheets = cargar_datos()
df_rec = resolver_recolecciones(cargar_recolecciones())

tab_dashboard, tab_rendimiento, tab_carrusel = st.tabs(["Dashboard", "Rendimiento", "Carrusel"])

with tab_dashboard:
    mostrar_dashboard(df_sheets, df_rec)

with tab_rendimiento:
    mostrar_rendimiento(df_rec)

with tab_carrusel:
    mostrar_carrusel(df_rec)
