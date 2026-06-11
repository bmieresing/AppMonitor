import time

import streamlit as st
import pandas as pd

from connectors.sheets import cargar_datos, cargar_datos_regiones
from connectors.mysql import (
    cargar_recolecciones, cargar_usuarios_vehiculos,
    cargar_estado_locales, cargar_emergencias, cargar_choferes_usuarios,
)
from connectors.postgres import (
    cargar_vehiculos, cargar_razones, cargar_empleados, cargar_productos,
)
from components.helpers.carrusel_data import lista_choferes
from components.helpers.id_resolver import resolver_recolecciones
from components.helpers.data_prep import _preparar_datos, _preparar_datos_regiones
from components.widgets.layout import _css, _header
from components.tabs.tab_global import mostrar_dashboard
from components.tabs.tab_zonas import mostrar_cards_choferes
from components.tabs.tab_rendimiento import mostrar_rendimiento
from components.tabs.tab_carrusel import mostrar_carrusel
from components.tabs.tab_carrusel_v2 import mostrar_carrusel_v2
from components.tabs.tab_carrusel_zonas import mostrar_carrusel_zonas
from components.tabs.tab_carrusel_zonas_v2 import mostrar_carrusel_zonas_v2
from components.tabs.tab_recolecciones import mostrar_tab_recolecciones
from components.tabs.tab_parametros import mostrar_parametros
from components.tabs.tab_v2 import mostrar_tab_v2
from connectors.estado_carga import tomar_ciclo, confirmar_ciclo
from config import RERUN_SEG

st.set_page_config(layout="wide", page_title="App Monitor")

# Auth: la maneja Streamlit Cloud (whitelist de correos). La app no implementa auth propia.

# Auto-refresh: rerun completo cada RERUN_SEG; los datos se recargan solo
# cuando vence su TTL (TTL_DATOS_SEG). Ver nota en config.py sobre el desfase
# rerun/TTL. Nativo (st.fragment run_every) en vez de st_autorefresh, que no
# estaba gatillando los reruns en el nivel superior de la app.
st.session_state["_marca_run_app"] = time.time()


@st.fragment(run_every=RERUN_SEG)
def _ciclo_rerun():
    # El cuerpo también corre durante el run completo (marca recién puesta →
    # no hace nada); solo el tick del timer, RERUN_SEG después, gatilla el
    # rerun de toda la app. Sin esta guarda sería un loop infinito.
    if time.time() - st.session_state.get("_marca_run_app", 0) >= RERUN_SEG - 1:
        st.rerun(scope="app")


_ciclo_rerun()

# Ciclo de datos EXPLÍCITO y ESTRICTO (todo-o-nada): cada TTL_DATOS_SEG se
# botan todas las cachés y se recargan las 11 tablas juntas, sin importar la
# vista activa. El ciclo solo se CONFIRMA si NINGUNA tabla falló; si alguna
# falla, todas las vistas siguen mostrando el último ciclo completo bueno
# (wrappers _con_respaldo de los conectores) y el próximo rerun (60 s)
# reintenta el ciclo entero. La fecha de los headers (hora_ciclo) solo
# avanza cuando un ciclo se confirma.
# tomar_ciclo() es atómico: si dos reruns/sesiones coinciden (botón ↺ +
# tick de 60 s, u otra pestaña), solo UNO ejecuta el ciclo — el otro sigue
# sirviendo el último confirmado. Evita los ciclos dobles.
_ciclo_nuevo = tomar_ciclo()
if _ciclo_nuevo:
    st.cache_data.clear()

# Carga de TODAS las tablas del ciclo, MySQL PRIMERO: si appsheet_db está
# caído (error 1040), la primera falla activa el fail-fast de los wrappers
# y el resto del intento ni siquiera consulta PostgreSQL ni los sheets —
# se sirve el último ciclo confirmado y el próximo rerun reintenta todo.
# Con caché vigente son hits gratis; tras el clear es la carga real.
cargar_recolecciones()
cargar_estado_locales()
cargar_emergencias()
cargar_usuarios_vehiculos()
cargar_choferes_usuarios()
cargar_empleados()
cargar_productos()
cargar_razones()
cargar_vehiculos()
cargar_datos()
cargar_datos_regiones()

