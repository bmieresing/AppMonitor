# Tab Parámetros: diagnóstico de cómo cruzan los datos de Google Sheets con
# MySQL/PostgreSQL (matches por patente en Santiago y por nombre en Regiones).
# Las constantes y la configuración quedan en expanders al final.
import streamlit as st
import pandas as pd
from connectors.mysql import cargar_usuarios_vehiculos, cargar_choferes_usuarios
from connectors.postgres import cargar_empleados, cargar_vehiculos
from connectors.sheets import COLUMNAS_INTERES, ZONA_MAP
from components.helpers.data_prep import _norm_key, _mapa_empleados
from config import (
    EXCLUIR_LITROS,
    UMBRAL_VERDE, UMBRAL_AMARILLO,
    UMBRAL_COMP_VERDE, UMBRAL_COMP_AMARILLO,
    INTERVALO_CARRUSEL_SEG, INTERVALO_ZONAS_SEG,
    TTL_DATOS_SEG, RERUN_SEG,
)


def _widget_semaforo(titulo: str, verde: int, amarillo: int, descripcion: str = ""):
    """Barra horizontal con las tres zonas coloreadas y los umbrales marcados."""
    w_rojo     = amarillo
    w_amarillo = verde - amarillo
    w_verde    = 100 - verde

    st.markdown(f"**{titulo}**")
    if descripcion:
        st.caption(descripcion)

    barra = f"""
    <div style="margin:4px 0 2px">
        <div style="display:flex;border-radius:6px;overflow:hidden;height:28px;font-size:12px;font-weight:700">
            <div style="width:{w_rojo}%;background:#c0392b;display:flex;align-items:center;
                        justify-content:center;color:white;gap:4px">
                🔴 &lt; {amarillo}%
            </div>
            <div style="width:{w_amarillo}%;background:#e67e22;display:flex;align-items:center;
                        justify-content:center;color:white;gap:4px">
                🟡 {amarillo}–{verde-1}%
            </div>
            <div style="width:{w_verde}%;background:#2d7a2d;display:flex;align-items:center;
                        justify-content:center;color:white;gap:4px">
                🟢 ≥ {verde}%
            </div>
        </div>
    </div>
    """
    st.markdown(barra, unsafe_allow_html=True)


