import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, date

from connectors.sheets import cargar_datos
from components.tabla import mostrar_tabla

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

# Header
col_titulo, col_hora = st.columns([3, 1])
col_titulo.title(f"App Monitor — {date.today().strftime('%d/%m/%Y')}")
col_hora.markdown(
    f"<div style='text-align:right; padding-top:16px; color:gray'>"
    f"Actualizado: {datetime.now().strftime('%H:%M:%S')}</div>",
    unsafe_allow_html=True,
)

# Tabla del día
df = cargar_datos()
mostrar_tabla(df)
