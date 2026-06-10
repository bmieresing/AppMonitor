import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


def _hoy() -> str:
    return datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta un query en MySQL. Si la conexión falla, muestra el error en
    pantalla y retorna un DataFrame vacío para que el monitor no se caiga."""
    cfg = st.secrets["mysql"]
    try:
        conn = pymysql.connect(
            host=cfg["host"],
            port=int(cfg.get("port", 3306)),
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
    except pymysql.MySQLError as e:
        st.error(f"Sin conexión a MySQL: {e}")
        return pd.DataFrame()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except pymysql.MySQLError as e:
        st.error(f"Error consultando MySQL: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=300)
def cargar_recolecciones() -> pd.DataFrame:
    df = _query("SELECT * FROM VistaMonitor WHERE Fecha = %s", (_hoy(),))
    if not df.empty:
        df["Litros"] = pd.to_numeric(df["Litros"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=60)
def cargar_estado_locales() -> pd.DataFrame:
    """Todos los locales de las rutas activas hoy con su Estado actual."""
    return _query("""
        SELECT lr.Ruta AS NombreRuta, lr.ID_Local, lr.Local, lr.Estado,
               lr.Prioridad, lr.CentroAcopio, u.Chofer
        FROM LocalesRuta lr
        JOIN Usuarios u ON lr.Mail_Oficial = u.Correo
        WHERE lr.Fecha_Registro = %s
    """, (_hoy(),))


@st.cache_data(ttl=300)
def cargar_emergencias() -> pd.DataFrame:
    """Emergencias asignadas hoy con chofer_asignado. Fuente: appsheet_db.Emergencias."""
    return _query(
        "SELECT id_local, chofer_asignado FROM Emergencias "
        "WHERE fecha_asignacion_emergencia = %s AND chofer_asignado IS NOT NULL",
        (_hoy(),),
    )


@st.cache_data(ttl=3600)
def cargar_usuarios_vehiculos() -> pd.DataFrame:
    """Vehiculo (ID) y Chofer (ID) desde Usuarios — para resolver Patente → Chofer sin depender de visitas."""
    return _query("SELECT Vehiculo, Chofer FROM Usuarios WHERE Vehiculo IS NOT NULL AND Chofer IS NOT NULL")
