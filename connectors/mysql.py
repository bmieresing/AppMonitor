import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

def _hoy() -> str:
    return datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")


@st.cache_data(ttl=300)
def cargar_recolecciones() -> pd.DataFrame:
    cfg = st.secrets["mysql"]
    conn = pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM VistaMonitor WHERE Fecha = %s", (_hoy(),))
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Litros"] = pd.to_numeric(df["Litros"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=60)
def cargar_estado_locales() -> pd.DataFrame:
    """Todos los locales de las rutas activas hoy con su Estado actual."""
    cfg = st.secrets["mysql"]
    conn = pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT lr.Ruta AS NombreRuta, lr.ID_Local, lr.Local, lr.Estado,
                       lr.Prioridad, lr.CentroAcopio, u.Chofer
                FROM LocalesRuta lr
                JOIN Usuarios u ON lr.Mail_Oficial = u.Correo
                WHERE lr.idRuta IN (
                    SELECT DISTINCT Ruta FROM ResumenCompleto WHERE Fecha = %s
                )
            """, (_hoy(),))
            rows = cur.fetchall()
    finally:
        conn.close()

    return pd.DataFrame(rows) if rows else pd.DataFrame()
