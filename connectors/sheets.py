import streamlit as st
import gspread
import pandas as pd
from datetime import date

COLUMNAS_INTERES = ["FECHA", "CHOFER", "PEONETA1", "PEONETA2", "PATENTE", "PROM RUTA"]

@st.cache_data(ttl=300)
def cargar_datos() -> pd.DataFrame:
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    cfg = st.secrets["sheets"]
    hoja = gc.open_by_key(cfg["spreadsheet_id"]).worksheet(cfg["sheet_name"])
    filas = hoja.get(cfg.get("sheet_range", "A:Z"))
    if not filas or len(filas) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(filas[1:], columns=filas[0])
    df.replace({"#N/A": None, "": None}, inplace=True)

    # Filtrar solo columnas de interés (por coincidencia parcial, case-insensitive)
    cols_sel = [
        c for c in df.columns
        if any(k in c.upper() for k in COLUMNAS_INTERES)
    ]
    df = df[cols_sel] if cols_sel else df

    # Filtrar filas del día de hoy por columna Fecha (acepta cualquier formato parseable)
    col_fecha = next((c for c in df.columns if "FECHA" in c.upper()), None)
    if col_fecha:
        fechas = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
        df = df[fechas.dt.date == date.today()]

    return df.reset_index(drop=True)
