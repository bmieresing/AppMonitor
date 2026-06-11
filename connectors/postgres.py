import functools

import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd

from connectors.estado_carga import (
    registrar_carga, registrar_falla, ciclo_ok, intento_fallido,
)

# Versión de cada tabla en el último ciclo confirmado (mismo esquema
# todo-o-nada que connectors/mysql.py)
_ultimo_ok: dict[str, pd.DataFrame] = {}


def _conectar():
    cfg = st.secrets["postgres"]
    return psycopg2.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 5432)),
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        connect_timeout=10,
    )


def _query(sql: str, tabla: str = "?") -> pd.DataFrame:
    """Si falla, registra la falla (log a consola + marcador rojo junto a la
    fecha) y RELANZA: el fracaso no debe quedar cacheado (st.cache_data no
    cachea excepciones); el respaldo lo maneja el decorador _con_respaldo."""
    try:
        conn = _conectar()
    except psycopg2.Error as e:
        registrar_falla("PostgreSQL", tabla, e)
        raise
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    except psycopg2.Error as e:
        registrar_falla("PostgreSQL", tabla, e)
        raise
    finally:
        conn.close()
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    registrar_carga("PostgreSQL", tabla, len(df))
    return df


def _con_respaldo(tabla: str):
    """Mismo commit todo-o-nada que connectors/mysql.py: con falla propia o
    ciclo sin confirmar, sirve la versión del último ciclo confirmado; con el
    ciclo confirmado, sirve lo nuevo y lo guarda. El fracaso nunca queda
    cacheado (la excepción atraviesa st.cache_data) → reintento al rerun."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Fail-fast: si el intento de ciclo ya falló, ni consultar la fuente
            if intento_fallido():
                return _ultimo_ok.get(tabla, pd.DataFrame()).copy()
            try:
                df = fn(*args, **kwargs)
            except psycopg2.Error:
                return _ultimo_ok.get(tabla, pd.DataFrame()).copy()
            if ciclo_ok():
                _ultimo_ok[tabla] = df.copy()
                return df
            return _ultimo_ok.get(tabla, df).copy()
        return wrapper
    return deco


@_con_respaldo("personnel_employee")
@st.cache_data(ttl=3600)
def cargar_empleados() -> pd.DataFrame:
    """id, nombre completo — para resolver Chofer, Peoneta1, Peoneta2."""
    df = _query("SELECT id, name, last_name FROM personnel_employee WHERE active = TRUE",
                tabla="personnel_employee")
    if not df.empty:
        df["nombre"] = df["name"] + " " + df["last_name"]
    return df[["id", "nombre"]] if not df.empty else df


@_con_respaldo("products_product")
@st.cache_data(ttl=3600)
def cargar_productos() -> pd.DataFrame:
    """id, name — para resolver idProducto."""
    return _query("SELECT id, name FROM products_product WHERE active = TRUE",
                  tabla="products_product")


@_con_respaldo("visits_visitfailurereason")
@st.cache_data(ttl=3600)
def cargar_razones() -> pd.DataFrame:
    """id, name — para resolver Razon (fallo de visita)."""
    return _query("SELECT id, name FROM visits_visitfailurereason WHERE active = TRUE",
                  tabla="visits_visitfailurereason")


@_con_respaldo("visits_vehicle")
@st.cache_data(ttl=3600)
def cargar_vehiculos() -> pd.DataFrame:
    """id, plate — para resolver Patente (ID numérico → patente real)."""
    return _query("SELECT id, plate FROM visits_vehicle WHERE active = TRUE",
                  tabla="visits_vehicle")
