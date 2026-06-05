import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from zoneinfo import ZoneInfo
from components.comparativa import _preparar_datos
from connectors.mysql import cargar_estado_locales
from connectors.postgres import cargar_empleados
from connectors.sheets import cargar_datos_regiones

TZ = ZoneInfo("America/Santiago")


def _css():
    st.markdown("""
    <style>
        section.main > div.block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }
        div[data-testid="stVerticalBlock"] > div {
            gap: 0.3rem !important;
        }
        hr { margin: 0.4rem 0 !important; }
        div[data-testid="stMetric"] label { font-size: 11px !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
            font-size: 11px !important;
            color: #444 !important;
        }
        div[data-testid="stMetricDelta"] svg {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)


def _header():
    ahora = datetime.now(TZ)
    st.markdown(f"""
    <div style="background:#1a472a;color:white;padding:8px 20px;border-radius:6px;
                margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:16px;font-weight:700;letter-spacing:1px">
            DASHBOARD OPERACIONAL &ndash; RECOLECCIÓN DE ACEITE
        </span>
        <div style="text-align:right;font-size:12px;line-height:1.6">
            Última actualización: {ahora.strftime('%d/%m/%Y %H:%M')}<br>
            <span style="background:#28a745;padding:2px 10px;border-radius:12px;font-weight:bold">
                ● EN VIVO
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _kpis(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame):
    litros_hoy = df_rec["Litros"].sum() if not df_rec.empty else 0
    n_choferes = df_rec["NombreChofer"].nunique() if "NombreChofer" in df_rec.columns else 0
    prom_por_ruta = litros_hoy / n_choferes if n_choferes > 0 else 0

    prom_stgo = data_comp["Prom"].sum() if not data_comp.empty else 0
    df_reg = cargar_datos_regiones()
    col_prom_reg = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
    prom_reg = df_reg[col_prom_reg].sum() if (not df_reg.empty and col_prom_reg) else 0
    prom_total = prom_stgo + prom_reg
    vs_pct = (litros_hoy / prom_total * 100) if prom_total > 0 else 0

    total_locales = len(df_locales)
    realizados = int((df_locales["Estado"] == "Realizado").sum()) if not df_locales.empty else 0
    pct_real = (realizados / total_locales * 100) if total_locales > 0 else 0

    if not df_locales.empty and "Prioridad" in df_locales.columns:
        df_alta = df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
        total_alta = len(df_alta)
        realizados_alta = int((df_alta["Estado"] == "Realizado").sum())
        pct_alta = (realizados_alta / total_alta * 100) if total_alta > 0 else 0
    else:
        total_alta = realizados_alta = pct_alta = 0

    if "FechaObservacion" in df_rec.columns and "NombreChofer" in df_rec.columns:
        cerradas = int(
            df_rec.groupby("NombreChofer")["FechaObservacion"]
            .apply(lambda x: x.notna().any())
            .sum()
        )
    else:
        cerradas = 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💧 LITROS RECOLECTADOS HOY", f"{litros_hoy:,.0f} L",
              delta=f"🚛 Promedio por chofer: {prom_por_ruta:,.0f} L",
              delta_color="off")
    c2.metric("📊 VS. ESPERADO (PROM. RUTA)", f"{vs_pct:.1f}%",
              delta=f"🎯 Esperado: {prom_total:,.0f} L",
              delta_color="off")
    c3.metric("🏪 LOCALES ASIGNADOS", str(total_locales),
              delta=f"✅ Realizados: {realizados} ({pct_real:.0f}%)",
              delta_color="off")
    c4.metric("⭐ PRIORIDAD ALTA", str(total_alta),
              delta=f"✅ Realizados: {realizados_alta} ({pct_alta:.0f}%)",
              delta_color="off")
    c5.metric("🚦 RUTAS CERRADAS EN LA APP", f"{cerradas} / {n_choferes}",
              delta=f"⏳ {n_choferes - cerradas} pendientes",
              delta_color="off")


