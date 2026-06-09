import streamlit as st
import streamlit.components.v1 as _cv1
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Santiago")

from connectors.sheets import cargar_datos, cargar_datos_regiones
from connectors.mysql import cargar_recolecciones, cargar_usuarios_vehiculos
from connectors.postgres import cargar_vehiculos
from components.recolecciones import resolver_recolecciones
from components.dashboard import mostrar_dashboard, mostrar_cards_choferes, _preparar_datos_regiones
from components.rendimiento import mostrar_rendimiento
from components.carrusel import mostrar_carrusel, mostrar_carrusel_zonas
from components.tab_recolecciones import mostrar_tab_recolecciones
from components.tab_parametros import mostrar_parametros

st.set_page_config(layout="wide", page_title="App Monitor")

# Auth: Google OAuth en producción, contraseña en local

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

# Navegación desde card de chofer (link ?nav_carrusel=Nombre)
_nav_target = st.query_params.get("nav_carrusel", "")
if _nav_target:
    _ch_sorted = sorted(df_rec["NombreChofer"].dropna().unique().tolist()) if not df_rec.empty and "NombreChofer" in df_rec.columns else []
    if _nav_target in _ch_sorted:
        st.session_state.carrusel_idx = _ch_sorted.index(_nav_target)
    st.session_state._do_nav_car = True
    st.query_params.clear()
    st.rerun()

if st.session_state.get("_do_nav_car"):
    st.session_state._do_nav_car = False
    _cv1.html("""<script>
setTimeout(function(){
    var t=window.parent.document.querySelectorAll('[data-baseweb="tab"],[role="tab"]');
    for(var i=0;i<t.length;i++){
        if(t[i].textContent.trim()==='Carrusel'){t[i].click();break;}
    }
},300);
</script>""", height=1)

_, col_btn = st.columns([10, 1])
with col_btn:
    if st.button("↺ Actualizar", use_container_width=True, help="Recarga todos los datos desde MySQL, PostgreSQL y Google Sheets"):
        st.cache_data.clear()
        st.rerun()

tab_global, tab_stgo, tab_reg, tab_rec_tab, tab_rendimiento, tab_carrusel, tab_cz, tab_params = st.tabs([
    "Global", "Santiago", "Regiones", "Recolecciones", "Rendimiento", "Carrusel", "Carrusel Zonas", "Parametros"
])

with tab_global:
    mostrar_dashboard(df_sheets, df_rec, key_prefix="global_", choferes_filter=choferes_todos, tab_nombre="Global", mostrar_donuts=True, mostrar_peores=False)

with tab_stgo:
    mostrar_cards_choferes(df_sheets, df_rec_stgo, choferes_filter=choferes_stgo, key_prefix="stgo_cards_", tab_nombre="Santiago")

with tab_reg:
    _data_comp_reg = _preparar_datos_regiones(df_regiones, df_rec_reg)
    mostrar_cards_choferes(df_regiones, df_rec_reg, choferes_filter=choferes_reg, key_prefix="reg_cards_", tab_nombre="Regiones", data_comp_override=_data_comp_reg)

with tab_rec_tab:
    mostrar_tab_recolecciones(df_rec)

with tab_rendimiento:
    mostrar_rendimiento(df_rec)

with tab_carrusel:
    mostrar_carrusel(df_rec)

with tab_cz:
    mostrar_carrusel_zonas(df_sheets, df_rec, df_rec_stgo, df_rec_reg, df_regiones, choferes_todos, choferes_stgo, choferes_reg)

with tab_params:
    mostrar_parametros(df_rec, df_sheets, df_regiones, choferes_stgo, choferes_reg)