if _ciclo_nuevo:
    confirmar_ciclo()

# Obtener los datos — vía los wrappers, que sirven SIEMPRE la versión del
# último ciclo confirmado
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
if not df_uv.empty:
    df_uv["Vehiculo"] = df_uv["Vehiculo"].astype(str)
choferes_stgo  = set(df_uv[df_uv["Vehiculo"].isin(vehiculos_stgo)]["Chofer"].tolist()) if not df_uv.empty else set()
choferes_todos = set(df_uv["Chofer"].tolist()) if not df_uv.empty else set()
choferes_reg   = choferes_todos - choferes_stgo

df_rec_stgo = df_rec[df_rec["Chofer"].isin(choferes_stgo)].copy() if "Chofer" in df_rec.columns else pd.DataFrame()
df_rec_reg  = df_rec[df_rec["Chofer"].isin(choferes_reg)].copy()  if "Chofer" in df_rec.columns else pd.DataFrame()

# Comparativas litros vs esperado — se calculan UNA vez y se pasan a todas
# las vistas (antes cada tab recalculaba la suya)
_dc_stgo = _preparar_datos(df_sheets, df_rec_stgo)
_dc_reg  = _preparar_datos_regiones(df_regiones, df_rec_reg)
_dc_stgo = _dc_stgo if _dc_stgo is not None else pd.DataFrame()
_dc_reg  = _dc_reg  if _dc_reg  is not None else pd.DataFrame()
data_comp_todos = pd.concat([_dc_stgo, _dc_reg], ignore_index=True) if not (_dc_stgo.empty and _dc_reg.empty) else pd.DataFrame()

# El grupo v2 va después de Parametros, en el mismo orden que los originales
VISTAS = [
    "Global", "Santiago", "Regiones", "Recolecciones", "Rendimiento",
    "Carrusel", "Carrusel Zonas", "Parametros",
    "Global v2", "Santiago v2", "Regiones v2", "Carrusel v2", "Carrusel Zonas v2",
    "Global v3", "Santiago v3", "Regiones v3", "Carrusel v3", "Carrusel Zonas v3",
]

# Navegación desde card de chofer (?nav_carrusel=Nombre → Carrusel v1;
# ?nav_carrusel_v2 → Carrusel v2; ?nav_carrusel_v3 → Carrusel v3)
_nav_v1 = st.query_params.get("nav_carrusel", "")
_nav_v2 = st.query_params.get("nav_carrusel_v2", "")
_nav_v3 = st.query_params.get("nav_carrusel_v3", "")
if _nav_v1 or _nav_v2 or _nav_v3:
    # Misma lista que usan los carruseles (incluye choferes del sheet sin recolecciones)
    _ch_sorted = lista_choferes(df_rec, data_comp_todos)
    _target = _nav_v3 or _nav_v2 or _nav_v1
    if _nav_v3:
        if _target in _ch_sorted:
            st.session_state.carrusel3_idx = _ch_sorted.index(_target)
            # Limpiar la selección previa de pills para que tome el nuevo índice
            st.session_state.pop("carrusel3_slicer", None)
        st.session_state.nav_vista = "Carrusel v3"
    elif _nav_v2:
        if _target in _ch_sorted:
            st.session_state.carrusel2_idx = _ch_sorted.index(_target)
            st.session_state.pop("carrusel2_slicer", None)
        st.session_state.nav_vista = "Carrusel v2"
    else:
        if _target in _ch_sorted:
            st.session_state.carrusel_idx = _ch_sorted.index(_target)
            st.session_state.pop("slicer_chofer", None)
        st.session_state.nav_vista = "Carrusel"
    st.query_params.clear()
    st.rerun()

# Selector de vista: a diferencia de st.tabs, solo se ejecuta y renderiza
# la vista activa (st.tabs corría las 11 en cada rerun)
if "nav_vista" not in st.session_state:
    st.session_state.nav_vista = "Global"
vista = st.segmented_control(
    "Vista", VISTAS, key="nav_vista", label_visibility="collapsed"
) or "Global"

if vista == "Global":
    mostrar_dashboard(df_sheets, df_rec, choferes_filter=choferes_todos,
                      key_prefix="global_", tab_nombre="Global",
                      data_comp_override=_dc_stgo)