def _match_santiago(df_rec: pd.DataFrame, df_sheets: pd.DataFrame, choferes_stgo: set):
    """Cadena de match de Santiago: cada PATENTE del sheet debe encontrar su
    vehículo en PG, su chofer en MySQL y su nombre en PG para entrar a la comparativa."""
    st.markdown("#### 🔗 Santiago — match por patente")
    st.caption(
        "Sheet *Seguimiento diario* col. **PATENTE** → `visits_vehicle.plate` (PostgreSQL) "
        "→ `Usuarios.Vehiculo` (MySQL) → `personnel_employee` (PostgreSQL). "
        "Si un eslabón falla, esa patente queda fuera de la comparativa litros vs esperado."
    )

    col_patente = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
    col_prom    = next((c for c in df_sheets.columns if "PROM" in c.upper()), None)

    if not col_patente or df_sheets.empty:
        st.info("No hay datos del sheet Santiago para hoy.")
        return

    usuarios     = cargar_usuarios_vehiculos()
    vehiculos_pg = cargar_vehiculos()
    empleados_pg = cargar_empleados()

    mapa_placa_a_id    = vehiculos_pg.set_index("plate")["id"].to_dict() if not vehiculos_pg.empty else {}
    mapa_veh_a_chofer  = usuarios.set_index("Vehiculo")["Chofer"].to_dict() if not usuarios.empty else {}
    mapa_chofer_nombre = empleados_pg.set_index("id")["nombre"].to_dict() if not empleados_pg.empty else {}

    litros_por_patente = {}
    if not df_rec.empty and "Patente_Real" in df_rec.columns:
        litros_por_patente = (
            df_rec[df_rec["Litros"] > 0].groupby("Patente_Real")["Litros"].sum().to_dict()
        )

    # Referencia de celda en el sheet (letra de la columna PATENTE + fila real)
    letra_pat = df_sheets.attrs.get("letras_col", {}).get(col_patente, "")
    fila_por_patente = (
        df_sheets.drop_duplicates(col_patente).set_index(col_patente)["_FilaSheet"].to_dict()
        if "_FilaSheet" in df_sheets.columns else {}
    )

    filas = []
    for pat in sorted(df_sheets[col_patente].dropna().unique().tolist()):
        vid    = mapa_placa_a_id.get(pat)
        cid    = mapa_veh_a_chofer.get(vid) if vid is not None else None
        nombre = mapa_chofer_nombre.get(cid) if cid is not None else None
        celda  = (
            f"{letra_pat}{int(fila_por_patente[pat])}"
            if letra_pat and pat in fila_por_patente else "—"
        )
        prom_val = None
        if col_prom:
            row_s = df_sheets[df_sheets[col_patente] == pat]
            if not row_s.empty:
                try:
                    prom_val = float(str(row_s.iloc[0][col_prom]).replace(".", "").replace(",", "."))
                except (ValueError, TypeError):
                    pass
        litros = litros_por_patente.get(pat)
        filas.append({
            "Match": "✅" if nombre else "❌",
            "Celda sheet": celda,
            "Patente (sheet)": pat,
            "ID Vehículo (PG)": str(vid) if vid else "— sin match",
            "ID Chofer (MySQL)": str(cid) if cid else "— sin match",
            "Nombre Chofer (PG)": nombre or "— sin match",
            "PROM 3M (sheet)": f"{prom_val:,.0f}" if prom_val else "—",
            "Litros hoy (MySQL)": f"{litros:,.0f}" if litros else "0",
        })

    total  = len(filas)
    ok     = sum(1 for r in filas if r["Match"] == "✅")
    sin_v  = sum(1 for r in filas if r["ID Vehículo (PG)"].startswith("—"))
    sin_c  = sum(1 for r in filas if r["ID Chofer (MySQL)"].startswith("—"))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Patentes en el sheet", total)
    m2.metric("Match completo", ok, delta=f"{ok - total} sin match" if ok < total else "todas",
              delta_color="inverse" if ok < total else "off")
    m3.metric("Sin vehículo en PG", sin_v)
    m4.metric("Sin chofer en MySQL", sin_c)

    st.dataframe(pd.DataFrame(filas), width='stretch', hide_index=True)

    # Litros del día que NO entran a la comparativa (patente fuera del sheet)
    if not df_rec.empty and "Patente_Real" in df_rec.columns and "Chofer" in df_rec.columns:
        pats_sheet = set(df_sheets[col_patente].dropna().tolist())
        df_stgo = df_rec[df_rec["Chofer"].isin(choferes_stgo)]
        fuera = (
            df_stgo[(df_stgo["Litros"] > 0) & (~df_stgo["Patente_Real"].isin(pats_sheet))]
            .groupby("Patente_Real")
            .agg(NombreChofer=("NombreChofer", "first"), Litros=("Litros", "sum"))
            .reset_index()
            .rename(columns={"Patente_Real": "Patente"})
        )
        if not fuera.empty:
            st.warning(
                f"⚠️ {len(fuera)} patente(s) de Santiago con litros hoy que **no están en el sheet**: "
                f"esos litros no se cuentan en la comparativa litros vs esperado."
            )
            st.dataframe(fuera, width='stretch', hide_index=True)
        else:
            st.success("Todas las patentes con litros hoy están en el sheet. ✓")


