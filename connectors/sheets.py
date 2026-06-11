import functools

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo

from config import TTL_DATOS_SEG
from connectors.estado_carga import (
    registrar_carga, registrar_falla, ciclo_ok, intento_fallido,
)

# Versión de cada hoja en el último ciclo confirmado (mismo esquema
# todo-o-nada que connectors/mysql.py)
_ultimo_ok: dict[str, pd.DataFrame] = {}


def _con_respaldo(hoja: str):
    """Mismo commit todo-o-nada que connectors/mysql.py: con falla propia o
    ciclo sin confirmar, sirve la versión del último ciclo confirmado; con el
    ciclo confirmado, sirve lo nuevo y lo guarda. (gspread lanza excepciones
    variadas → se atrapa Exception.)"""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Fail-fast: si el intento de ciclo ya falló (p. ej. MySQL caído),
            # ni consultar el sheet — son las cargas más lentas del ciclo
            if intento_fallido():
                return _ultimo_ok.get(hoja, pd.DataFrame()).copy()
            try:
                df = fn(*args, **kwargs)
            except Exception:
                return _ultimo_ok.get(hoja, pd.DataFrame()).copy()
            if ciclo_ok():
                _ultimo_ok[hoja] = df.copy()
                return df
            return _ultimo_ok.get(hoja, df).copy()
        return wrapper
    return deco


def _hoy() -> date:
    return datetime.now(ZoneInfo("America/Santiago")).date()

COLUMNAS_INTERES = ["FECHA", "RUTA", "CHOFER", "PEONETA1", "PEONETA2", "PATENTE", "PROM RUTA"]


def _letra_col(i: int) -> str:
    """Índice de columna (0-based) → letra de columna de Sheets (A, B, ... AA)."""
    letras = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        letras = chr(65 + r) + letras
    return letras

@_con_respaldo("Seguimiento diario")
@st.cache_data(ttl=TTL_DATOS_SEG * 2)  # respaldo: el ciclo (clear) manda; 2x evita vencimientos fuera de ciclo
def cargar_datos() -> pd.DataFrame:
    try:
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        cfg = st.secrets["sheets"]
        hoja = gc.open_by_key(cfg["spreadsheet_id"]).worksheet(cfg["sheet_name"])
        filas = hoja.get(cfg.get("sheet_range", "A:Z"))
    except Exception as e:
        registrar_falla("Sheets", "Seguimiento diario", e)
        raise  # atraviesa st.cache_data: el fracaso no queda cacheado
    registrar_carga("Sheets", "Seguimiento diario", max(len(filas) - 1, 0))
    if not filas or len(filas) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(filas[1:], columns=filas[0])
    # Fila real en el sheet (fila 1 = cabecera) y letra de cada columna,
    # para poder referenciar celdas (p. ej. F14) en el tab Parámetros
    df["_FilaSheet"] = range(2, len(df) + 2)
    letras = {c: _letra_col(i) for i, c in enumerate(filas[0])}
    df.replace({"#N/A": None, "": None}, inplace=True)

    # Filtrar solo columnas de interés (por coincidencia parcial, case-insensitive)
    cols_sel = [
        c for c in df.columns
        if any(k in c.upper() for k in COLUMNAS_INTERES)
    ]
    df = df[cols_sel + ["_FilaSheet"]] if cols_sel else df

    # Filtrar filas del día de hoy por columna Fecha (acepta cualquier formato parseable)
    col_fecha = next((c for c in df.columns if "FECHA" in c.upper()), None)
    if col_fecha:
        fechas = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
        df = df[fechas.dt.date == _hoy()]

    # Excluir fila de totales
    col_chofer = next((c for c in df.columns if "CHOFER" in c.upper()), None)
    if col_chofer:
        df = df[~df[col_chofer].str.contains("TOTALES", case=False, na=False)]

    df = df.reset_index(drop=True)
    df.attrs["letras_col"] = letras
    return df


ZONA_MAP = [
    ("ARICA",        "Arica"),
    ("IQQ",          "Iquique"),
    ("ANTO",         "Antofagasta"),
    ("LA SERENA",    "La Serena"),
    ("CV",           "Viña del Mar"),
    ("RANCAGUA",     "Rancagua"),
    ("NCH",          "Nuevo Chillán"),
    ("LL",           "Los Lagos"),
    ("TEMUCO",       "Temuco"),
    ("PUNTA ARENAS", "Punta Arenas"),
]


def mapear_zona(tripulacion: str) -> str | None:
    t = str(tripulacion).upper().strip()
    for prefijo, zona in ZONA_MAP:
        if t.startswith(prefijo):
            return zona
    return None


@_con_respaldo("Control Regiones")
@st.cache_data(ttl=TTL_DATOS_SEG * 2)  # respaldo: el ciclo (clear) manda; 2x evita vencimientos fuera de ciclo
def cargar_datos_regiones() -> pd.DataFrame:
    try:
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        cfg = st.secrets["sheets"]
        hoja = gc.open_by_key(cfg["spreadsheet_id"]).worksheet(
            cfg.get("sheet_name_regiones", "Control Regiones")
        )
        # A:I para incluir la columna RUTA (col I)
        filas = hoja.get("A:I")
    except Exception as e:
        registrar_falla("Sheets", "Control Regiones", e)
        raise  # atraviesa st.cache_data: el fracaso no queda cacheado
    registrar_carga("Sheets", "Control Regiones", max(len(filas) - 1, 0))
    if not filas or len(filas) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(filas[1:], columns=filas[0])
    df["_FilaSheet"] = range(2, len(df) + 2)
    letras = {c: _letra_col(i) for i, c in enumerate(filas[0])}
    df.replace({"#N/A": None, "#DIV/0!": None, "": None, "-": None}, inplace=True)

    # Filtrar hoy
    col_fecha = next((c for c in df.columns if "FECHA" in c.upper()), None)
    if col_fecha:
        fechas = pd.to_datetime(df[col_fecha], dayfirst=True, errors="coerce")
        df = df[fechas.dt.date == _hoy()]

    # Excluir filas TOTALES
    col_trip = next((c for c in df.columns if "TRIPULACI" in c.upper()), None)
    if col_trip:
        df = df[~df[col_trip].str.contains("TOTALES", case=False, na=False)]
        df["Zona"] = df[col_trip].apply(mapear_zona)

    # Parsear numéricos
    col_prom = next((c for c in df.columns if "PROM" in c.upper()), None)
    col_litros = next((c for c in df.columns if "LITROS" in c.upper() and c != "_FilaSheet"), None)
    for col in [col_prom, col_litros]:
        if col:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                errors="coerce",
            ).fillna(0)

    df = df.reset_index(drop=True)
    df.attrs["letras_col"] = letras
    return df
