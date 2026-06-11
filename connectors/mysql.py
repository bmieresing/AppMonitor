import functools
import threading

import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TTL_DATOS_SEG
from connectors.estado_carga import (
    registrar_carga, registrar_falla, ciclo_ok, intento_fallido,
)

# pymysql no es thread-safe: las sesiones/fragments comparten la conexión
# bajo este lock (los queries son cortos, no se nota)
_lock = threading.Lock()

# Versión de cada tabla en el último ciclo CONFIRMADO (todas las tablas OK).
# Ciclo estricto todo-o-nada: mientras el ciclo en curso no se confirme, los
# loaders sirven esto — nunca se mezclan datos de ciclos distintos.
_ultimo_ok: dict[str, pd.DataFrame] = {}


def _hoy() -> str:
    return datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")


@st.cache_resource
def _conexion() -> pymysql.connections.Connection:
    """UNA conexión MySQL por proceso, compartida por todos los queries.
    Antes cada query abría y cerraba la suya (~5 por ciclo) peleando por
    slots contra un RDS que ya anda al límite (error 1040). autocommit=True
    es clave: sin él, la conexión persistente quedaría pegada al snapshot
    de su primera transacción y leería datos viejos para siempre."""
    cfg = st.secrets["mysql"]
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        autocommit=True,
    )


def _query(sql: str, params: tuple = (), tabla: str = "?") -> pd.DataFrame:
    """Ejecuta un query reutilizando la conexión compartida. Si falla,
    registra la falla (log a consola + marcador rojo junto a la fecha) y
    RELANZA la excepción: así atraviesa st.cache_data (que no cachea
    excepciones) y el resultado fallido nunca queda cacheado — el respaldo
    lo maneja el decorador _con_respaldo del loader."""
    try:
        with _lock:
            conn = _conexion()
            conn.ping(reconnect=True)  # reconecta si el servidor botó la conexión
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except pymysql.MySQLError as e:
        registrar_falla("MySQL", tabla, e)
        raise
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    registrar_carga("MySQL", tabla, len(df))
    return df


def _con_respaldo(tabla: str):
    """Envuelve a un loader cacheado con el commit todo-o-nada del ciclo:

    - Si el loader truena (falla ya registrada por _query; la excepción
      atravesó st.cache_data, así que el fracaso NO queda cacheado): sirve
      la versión del último ciclo confirmado.
    - Si carga bien pero el ciclo aún NO está confirmado (en curso, o falló
      otra tabla): también sirve la del último ciclo confirmado — todas las
      tablas en pantalla pertenecen siempre al mismo ciclo.
    - Con el ciclo confirmado: sirve lo nuevo y lo guarda como confirmado."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Fail-fast: si el intento de ciclo ya falló, ni consultar la
            # fuente — servir el último ciclo confirmado hasta el reintento
            if intento_fallido():
                return _ultimo_ok.get(tabla, pd.DataFrame()).copy()
            try:
                df = fn(*args, **kwargs)
            except pymysql.MySQLError:
                return _ultimo_ok.get(tabla, pd.DataFrame()).copy()
            if ciclo_ok():
                # Versión FINAL del loader (post-proceso), en cada llamada
                # (hit o miss): barato y siempre al día
                _ultimo_ok[tabla] = df.copy()
                return df
            return _ultimo_ok.get(tabla, df).copy()
        return wrapper
    return deco


@_con_respaldo("VistaMonitor")
@st.cache_data(ttl=TTL_DATOS_SEG)
def cargar_recolecciones() -> pd.DataFrame:
    # Solo las columnas que la app consume: la vista tiene ~24 y el resto
    # (observaciones, whatsapp, comuna, etc.) viajaba desde RDS sin usarse.
    # Si un widget nuevo necesita otra columna, agregarla acá.
    df = _query(
        "SELECT Litros, Razon, Chofer, Patente, idProducto, "
        "idLocalSistema, Local, Emergencia, FechaObservacion "
        "FROM VistaMonitor WHERE Fecha = %s",
        (_hoy(),),
        tabla="VistaMonitor",
    )
    if not df.empty:
        df["Litros"] = pd.to_numeric(df["Litros"], errors="coerce").fillna(0)
    return df


@_con_respaldo("LocalesRuta")
@st.cache_data(ttl=TTL_DATOS_SEG)
def cargar_estado_locales() -> pd.DataFrame:
    """Todos los locales de las rutas activas hoy con su Estado actual.
    TTL alineado al ciclo de datos del dashboard."""
    return _query("""
        SELECT lr.Ruta AS NombreRuta, lr.ID_Local, lr.Local, lr.Estado,
               lr.Prioridad, lr.CentroAcopio, u.Chofer
        FROM LocalesRuta lr
        JOIN Usuarios u ON lr.Mail_Oficial = u.Correo
        WHERE lr.Fecha_Registro = %s
    """, (_hoy(),), tabla="LocalesRuta")


@_con_respaldo("Emergencias")
@st.cache_data(ttl=TTL_DATOS_SEG)
def cargar_emergencias() -> pd.DataFrame:
    """Emergencias asignadas hoy con chofer_asignado. Fuente: appsheet_db.Emergencias."""
    return _query(
        "SELECT id_local, chofer_asignado FROM Emergencias "
        "WHERE fecha_asignacion_emergencia = %s AND chofer_asignado IS NOT NULL",
        (_hoy(),),
        tabla="Emergencias",
    )


@_con_respaldo("Usuarios")
@st.cache_data(ttl=3600)
def _cargar_usuarios() -> pd.DataFrame:
    """UN solo SELECT a Usuarios por ciclo; de acá derivan los dos consumos
    (antes eran dos queries casi iguales a la misma tabla)."""
    return _query("SELECT Vehiculo, Chofer FROM Usuarios WHERE Chofer IS NOT NULL",
                  tabla="Usuarios")


def cargar_usuarios_vehiculos() -> pd.DataFrame:
    """Vehiculo (ID) y Chofer (ID) desde Usuarios — para resolver Patente → Chofer sin depender de visitas."""
    df = _cargar_usuarios()
    if df.empty:
        return df
    return df[df["Vehiculo"].notna()].copy()


def cargar_choferes_usuarios() -> pd.DataFrame:
    """Todos los IDs de chofer registrados en Usuarios (AppSheet), tengan o no
    vehículo asignado — para diagnosticar si un chofer falta por ingresar."""
    df = _cargar_usuarios()
    if df.empty:
        return pd.DataFrame(columns=["Chofer"])
    return df[["Chofer"]].drop_duplicates().reset_index(drop=True)