def _match_regiones(data_comp_reg: pd.DataFrame | None, df_regiones: pd.DataFrame):
    """Match de Regiones: el sheet trae nombres de chofer (texto) que se cruzan
    contra NombreChofer de las recolecciones con clave normalizada."""
    st.markdown("#### 🔗 Regiones — match por nombre de chofer")
    st.caption(
        "Sheet *Control Regiones* col. **CHOFER** vs `NombreChofer` de las recolecciones "
        "(nombre resuelto desde `personnel_employee`). La clave de match se normaliza: "
        "minúsculas, sin tildes y espacios colapsados. Si el nombre está escrito distinto "
        "en el sheet, el chofer aparece dos veces (una sin litros y otra sin promedio). "
        "Para los que no tienen litros, se verifica además si el chofer existe en la tabla "
        "`Usuarios` de AppSheet: distingue **falta ingresarlo** de **no ha subido nada hoy**."
    )

    if data_comp_reg is None or data_comp_reg.empty:
        st.info("No hay datos de Regiones para hoy.")
        return

    df = data_comp_reg.copy()
    df["Prom"] = pd.to_numeric(df.get("Prom", 0), errors="coerce").fillna(0)
    df["LitrosHoy"] = pd.to_numeric(df.get("LitrosHoy", 0), errors="coerce").fillna(0)
    # La fila viene del sheet si trae _FilaSheet (el outer join deja NaN en las
    # que solo existen en las recolecciones de AppSheet)
    df["_en_sheet"] = (
        df["_FilaSheet"].notna() if "_FilaSheet" in df.columns else df["Prom"] > 0
    )

    # Choferes registrados en Usuarios (AppSheet), por nombre normalizado:
    # distingue "falta ingresarlo" de "está registrado pero no ha subido nada"
    nombres_registrados = set()
    u = cargar_choferes_usuarios()
    if not u.empty:
        mapa_emp = _mapa_empleados()
        nombres = pd.to_numeric(u["Chofer"], errors="coerce").map(mapa_emp).dropna()
        if not nombres.empty:
            nombres_registrados = set(_norm_key(nombres))
    df["_registrado"] = _norm_key(df["Chofer"].astype(str)).isin(nombres_registrados)

    def _estado(row) -> str:
        if row["_en_sheet"]:
            if row["LitrosHoy"] > 0 and row["Prom"] > 0:
                return "✅ Match"
            if row["LitrosHoy"] > 0:
                return "⚠️ Match, sin PROM en el sheet"
            if row["_registrado"]:
                return "⚠️ Registrado, sin recolecciones hoy"
            return "❌ No registrado en Usuarios (AppSheet)"
        return "❌ Solo en AppSheet, no está en el sheet"

    df["Match"] = df.apply(_estado, axis=1)

    # Referencia de celda en el sheet (letra de la columna CHOFER + fila real)
    col_chofer_sheet = next((c for c in df_regiones.columns if "CHOFER" in c.upper()), None)
    letra_ch = df_regiones.attrs.get("letras_col", {}).get(col_chofer_sheet, "")
    if "_FilaSheet" in df.columns and letra_ch:
        df["Celda sheet"] = df["_FilaSheet"].map(
            lambda f: f"{letra_ch}{int(f)}" if pd.notna(f) else "—"
        )

    n_ok    = int((df["Match"] == "✅ Match").sum())
    n_warn  = int(df["Match"].str.startswith("⚠️").sum())
    n_err   = int(df["Match"].str.startswith("❌").sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Filas comparativa", len(df))
    m2.metric("Match completo", n_ok)
    m3.metric("Con advertencia", n_warn,
              help="Registrado en Usuarios pero sin recolecciones hoy, o con litros pero la celda PROM del sheet vacía")
    m4.metric("Sin match", n_err,
              help="No registrado en Usuarios (falta ingresarlo en AppSheet, o el nombre del sheet está escrito distinto), o con recolecciones pero ausente del sheet")

    cols_mostrar = [c for c in ["Match", "Celda sheet", "Chofer", "Ruta", "Prom", "LitrosHoy", "Pct"] if c in df.columns]
    st.dataframe(
        df[cols_mostrar].sort_values("Match"),
        width='stretch', hide_index=True,
    )

    with st.expander("Mapa de zonas (prefijo de Tripulación → Zona)"):
        df_zonas = pd.DataFrame(ZONA_MAP, columns=["Prefijo detectado", "Zona asignada"])
        zonas_activas = set()
        if not df_regiones.empty and "Zona" in df_regiones.columns:
            zonas_activas = set(df_regiones["Zona"].dropna().unique())
        df_zonas["Activa hoy"] = df_zonas["Zona asignada"].apply(
            lambda z: "Sí" if z in zonas_activas else "No"
        )
        st.dataframe(df_zonas, width='stretch', hide_index=True)
        sin_zona = (
            df_regiones[df_regiones["Zona"].isna()] if not df_regiones.empty and "Zona" in df_regiones.columns
            else pd.DataFrame()
        )
        if not sin_zona.empty:
            st.warning(f"⚠️ {len(sin_zona)} fila(s) del sheet Regiones sin zona asignada (prefijo no reconocido).")


def mostrar_parametros(
    df_rec: pd.DataFrame,
    df_sheets: pd.DataFrame,
    df_regiones: pd.DataFrame,
    choferes_stgo: set,
    choferes_reg: set,
    data_comp_reg: pd.DataFrame | None = None,
):
    st.subheader("Diagnóstico de cruces con Google Sheets")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas sheet Santiago hoy", len(df_sheets))
    c2.metric("Filas sheet Regiones hoy", len(df_regiones))
    c3.metric("Choferes Santiago", len(choferes_stgo),
              help="Conducen un vehículo cuya patente está en el sheet Santiago")
    c4.metric("Choferes Regiones", len(choferes_reg),
              help="Todos los demás choferes con vehículo asignado en Usuarios")

    st.divider()
    _match_santiago(df_rec, df_sheets, choferes_stgo)

    st.divider()
    _match_regiones(data_comp_reg, df_regiones)

    st.divider()

    with st.expander("Columnas leídas de los sheets"):
        col_sh1, col_sh2 = st.columns(2)
        with col_sh1:
            st.markdown("**Sheet Santiago**")
            st.caption(f"Rango: A:Z  ·  Sheet: `{st.secrets.get('sheets', {}).get('sheet_name', '—')}`")
            st.caption(f"Palabras clave: `{', '.join(COLUMNAS_INTERES)}`")
            if not df_sheets.empty:
                cols_e = [c for c in df_sheets.columns if c != "_FilaSheet"]
                st.dataframe(
                    pd.DataFrame({
                        "Columna": cols_e,
                        "Con dato": [int(df_sheets[c].notna().sum()) for c in cols_e],
                        "Nulos":    [int(df_sheets[c].isna().sum()) for c in cols_e],
                    }),
                    width='stretch', hide_index=True,
                )
            else:
                st.caption("Sin datos hoy")
        with col_sh2:
            st.markdown("**Sheet Regiones**")
            st.caption(f"Rango: A:I  ·  Sheet: `{st.secrets.get('sheets', {}).get('sheet_name_regiones', '—')}`")
            if not df_regiones.empty:
                cols_r = [c for c in df_regiones.columns if c != "_FilaSheet"]
                st.dataframe(
                    pd.DataFrame({
                        "Columna": cols_r,
                        "Con dato": [int(df_regiones[c].notna().sum()) for c in cols_r],
                        "Nulos":    [int(df_regiones[c].isna().sum()) for c in cols_r],
                    }),
                    width='stretch', hide_index=True,
                )
            else:
                st.caption("Sin datos hoy")

    with st.expander("Constantes del sistema (config.py)"):
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            _widget_semaforo(
                "Cards choferes / Centros de acopio / Recolecciones",
                verde=UMBRAL_VERDE,
                amarillo=UMBRAL_AMARILLO,
                descripcion="Aplica a: % locales realizados, % litros relativo al grupo, % prioridad alta",
            )
        with col_s2:
            _widget_semaforo(
                "Tabla comparativa — Litros vs Esperado",
                verde=UMBRAL_COMP_VERDE,
                amarillo=UMBRAL_COMP_AMARILLO,
                descripcion="Aplica a: columna % en tabla de resumen por chofer (vs promedio 3M)",
            )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Productos excluidos del total",
            len(EXCLUIR_LITROS),
            delta=", ".join(sorted(EXCLUIR_LITROS)),
            delta_color="off",
        )
        c2.metric(
            "Ciclo de datos (seg)",
            TTL_DATOS_SEG,
            delta=f"rerun cada {RERUN_SEG}s",
            delta_color="off",
            help="Los datos vencen cada TTL_DATOS_SEG; la página hace rerun cada "
                 "RERUN_SEG para recargarlos apenas venzan (sin consultar antes las bases)",
        )
        c3.metric("Auto-avance Carrusel (seg)", INTERVALO_CARRUSEL_SEG)
        c4.metric("Auto-avance Carrusel Zonas (seg)", INTERVALO_ZONAS_SEG)

    with st.expander("Configuración activa (conexiones)"):
        s = st.secrets
        filas_cfg = [
            ("Sheet ID",        str(s.get("sheets", {}).get("spreadsheet_id", "—"))),
            ("Sheet Santiago",  str(s.get("sheets", {}).get("sheet_name", "—"))),
            ("Sheet Regiones",  str(s.get("sheets", {}).get("sheet_name_regiones", "—"))),
            ("Postgres host",   str(s.get("postgres", {}).get("host", "—"))),
            ("Postgres DB",     str(s.get("postgres", {}).get("database", "—"))),
            ("MySQL host",      str(s.get("mysql", {}).get("host", "—"))),
            ("MySQL DB",        str(s.get("mysql", {}).get("database", "—"))),
        ]
        st.dataframe(
            pd.DataFrame(filas_cfg, columns=["Parámetro", "Valor"]),
            width='stretch', hide_index=True,
        )
