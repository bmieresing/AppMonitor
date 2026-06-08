import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Santiago")

from connectors.sheets import cargar_datos, cargar_datos_regiones
from connectors.mysql import cargar_recolecciones, cargar_usuarios_vehiculos
from connectors.postgres import cargar_vehiculos
from components.recolecciones import resolver_recolecciones
from components.dashboard import mostrar_dashboard
from components.rendimiento import mostrar_rendimiento
from components.carrusel import mostrar_carrusel, mostrar_carrusel_zonas
from components.tab_recolecciones import mostrar_tab_recolecciones

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
df_sheets     = cargar_datos()
df_rec        = resolver_recolecciones(cargar_recolecciones())
df_regiones   = cargar_datos_regiones()

# Patentes del sheet Stgo
col_pat = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
stgo_patentes = set(df_sheets[col_pat].dropna().tolist()) if col_pat and not df_sheets.empty else set()

# Usuarios[Vehiculo] → visits_vehicle[id] → plate → match sheet
# Convertir IDs a str para evitar mismatch de tipos entre MySQL y PostgreSQL
df_veh = cargar_vehiculos()
vehiculos_stgo = set(df_veh[df_veh["plate"].isin(stgo_patentes)]["id"].astype(str).tolist()) if not df_veh.empty else set()

df_uv = cargar_usuarios_vehiculos()
df_uv["Vehiculo"] = df_uv["Vehiculo"].astype(str)
choferes_stgo  = set(df_uv[df_uv["Vehiculo"].isin(vehiculos_stgo)]["Chofer"].tolist()) if not df_uv.empty else set()
choferes_todos = set(df_uv["Chofer"].tolist()) if not df_uv.empty else set()
choferes_reg   = choferes_todos - choferes_stgo

df_rec_stgo = df_rec[df_rec["Chofer"].isin(choferes_stgo)].copy() if "Chofer" in df_rec.columns else pd.DataFrame()
df_rec_reg  = df_rec[df_rec["Chofer"].isin(choferes_reg)].copy()  if "Chofer" in df_rec.columns else pd.DataFrame()

tab_global, tab_stgo, tab_reg, tab_rec_tab, tab_rendimiento, tab_carrusel, tab_cz = st.tabs([
    "Global", "Santiago", "Regiones", "Recolecciones", "Rendimiento", "Carrusel", "Carrusel Zonas"
])

with tab_global:
    mostrar_dashboard(df_sheets, df_rec, key_prefix="global_", choferes_filter=choferes_todos, tab_nombre="Global", mostrar_donuts=True, mostrar_peores=False)

with tab_stgo:
    mostrar_dashboard(df_sheets, df_rec_stgo, key_prefix="stgo_", mostrar_centros=False, choferes_filter=choferes_stgo, tab_nombre="Santiago", mostrar_donuts=True, mostrar_peores=False)

with tab_reg:
    mostrar_dashboard(df_regiones, df_rec_reg, key_prefix="reg_", choferes_filter=choferes_reg, mostrar_litros=False, mostrar_peores=False, mostrar_litros_simple=True, mostrar_centros=False, tab_nombre="Regiones", mostrar_donuts=True)

with tab_rec_tab:
    mostrar_tab_recolecciones(df_rec)

with tab_rendimiento:
    mostrar_rendimiento(df_rec)

with tab_carrusel:
    mostrar_carrusel(df_rec)

with tab_cz:
    mostrar_carrusel_zonas(df_sheets, df_rec, df_rec_stgo, df_rec_reg, df_regiones, choferes_todos, choferes_stgo, choferes_reg)
