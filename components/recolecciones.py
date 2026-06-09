import streamlit as st
import pandas as pd
from connectors.postgres import cargar_empleados, cargar_vehiculos, cargar_productos


def _resolver_nombre(df: pd.DataFrame, col_id: str, lookup: pd.DataFrame, col_nuevo: str) -> pd.DataFrame:
    if lookup.empty or col_id not in df.columns:
        df[col_nuevo] = df[col_id].astype(str)
        return df
    mapa = lookup.set_index("id")["nombre"]
    df[col_nuevo] = df[col_id].map(mapa).fillna(df[col_id].astype(str))
    return df


def resolver_recolecciones(df: pd.DataFrame) -> pd.DataFrame:
    """Resuelve IDs numéricos a nombres legibles. Llamar una sola vez en app.py."""
    if df.empty:
        return df
    empleados = cargar_empleados()
    vehiculos = cargar_vehiculos().rename(columns={"plate": "nombre"})
    productos = cargar_productos().rename(columns={"name": "nombre"})
    df = _resolver_nombre(df, "Chofer", empleados, "NombreChofer")
    df = _resolver_nombre(df, "Peoneta1", empleados, "NombrePeoneta1")
    df = _resolver_nombre(df, "Peoneta2", empleados, "NombrePeoneta2")
    df = _resolver_nombre(df, "Patente", vehiculos, "Patente_Real")
    df = _resolver_nombre(df, "idProducto", productos, "Producto")
    # VistaMonitor tiene 1 fila por producto por visita y puede duplicar filas
    # del mismo (local, producto). Dedup garantiza 1 fila por combinación única.
    if "idLocalSistema" in df.columns and "idProducto" in df.columns:
        df = df.drop_duplicates(subset=["idLocalSistema", "idProducto"])
    return df


def mostrar_recolecciones(df: pd.DataFrame):
    if df.empty:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    # Litros por chofer
    st.subheader("Litros por chofer")
    litros = (
        df[df["Litros"] > 0]
        .groupby("NombreChofer")["Litros"]
        .sum()
        .reset_index()
        .sort_values("Litros", ascending=False)
        .rename(columns={"NombreChofer": "Chofer"})
    )
    col_chart, col_tabla = st.columns([3, 1])
    with col_chart:
        st.bar_chart(litros.set_index("Chofer")["Litros"])
    with col_tabla:
        st.dataframe(litros, width='stretch', hide_index=True)

    st.divider()

    # Tabla detalle
    st.subheader("Detalle recolecciones")
    cols = [c for c in [
        "NombreRuta", "Local", "NombreChofer", "NombrePeoneta1", "NombrePeoneta2",
        "Patente_Real", "Litros", "Estado", "Prioridad", "Emergencia",
        "Mail_Oficial", "Comuna", "CentroAcopio",
        "whatsapp_asignado", "respuesta_whatsapp", "hora_respuesta_whatsapp",
        "Observaciones",
    ] if c in df.columns]
    st.dataframe(df[cols], width='stretch', hide_index=True)
