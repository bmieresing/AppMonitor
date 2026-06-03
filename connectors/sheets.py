import streamlit as st
import gspread
import pandas as pd


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
    return df
