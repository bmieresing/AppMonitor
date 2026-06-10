import streamlit as st
import pandas as pd
from connectors.mysql import cargar_usuarios_vehiculos
from connectors.postgres import cargar_empleados, cargar_vehiculos
from connectors.sheets import COLUMNAS_INTERES, ZONA_MAP


# ── Parámetros centralizados del sistema ─────────────────────────────────────
UMBRAL_VERDE  = 80   # % ≥ este valor → verde
UMBRAL_AMARILLO = 50  # % ≥ este valor → amarillo  /  < UMBRAL_VERDE
# < UMBRAL_AMARILLO → rojo

UMBRAL_COMP_VERDE   = 100  # % vs esperado: ≥ verde (tabla comparativa)
UMBRAL_COMP_AMARILLO = 70  # % vs esperado: ≥ amarillo

EXCLUIR_LITROS = ["Latas", "Desengrasante"]

INTERVALO_CARRUSEL_SEG  = 10
INTERVALO_ZONAS_SEG     = 20


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


def mostrar_parametros(
    df_rec: pd.DataFrame,
    df_sheets: pd.DataFrame,
    df_regiones: pd.DataFrame,
    choferes_stgo: set,
    choferes_reg: set,
):
    st.subheader("Semáforos del sistema")

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

    st.divider()

    st.subheader("Parámetros operacionales")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Productos excluidos del total",
        len(EXCLUIR_LITROS),
        delta=", ".join(EXCLUIR_LITROS),
        delta_color="off",
    )
    c2.metric(
        "Refresh página (seg)",
        int(st.secrets.get("refresh_interval_seconds", 300)),
    )
    c3.metric("Auto-avance Carrusel (seg)", INTERVALO_CARRUSEL_SEG)
    c4.metric("Auto-avance Carrusel Zonas (seg)", INTERVALO_ZONAS_SEG)

    st.divider()

    st.subheader("Mapa de zonas — Regiones")
    st.caption("Prefijos detectados al inicio de la columna Tripulación para asignar zona.")
    df_zonas = pd.DataFrame(ZONA_MAP, columns=["Prefijo detectado", "Zona asignada"])
    zonas_activas = set()
    if not df_regiones.empty and "Zona" in df_regiones.columns:
        zonas_activas = set(df_regiones["Zona"].dropna().unique())
    df_zonas["Activa hoy"] = df_zonas["Zona asignada"].apply(
        lambda z: "Sí" if z in zonas_activas else "No"
    )
    st.dataframe(df_zonas, width='stretch', hide_index=True)

    st.divider()

    st.subheader("Columnas leídas de los sheets")
    col_sh1, col_sh2 = st.columns(2)

    with col_sh1:
        st.markdown("**Sheet Santiago**")
        st.caption(f"Rango: A:Z  ·  Sheet: `{st.secrets.get('sheets', {}).get('sheet_name', '—')}`")
        st.caption(f"Palabras clave: `{', '.join(COLUMNAS_INTERES)}`")
        if not df_sheets.empty:
            cols_e = df_sheets.columns.tolist()
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
        st.caption(f"Rango: A:F  ·  Sheet: `{st.secrets.get('sheets', {}).get('sheet_name_regiones', '—')}`")
        if not df_regiones.empty:
            cols_r = df_regiones.columns.tolist()
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

    with st.expander("Diagnóstico cadena Patente → Vehículo → Chofer (Santiago)"):
        usuarios    = cargar_usuarios_vehiculos()
        vehiculos_pg = cargar_vehiculos()
        empleados_pg = cargar_empleados()

        col_patente = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
        col_prom    = next((c for c in df_sheets.columns if "PROM" in c.upper()), None)

        if col_patente and not df_sheets.empty:
            mapa_placa_a_id  = vehiculos_pg.set_index("plate")["id"].to_dict() if not vehiculos_pg.empty else {}
            mapa_veh_a_chofer = usuarios.set_index("Vehiculo")["Chofer"].to_dict() if not usuarios.empty else {}
            mapa_chofer_nombre = empleados_pg.set_index("id")["nombre"].to_dict() if not empleados_pg.empty else {}
            litros_por_patente = {}
            if not df_rec.empty and "Patente_Real" in df_rec.columns:
                litros_por_patente = (
                    df_rec[df_rec["Litros"] > 0].groupby("Patente_Real")["Litros"].sum().to_dict()
                )

            filas = []
            for pat in sorted(df_sheets[col_patente].dropna().unique().tolist()):
                vid    = mapa_placa_a_id.get(pat)
                cid    = mapa_veh_a_chofer.get(vid) if vid is not None else None
                nombre = mapa_chofer_nombre.get(cid) if cid is not None else None
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
                    "Patente": pat,
                    "ID Vehículo": str(vid) if vid else "— sin match",
                    "ID Chofer":   str(cid) if cid else "— sin match",
                    "Nombre Chofer": nombre or "— sin match",
                    "PROM 3M":     f"{prom_val:,.0f}" if prom_val else "—",
                    "Litros hoy":  f"{litros:,.0f}" if litros else "0",
                })

            st.dataframe(pd.DataFrame(filas), width='stretch', hide_index=True)

            sin_v = sum(1 for r in filas if r["ID Vehículo"].startswith("—"))
            sin_c = sum(1 for r in filas if r["ID Chofer"].startswith("—"))
            sin_n = sum(1 for r in filas if r["Nombre Chofer"].startswith("—"))
            if sin_v or sin_c or sin_n:
                a1, a2, a3 = st.columns(3)
                a1.metric("Sin vehículo PG", sin_v)
                a2.metric("Sin chofer MySQL", sin_c)
                a3.metric("Sin nombre", sin_n)
        else:
            st.info("No hay datos del sheet Santiago para hoy.")

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
