import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd


def _conectar():
    cfg = st.secrets["postgres"]
    return psycopg2.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 5432)),
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )


def _query(sql: str) -> pd.DataFrame:
    conn = _conectar()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    finally:
        conn.close()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=3600)
def cargar_empleados() -> pd.DataFrame:
    """id, nombre completo — para resolver Chofer, Peoneta1, Peoneta2."""
    df = _query("SELECT id, name, last_name FROM personnel_employee WHERE active = TRUE")
    if not df.empty:
        df["nombre"] = df["name"] + " " + df["last_name"]
    return df[["id", "nombre"]] if not df.empty else df


@st.cache_data(ttl=3600)
def cargar_productos() -> pd.DataFrame:
    """id, name — para resolver idProducto."""
    return _query("SELECT id, name FROM products_product WHERE active = TRUE")


@st.cache_data(ttl=3600)
def cargar_razones() -> pd.DataFrame:
    """id, name — para resolver Razon (fallo de visita)."""
    return _query("SELECT id, name FROM visits_visitfailurereason WHERE active = TRUE")


@st.cache_data(ttl=3600)
def cargar_vehiculos() -> pd.DataFrame:
    """id, plate — para resolver Patente (ID numérico → patente real)."""
    return _query("SELECT id, plate FROM visits_vehicle WHERE active = TRUE")