elif vista == "Santiago":
    mostrar_cards_choferes(df_sheets, df_rec_stgo, choferes_filter=choferes_stgo,
                           key_prefix="stgo_cards_", tab_nombre="Santiago",
                           data_comp_override=_dc_stgo)

elif vista == "Regiones":
    mostrar_cards_choferes(df_regiones, df_rec_reg, choferes_filter=choferes_reg,
                           key_prefix="reg_cards_", tab_nombre="Regiones",
                           data_comp_override=_dc_reg)

elif vista == "Recolecciones":
    _css()
    _header("Recolecciones")
    mostrar_tab_recolecciones(df_rec)

elif vista == "Rendimiento":
    _css()
    _header("Rendimiento")
    mostrar_rendimiento(df_rec)

elif vista == "Carrusel":
    _css()
    _header("Carrusel")
    mostrar_carrusel(df_rec, data_comp=data_comp_todos)

elif vista == "Carrusel Zonas":
    # Sin _header propio: cada vista interna (Global/Santiago/Regiones) ya trae el suyo
    _css()
    mostrar_carrusel_zonas(df_sheets, df_rec, df_rec_stgo, df_rec_reg, df_regiones,
                           choferes_todos, choferes_stgo, choferes_reg,
                           data_comp_stgo=_dc_stgo, data_comp_reg=_dc_reg)

elif vista == "Parametros":
    _css()
    _header("Parametros")
    mostrar_parametros(df_rec, df_sheets, df_regiones, choferes_stgo, choferes_reg,
                       data_comp_reg=_dc_reg)

elif vista == "Santiago v2":
    mostrar_tab_v2(df_rec_stgo, choferes_filter=choferes_stgo,
                   data_comp=_dc_stgo, tab_nombre="Santiago")

elif vista == "Global v2":
    # data_comp_centros=_dc_stgo: el override de litros/prom del centro Santiago
    # debe salir de la comparativa de Santiago, no de la global
    mostrar_tab_v2(df_rec, choferes_filter=choferes_todos,
                   data_comp=data_comp_todos, tab_nombre="Global",
                   data_comp_centros=_dc_stgo)

elif vista == "Regiones v2":
    mostrar_tab_v2(df_rec_reg, choferes_filter=choferes_reg,
                   data_comp=_dc_reg, tab_nombre="Regiones")

elif vista == "Carrusel v2":
    mostrar_carrusel_v2(df_rec, data_comp=data_comp_todos)

# Grupo v3: igual a v2 pero con el emoji a la izquierda de la dona (estilo v1)
elif vista == "Global v3":
    mostrar_tab_v2(df_rec, choferes_filter=choferes_todos,
                   data_comp=data_comp_todos, tab_nombre="Global",
                   data_comp_centros=_dc_stgo,
                   key_prefix="v3_", emoji_lado=True)

elif vista == "Santiago v3":
    mostrar_tab_v2(df_rec_stgo, choferes_filter=choferes_stgo,
                   data_comp=_dc_stgo, tab_nombre="Santiago",
                   key_prefix="v3_", emoji_lado=True)

elif vista == "Regiones v3":
    mostrar_tab_v2(df_rec_reg, choferes_filter=choferes_reg,
                   data_comp=_dc_reg, tab_nombre="Regiones",
                   key_prefix="v3_", emoji_lado=True)

elif vista == "Carrusel v3":
    mostrar_carrusel_v2(df_rec, data_comp=data_comp_todos, keys_ns="carrusel3")

elif vista == "Carrusel Zonas v3":
    mostrar_carrusel_zonas_v2(df_rec, df_rec_stgo, df_rec_reg,
                              choferes_todos, choferes_stgo, choferes_reg,
                              data_comp_todos, _dc_stgo, _dc_reg,
                              keys_ns="czv3", emoji_lado=True)

elif vista == "Carrusel Zonas v2":
    mostrar_carrusel_zonas_v2(df_rec, df_rec_stgo, df_rec_reg,
                              choferes_todos, choferes_stgo, choferes_reg,
                              data_comp_todos, _dc_stgo, _dc_reg)