def _bullet_chart(data: pd.DataFrame, col_y: str, col_pct: str, titulo: str, altura: int = 320, max_x: int | None = None) -> alt.Chart:
    orden = data.sort_values(col_pct, ascending=True)[col_y].tolist()
    dominio = max_x if max_x else min(125, data[col_pct].max() * 1.1 + 10)
    scale_x = alt.Scale(domain=[0, dominio])

    bg = (
        alt.Chart(data)
        .transform_calculate(base="100")
        .mark_bar(color="#a8d5a2", height=10)
        .encode(
            y=alt.Y(f"{col_y}:N", sort=orden, title=None,
                    axis=alt.Axis(labelFontSize=10)),
            x=alt.X("base:Q", scale=scale_x, title="% del esperado"),
        )
    )
    real = (
        alt.Chart(data)
        .mark_bar(color="#2d7a2d", height=6)
        .encode(
            y=alt.Y(f"{col_y}:N", sort=orden),
            x=alt.X(f"{col_pct}:Q", scale=scale_x),
        )
    )
    label = (
        alt.Chart(data)
        .mark_text(align="left", dx=4, fontSize=10, fontWeight="bold", color="#1a472a")
        .encode(
            y=alt.Y(f"{col_y}:N", sort=orden),
            x=alt.X(f"{col_pct}:Q"),
            text=alt.Text(f"{col_pct}:Q", format=".0f"),
        )
    )

    return (
        (bg + real + label)
        .properties(
            title=alt.TitleParams(titulo, fontSize=12, fontWeight="bold", anchor="start"),
            height=altura,
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )


def _grafico_litros(data_comp: pd.DataFrame):
    if data_comp.empty:
        st.info("Sin datos de litros vs esperado.")
        return

    orden = data_comp.sort_values("Prom", ascending=False)["Chofer"].tolist()
    max_x = max(data_comp["Prom"].max(), data_comp["LitrosHoy"].max()) * 1.12

    bg = (
        alt.Chart(data_comp)
        .mark_bar(color="#a8d5a2", height=16)
        .encode(
            y=alt.Y("Chofer:N", sort=orden, title=None, axis=alt.Axis(labelFontSize=11)),
            x=alt.X("Prom:Q", scale=alt.Scale(domain=[0, max_x]), title="Litros"),
        )
    )
    real = (
        alt.Chart(data_comp)
        .mark_bar(color="#2d7a2d", height=10)
        .encode(
            y=alt.Y("Chofer:N", sort=orden),
            x=alt.X("LitrosHoy:Q", scale=alt.Scale(domain=[0, max_x])),
        )
    )
    label = (
        alt.Chart(data_comp)
        .mark_text(align="left", dx=5, fontSize=11, fontWeight="bold", color="#1a472a")
        .encode(
            y=alt.Y("Chofer:N", sort=orden),
            x=alt.X("LitrosHoy:Q"),
            text=alt.Text("LitrosHoy:Q", format=",.0f"),
        )
    )

    chart = (
        (bg + real + label)
        .properties(
            title=alt.TitleParams(
                "LITROS QUE LLEVAN VS LO ESPERADO (PROMEDIO RUTA)",
                fontSize=12, fontWeight="bold", anchor="start"
            ),
            height=max(280, len(data_comp) * 32),
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )
    st.altair_chart(chart, width='stretch')


def _grafico_litros_simple(df_rec: pd.DataFrame, df_locales: pd.DataFrame):
    if df_locales.empty or "Chofer" not in df_locales.columns:
        st.info("Sin datos de litros.")
        return

    empleados = cargar_empleados()
    mapa = empleados.set_index("id")["nombre"] if not empleados.empty else pd.Series(dtype=str)

    df_base = pd.DataFrame({"Chofer": df_locales["Chofer"].unique()})
    df_base["NombreChofer"] = df_base["Chofer"].map(mapa).fillna(df_base["Chofer"].astype(str))

    if not df_rec.empty and "Chofer" in df_rec.columns:
        litros = df_rec.groupby("Chofer")["Litros"].sum().reset_index()
    else:
        litros = pd.DataFrame(columns=["Chofer", "Litros"])

    data = (
        df_base.merge(litros, on="Chofer", how="left")
        .fillna({"Litros": 0})
        .sort_values("Litros", ascending=True)
    )
    orden = data["NombreChofer"].tolist()
    max_x = max(data["Litros"].max() * 1.15, 1)

    bars = (
        alt.Chart(data)
        .mark_bar(color="#2d7a2d", height=10)
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden, title=None, axis=alt.Axis(labelFontSize=11)),
            x=alt.X("Litros:Q", scale=alt.Scale(domain=[0, max_x]), title="Litros"),
        )
    )
    label = (
        alt.Chart(data)
        .mark_text(align="left", dx=5, fontSize=11, fontWeight="bold", color="#1a472a")
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("Litros:Q"),
            text=alt.Text("Litros:Q", format=",.0f"),
        )
    )

    chart = (
        (bars + label)
        .properties(
            title=alt.TitleParams("LITROS RECOLECTADOS HOY", fontSize=12, fontWeight="bold", anchor="start"),
            height=max(280, len(data) * 32),
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )
    st.altair_chart(chart, width='stretch')


def _grafico_locales(df_locales: pd.DataFrame, key_prefix: str = ""):
    if df_locales.empty or "Chofer" not in df_locales.columns:
        st.info("Sin datos de locales.")
        return

    empleados = cargar_empleados()
    if not empleados.empty:
        mapa = empleados.set_index("id")["nombre"]
        df_locales["NombreChofer"] = df_locales["Chofer"].map(mapa).fillna(df_locales["Chofer"].astype(str))
    else:
        df_locales["NombreChofer"] = df_locales["Chofer"].astype(str)

    # Dropdown filtro de prioridad
    opciones = ["Todos"]
    if "Prioridad" in df_locales.columns:
        prioridades = sorted(df_locales["Prioridad"].dropna().unique().tolist())
        opciones += prioridades

    filtro = st.selectbox("Prioridad", opciones, key=f"{key_prefix}filtro_prioridad_locales")
    if filtro != "Todos":
        df_locales = df_locales[df_locales["Prioridad"] == filtro]

    por_chofer = (
        df_locales.groupby("NombreChofer")
        .agg(Total=("ID_Local", "count"),
             Realizados=("Estado", lambda x: (x == "Realizado").sum()))
        .reset_index()
        .sort_values("Total", ascending=False)
    )

    max_x = por_chofer["Total"].max() * 1.1
    orden = por_chofer["NombreChofer"].tolist()

    bg = (
        alt.Chart(por_chofer)
        .mark_bar(color="#a8d5a2", height=10)
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden, title=None,
                    axis=alt.Axis(labelFontSize=10)),
            x=alt.X("Total:Q", scale=alt.Scale(domain=[0, max_x]),
                    title="Locales"),
        )
    )
    real = (
        alt.Chart(por_chofer)
        .mark_bar(color="#2d7a2d", height=6)
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("Realizados:Q", scale=alt.Scale(domain=[0, max_x])),
        )
    )
    label = (
        alt.Chart(por_chofer)
        .mark_text(align="left", dx=4, fontSize=10, fontWeight="bold", color="#1a472a")
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("Total:Q"),
            text=alt.Text("Realizados:Q", format=".0f"),
        )
    )

    chart = (
        (bg + real + label)
        .properties(
            title=alt.TitleParams(
                f"LOCALES ASIGNADOS VS REALIZADOS — {filtro}",
                fontSize=12, fontWeight="bold", anchor="start"
            ),
            height=max(300, len(por_chofer) * 28),
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )
    st.altair_chart(chart, width='stretch')


def _peores(data_comp: pd.DataFrame):
    if data_comp.empty:
        st.info("Sin datos.")
        return

    peores = data_comp.sort_values("Pct").head(5)[["Chofer", "LitrosHoy", "Pct"]].copy()
    peores = peores.reset_index(drop=True)
    peores["VS"] = (peores["Pct"] - 100).round(1)

    filas = []
    for i, row in peores.iterrows():
        ancho = min(abs(row["VS"]), 100)
        barra = f"""
        <div style="display:flex;align-items:center;gap:6px">
            <div style="background:#5a1010;height:14px;width:{ancho:.0f}px;border-radius:2px;min-width:4px"></div>
            <span style="color:#721c24;font-weight:bold;font-size:12px">{row['VS']:+.0f}%</span>
        </div>"""
        filas.append(f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:8px 6px;font-weight:bold;color:#888">{i+1}</td>
            <td style="padding:8px 6px;font-weight:600">{row['Chofer']}</td>
            <td style="padding:8px 6px">{row['LitrosHoy']:,.0f} L</td>
            <td style="padding:8px 6px">{barra}</td>
        </tr>""")

    html = f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead>
            <tr style="background:#f8f9fa;font-size:11px;color:#666;text-transform:uppercase">
                <th style="padding:8px 6px;text-align:left;width:20px">#</th>
                <th style="padding:8px 6px;text-align:left">Chofer</th>
                <th style="padding:8px 6px;text-align:left;white-space:nowrap">Litros hoy</th>
                <th style="padding:8px 6px;text-align:left">VS Esperado</th>
            </tr>
        </thead>
        <tbody>{''.join(filas)}</tbody>
    </table>"""
    st.html(html)


def _desempeno_centros(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame):
    # % Litros por Zona desde Control Regiones
    df_reg = cargar_datos_regiones()
    prom_zona: dict = {}
    if not df_reg.empty and "Zona" in df_reg.columns:
        col_prom = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
        if col_prom:
            for zona, grp in df_reg[df_reg["Zona"].notna()].groupby("Zona"):
                prom_zona[zona] = grp[col_prom].sum()

    # Litros actuales por CentroAcopio desde df_rec vía df_locales
    litros_zona: dict = {}
    if not df_rec.empty and not df_locales.empty and "CentroAcopio" in df_locales.columns and "Chofer" in df_locales.columns:
        chofer_centro = df_locales.drop_duplicates("Chofer").set_index("Chofer")["CentroAcopio"]
        df_tmp = df_rec.copy()
        df_tmp["CentroAcopio"] = df_tmp["Chofer"].map(chofer_centro)
        litros_zona = df_tmp.groupby("CentroAcopio")["Litros"].sum().to_dict()

    # % Locales por CentroAcopio (= Zona)
    local_stats = pd.DataFrame()
    if not df_locales.empty and "CentroAcopio" in df_locales.columns:
        local_stats = (
            df_locales.groupby("CentroAcopio")
            .agg(Total=("ID_Local", "count"),
                 Realizados=("Estado", lambda x: (x == "Realizado").sum()))
            .reset_index()
        )
        local_stats["PctLocales"] = (local_stats["Realizados"] / local_stats["Total"] * 100).round(0)

    centros = sorted(set(list(prom_zona.keys()) + (local_stats["CentroAcopio"].tolist() if not local_stats.empty else [])))
    centros = [c for c in centros if c and str(c) != "nan"]
    if not centros:
        return

    cols_por_fila = 3
    for i in range(0, len(centros), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, centro in enumerate(centros[i:i + cols_por_fila]):
            litros = litros_zona.get(centro, 0)
            prom = prom_zona.get(centro, 0)
            pct_litros = int(litros / prom * 100) if prom > 0 else 0

            fila_loc = local_stats[local_stats["CentroAcopio"] == centro] if not local_stats.empty else pd.DataFrame()
            realizados_loc = int(fila_loc["Realizados"].iloc[0]) if not fila_loc.empty else 0
            total_loc = int(fila_loc["Total"].iloc[0]) if not fila_loc.empty else 0

            cols[j].markdown(f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:7px 8px;text-align:center">
                <div style="font-weight:700;font-size:11px;margin-bottom:5px;color:#333;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
                     title="{centro}">{centro}</div>
                <div style="display:flex;justify-content:center;gap:10px">
                    <div>
                        <div style="font-size:15px;font-weight:800;color:#1a472a">{int(litros):,} / {int(prom):,}</div>
                        <div style="font-size:9px;color:#888">Litros</div>
                    </div>
                    <div style="border-left:1px solid #eee"></div>
                    <div>
                        <div style="font-size:15px;font-weight:800;color:#1a472a">{realizados_loc} / {total_loc}</div>
                        <div style="font-size:9px;color:#888">Locales</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def mostrar_dashboard(df_sheets: pd.DataFrame, df_rec: pd.DataFrame, choferes_filter: set, key_prefix: str = "", mostrar_centros: bool = True, mostrar_litros: bool = True, mostrar_peores: bool = True, mostrar_litros_simple: bool = False):
    data_comp = pd.DataFrame()
    if not df_sheets.empty and not df_rec.empty:
        result = _preparar_datos(df_sheets, df_rec)
        data_comp = result if result is not None else pd.DataFrame()

    df_locales = cargar_estado_locales()
    df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]

    _css()
    _header()
    _kpis(df_rec, data_comp, df_locales)
    st.divider()

    # Fila 2: dos gráficos con scroll
    if mostrar_litros:
        c_lit, c_loc = st.columns(2)
        altura_locales = max(300, len(data_comp) * 26 + 60) if not data_comp.empty else 300
        with c_lit:
            _grafico_litros(data_comp)
        with c_loc:
            with st.container(height=altura_locales):
                _grafico_locales(df_locales, key_prefix=key_prefix)
    elif mostrar_centros:
        if mostrar_litros_simple:
            _grafico_litros_simple(df_rec, df_locales)
        c_loc, c_centros = st.columns(2)
        with c_loc:
            with st.container(height=400):
                _grafico_locales(df_locales, key_prefix=key_prefix)
        with c_centros:
            _desempeno_centros(df_rec, pd.DataFrame(), df_locales)
    else:
        if mostrar_litros_simple:
            _grafico_litros_simple(df_rec, df_locales)
        with st.container(height=400):
            _grafico_locales(df_locales, key_prefix=key_prefix)

    st.divider()

    # Fila 3
    if mostrar_centros and mostrar_peores and mostrar_litros:
        c_peores, c_centros = st.columns([2, 3])
        with c_peores:
            st.markdown("**🔴 5 PEORES CHOFERES**")
            _peores(data_comp)
        with c_centros:
            _desempeno_centros(df_rec, pd.DataFrame(), df_locales)
    elif mostrar_centros and mostrar_litros:
        _desempeno_centros(df_rec, pd.DataFrame(), df_locales)
    elif mostrar_peores:
        st.markdown("**🔴 5 PEORES CHOFERES**")
        _peores(data_comp)
