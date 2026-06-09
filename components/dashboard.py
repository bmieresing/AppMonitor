import urllib.parse
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

# Productos que no se suman en litros totales (se pesan/cuentan diferente)
_EXCLUIR_LITROS = {"Latas", "Desengrasante"}


def _litros(df: pd.DataFrame) -> pd.DataFrame:
    """df_rec filtrado: excluye productos que no cuentan como litros de aceite."""
    if "Producto" not in df.columns or df.empty:
        return df
    return df[~df["Producto"].isin(_EXCLUIR_LITROS)]


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


def _header(tab_nombre: str = ""):
    ahora = datetime.now(TZ)
    badge = (f'<span style="background:rgba(255,255,255,0.18);padding:3px 14px;'
             f'border-radius:12px;font-size:18px;font-weight:700;letter-spacing:2px;'
             f'margin-left:16px">{tab_nombre.upper()}</span>') if tab_nombre else ""
    st.markdown(f"""
    <div style="background:#1a472a;color:white;padding:8px 20px;border-radius:6px;
                margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:16px;font-weight:700;letter-spacing:1px">
            DASHBOARD OPERACIONAL &ndash; RECOLECCIÓN DE ACEITE{badge}
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
    df_rec = _litros(df_rec)
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


def _grafico_litros_simple(df_rec: pd.DataFrame, df_locales: pd.DataFrame, vertical: bool = False):
    if df_locales.empty or "Chofer" not in df_locales.columns:
        st.info("Sin datos de litros.")
        return

    empleados = cargar_empleados()
    mapa = empleados.set_index("id")["nombre"] if not empleados.empty else pd.Series(dtype=str)

    df_base = pd.DataFrame({"Chofer": df_locales["Chofer"].unique()})
    df_base["NombreChofer"] = df_base["Chofer"].map(mapa).fillna(df_base["Chofer"].astype(str))

    if not df_rec.empty and "Chofer" in df_rec.columns:
        litros = _litros(df_rec).groupby("Chofer")["Litros"].sum().reset_index()
    else:
        litros = pd.DataFrame(columns=["Chofer", "Litros"])

    data = (
        df_base.merge(litros, on="Chofer", how="left")
        .fillna({"Litros": 0})
        .sort_values("Litros", ascending=False)
    )
    orden = data["NombreChofer"].tolist()

    def _chart_litros_mitad(choferes: list, titulo: str) -> alt.Chart:
        df_m = data[data["NombreChofer"].isin(choferes)]
        max_x = max(df_m["Litros"].max() * 1.15, 1)
        bars = (
            alt.Chart(df_m).mark_bar(color="#2d7a2d", height=10)
            .encode(
                y=alt.Y("NombreChofer:N", sort=choferes, title=None,
                        axis=alt.Axis(labelFontSize=10, labelOverlap=False)),
                x=alt.X("Litros:Q", scale=alt.Scale(domain=[0, max_x]), title="Litros"),
            )
        )
        lbl = (
            alt.Chart(df_m).mark_text(align="left", dx=5, fontSize=10,
                                      fontWeight="bold", color="#1a472a")
            .encode(
                y=alt.Y("NombreChofer:N", sort=choferes),
                x=alt.X("Litros:Q"),
                text=alt.Text("Litros:Q", format=",.0f"),
            )
        )
        return (
            (bars + lbl)
            .properties(
                title=alt.TitleParams(titulo, fontSize=12, fontWeight="bold", anchor="start"),
                height=len(choferes) * 28,
            )
            .configure_view(strokeWidth=0)
            .configure_axis(grid=False)
        )

    if vertical:
        mitad = len(orden) // 2 + len(orden) % 2
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(_chart_litros_mitad(orden[:mitad], "LITROS RECOLECTADOS HOY (1/2)"), width='stretch')
        with c2:
            st.altair_chart(_chart_litros_mitad(orden[mitad:], "LITROS RECOLECTADOS HOY (2/2)"), width='stretch')
    else:
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


def _grafico_locales(df_locales: pd.DataFrame, key_prefix: str = "", vertical: bool = False):
    if df_locales.empty or "Chofer" not in df_locales.columns:
        st.info("Sin datos de locales.")
        return

    df_locales = df_locales.copy()
    empleados = cargar_empleados()
    if not empleados.empty:
        mapa = empleados.set_index("id")["nombre"]
        df_locales["NombreChofer"] = df_locales["Chofer"].map(mapa).fillna(df_locales["Chofer"].astype(str))
    else:
        df_locales["NombreChofer"] = df_locales["Chofer"].astype(str)

    df_locales["Prio"] = (
        df_locales["Prioridad"].apply(lambda x: "Alta" if str(x).upper().startswith("ALTA") else "Normal")
        if "Prioridad" in df_locales.columns else "Normal"
    )

    por_chofer = (
        df_locales.groupby(["NombreChofer", "Prio"])
        .agg(Total=("ID_Local", "count"),
             Realizados=("Estado", lambda x: (x == "Realizado").sum()))
        .reset_index()
    )

    orden = (
        por_chofer.groupby("NombreChofer")["Total"].sum()
        .sort_values(ascending=False).index.tolist()
    )

    escala_col_bg   = alt.Scale(domain=["Alta", "Normal"], range=["#d5d5d5", "#d5d5d5"])
    escala_col_real = alt.Scale(domain=["Alta", "Normal"], range=["#c0392b", "#2d7a2d"])
    leyenda = alt.Legend(title="Prioridad", orient="top", labelFontSize=11, symbolSize=80)

    def _chart_mitad(choferes: list, titulo: str) -> alt.Chart:
        df_m = por_chofer[por_chofer["NombreChofer"].isin(choferes)]
        max_x = max(df_m["Total"].max() * 1.15, 1)
        bg = (
            alt.Chart(df_m).mark_bar(height=9)
            .encode(
                y=alt.Y("NombreChofer:N", sort=choferes, title=None,
                        axis=alt.Axis(labelFontSize=10, labelOverlap=False)),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Total:Q", scale=alt.Scale(domain=[0, max_x]), title="Locales"),
                color=alt.Color("Prio:N", scale=escala_col_bg, legend=None),
            )
        )
        real = (
            alt.Chart(df_m).mark_bar(height=5)
            .encode(
                y=alt.Y("NombreChofer:N", sort=choferes),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Realizados:Q", scale=alt.Scale(domain=[0, max_x])),
                color=alt.Color("Prio:N", scale=escala_col_real, legend=leyenda),
            )
        )
        lbl = (
            alt.Chart(df_m).mark_text(align="left", dx=4, fontSize=9, fontWeight="bold")
            .encode(
                y=alt.Y("NombreChofer:N", sort=choferes),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Total:Q"),
                text=alt.Text("Realizados:Q", format=".0f"),
                color=alt.Color("Prio:N", scale=escala_col_real, legend=None),
            )
        )
        return (
            (bg + real + lbl)
            .properties(
                title=alt.TitleParams(titulo, fontSize=11, fontWeight="bold", anchor="start"),
                height=len(choferes) * 42,
            )
            .configure_view(strokeWidth=0)
            .configure_axis(grid=False)
        )

    if vertical:
        mitad = len(orden) // 2 + len(orden) % 2
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(_chart_mitad(orden[:mitad], "LOCALES — ALTA / NORMAL (1/2)"), width='stretch')
        with c2:
            st.altair_chart(_chart_mitad(orden[mitad:], "LOCALES — ALTA / NORMAL (2/2)"), width='stretch')
    else:
        max_x = por_chofer["Total"].max() * 1.15
        bg = (
            alt.Chart(por_chofer)
            .mark_bar(height=9)
            .encode(
                y=alt.Y("NombreChofer:N", sort=orden, title=None,
                        axis=alt.Axis(labelFontSize=10)),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Total:Q", scale=alt.Scale(domain=[0, max_x]), title="Locales"),
                color=alt.Color("Prio:N", scale=escala_col_bg, legend=None),
            )
        )
        real = (
            alt.Chart(por_chofer)
            .mark_bar(height=5)
            .encode(
                y=alt.Y("NombreChofer:N", sort=orden),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Realizados:Q", scale=alt.Scale(domain=[0, max_x])),
                color=alt.Color("Prio:N", scale=escala_col_real, legend=leyenda),
            )
        )
        label = (
            alt.Chart(por_chofer)
            .mark_text(align="left", dx=4, fontSize=9, fontWeight="bold")
            .encode(
                y=alt.Y("NombreChofer:N", sort=orden),
                yOffset=alt.YOffset("Prio:N", sort=["Alta", "Normal"]),
                x=alt.X("Total:Q"),
                text=alt.Text("Realizados:Q", format=".0f"),
                color=alt.Color("Prio:N", scale=escala_col_real, legend=None),
            )
        )
        chart = (
            (bg + real + label)
            .properties(
                title=alt.TitleParams(
                    "LOCALES ASIGNADOS VS REALIZADOS — ALTA / NORMAL",
                    fontSize=12, fontWeight="bold", anchor="start"
                ),
                height=max(300, len(orden) * 44),
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


def _preparar_datos_regiones(df_reg: pd.DataFrame, df_rec: pd.DataFrame) -> pd.DataFrame:
    """data_comp para Regiones: une nombre chofer del sheet con litros reales del día."""
    col_chofer = next((c for c in df_reg.columns if "CHOFER" in c.upper()), None)
    col_prom = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
    if not col_chofer or df_reg.empty:
        return pd.DataFrame()

    prom_s = df_reg[[col_chofer]].copy()
    prom_s.columns = ["Chofer"]
    # cargar_datos_regiones ya convierte col_prom a numérico
    prom_s["Prom"] = df_reg[col_prom].fillna(0) if col_prom else 0.0
    prom_s = prom_s[prom_s["Chofer"].notna()].copy()
    prom_s["_key"] = prom_s["Chofer"].str.strip().str.lower()

    if not df_rec.empty and "NombreChofer" in df_rec.columns:
        lit_s = (
            _litros(df_rec)
            .groupby("NombreChofer")["Litros"]
            .sum()
            .reset_index()
            .rename(columns={"NombreChofer": "Chofer_rec", "Litros": "LitrosHoy"})
        )
        lit_s["_key"] = lit_s["Chofer_rec"].str.strip().str.lower()
        # outer: incluye choferes del sheet sin litros aún y choferes con litros no en el sheet
        result = prom_s.merge(lit_s[["_key", "LitrosHoy"]], on="_key", how="outer")
        name_by_key = lit_s.set_index("_key")["Chofer_rec"].to_dict()
        mask = result["Chofer"].isna()
        result.loc[mask, "Chofer"] = result.loc[mask, "_key"].map(name_by_key)
    else:
        result = prom_s.copy()
        result["LitrosHoy"] = 0.0

    result = result.drop(columns=["_key"]).copy()
    result["LitrosHoy"] = result["LitrosHoy"].fillna(0)
    result["Prom"] = result["Prom"].fillna(0)
    result["Pct"] = (result["LitrosHoy"] / result["Prom"] * 100).where(result["Prom"] > 0, 0).round(1)
    return result.sort_values("LitrosHoy", ascending=False).reset_index(drop=True)


def _grid_choferes(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame | None = None, tab_nombre: str = "", key_prefix: str = ""):
    empleados = cargar_empleados()
    # Índice en str para evitar mismatch de tipo int entre MySQL y PostgreSQL
    mapa = (
        empleados.set_index(empleados["id"].astype(str))["nombre"]
        if not empleados.empty else pd.Series(dtype=str)
    )

    # Litros por chofer — si hay data_comp (Santiago) usamos LitrosHoy/Prom, si no relativo al máximo
    if data_comp is not None and not data_comp.empty and "LitrosHoy" in data_comp.columns:
        litros_ch = data_comp.set_index("Chofer")["LitrosHoy"].to_dict()
        prom_ch   = data_comp.set_index("Chofer")["Prom"].to_dict()
        usar_prom = True
    else:
        df_lit = _litros(df_rec).copy() if not df_rec.empty else pd.DataFrame()
        if not df_lit.empty and "Chofer" in df_lit.columns:
            if "NombreChofer" not in df_lit.columns:
                df_lit["NombreChofer"] = df_lit["Chofer"].astype(str).map(mapa).fillna(df_lit["Chofer"].astype(str))
            litros_ch = df_lit.groupby("NombreChofer")["Litros"].sum().to_dict()
        else:
            litros_ch = {}
        prom_ch   = {}
        usar_prom = False

    max_litros = max(litros_ch.values(), default=1)

    # pct vs esperado; 0 si no hay prom definido
    pct_ch: dict[str, int] = {}
    for _n, _l in litros_ch.items():
        _p = prom_ch.get(_n, 0) if usar_prom else 0
        pct_ch[_n] = int(_l / _p * 100) if _p > 0 else 0

    # Locales por chofer: total y alta por separado
    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    # locales_ch[nombre] = {"total": (r, t), "alta": (r, t)}
    locales_ch: dict[str, dict] = {}
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = df_loc["Chofer"].astype(str).map(mapa).fillna(df_loc["Chofer"].astype(str))
        if "Prioridad" in df_loc.columns:
            df_loc["EsAlta"] = df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
        else:
            df_loc["EsAlta"] = False
        for nombre, grp in df_loc.groupby("NombreChofer"):
            realiz_total = int((grp["Estado"] == "Realizado").sum())
            grp_alta = grp[grp["EsAlta"]]
            realiz_alta = int((grp_alta["Estado"] == "Realizado").sum())
            locales_ch[nombre] = {
                "total": (realiz_total, len(grp)),
                "alta":  (realiz_alta, len(grp_alta)),
            }

    # Choferes que cerraron ruta (tienen FechaObservacion)
    cerrados: set[str] = set()
    if not df_rec.empty and "FechaObservacion" in df_rec.columns and "NombreChofer" in df_rec.columns:
        cerrados = set(
            df_rec.groupby("NombreChofer")["FechaObservacion"]
            .apply(lambda x: x.notna().any())
            .pipe(lambda s: s[s].index.tolist())
        )

    choferes = sorted(
        set(list(litros_ch.keys()) + list(locales_ch.keys())),
        key=lambda n: pct_ch.get(n, 0), reverse=True,
    )
    if not choferes:
        return

    def _color(pct: int) -> str:
        if pct >= 80: return "#2d7a2d"
        if pct >= 50: return "#e67e22"
        return "#c0392b"

    def _barra(pct_fill: int, pct_label: int, sub: str, mostrar_pct: bool = True) -> str:
        color = _color(pct_label) if mostrar_pct else "#1565c0"
        w = min(pct_fill, 100)
        pct_span = f'<span style="font-weight:700;color:{color}">{pct_label}%</span>' if mostrar_pct else ""
        return (
            f'<div style="margin-bottom:2px">'
            f'<div style="display:flex;justify-content:space-between;font-size:7px;color:#666;margin-bottom:1px">'
            f'<span>{sub}</span>{pct_span}'
            f'</div>'
            f'<div style="height:4px;border-radius:2px;background:#e8e8e8;overflow:hidden">'
            f'<div style="height:100%;width:{w}%;background:{color};border-radius:2px"></div>'
            f'</div></div>'
        )

    cards = []
    for nombre in choferes:
        litros = litros_ch.get(nombre, 0)
        pct_lit = pct_ch.get(nombre, 0)
        barra_lit = _barra(min(pct_lit, 100), pct_lit, f"💧 {int(litros):,} L", mostrar_pct=True)

        barras_loc = ""
        if nombre in locales_ch:
            r_tot, t_tot = locales_ch[nombre]["total"]
            r_alt, t_alt = locales_ch[nombre]["alta"]
            pct_tot = int(r_tot / t_tot * 100) if t_tot > 0 else 0
            barras_loc = _barra(pct_tot, pct_tot, f"📋 {r_tot}/{t_tot}")
            if t_alt > 0:
                pct_alt = int(r_alt / t_alt * 100) if t_alt > 0 else 0
                barras_loc += _barra(pct_alt, pct_alt, f"⭐ {r_alt}/{t_alt}")

        cerrado = nombre in cerrados
        candado = (
            '<span style="font-size:9px;margin-left:3px;vertical-align:middle;flex-shrink:0;'
            'font-family:\'Apple Color Emoji\',\'Segoe UI Emoji\',\'Noto Color Emoji\',sans-serif">🔒</span>'
        ) if cerrado else ''
        bg = '#f0f4f0' if cerrado else '#f9fdf9'
        link = f'?nav_carrusel={urllib.parse.quote(nombre)}'
        cards.append(
            f'<div style="border:1px solid #c8e6c9;border-radius:5px;padding:5px 7px;'
            f'background:{bg};box-shadow:0 1px 3px rgba(0,0,0,0.04)">'
            f'<div style="display:flex;align-items:center;font-weight:700;font-size:9px;'
            f'color:#1a472a;margin-bottom:3px;overflow:hidden" title="{nombre}">'
            f'<a href="{link}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            f'text-decoration:none;color:#1a472a">{nombre}</a>'
            f'{candado}</div>'
            f'{barra_lit}{barras_loc}</div>'
        )

    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:6px;padding:2px 0">'
        f'{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _desempeno_centros(df_rec: pd.DataFrame, data_comp: pd.DataFrame, df_locales: pd.DataFrame):
    df_rec = _litros(df_rec)
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

    # Santiago: litros y esperado vienen de data_comp (usa Patente_Real del sheet), no del mapping por chofer
    if not data_comp.empty and "LitrosHoy" in data_comp.columns:
        stgo_litros = data_comp["LitrosHoy"].sum()
        stgo_prom = data_comp["Prom"].sum() if "Prom" in data_comp.columns else 0
        stgo_centros = set()
        if not df_locales.empty and "CentroAcopio" in df_locales.columns:
            stgo_centros = {c for c in df_locales["CentroAcopio"].dropna().unique()
                            if "santiago" in str(c).lower()}
        for c in stgo_centros | {k for k in prom_zona if "santiago" in str(k).lower()}:
            litros_zona[c] = stgo_litros
            if stgo_prom > 0:
                prom_zona[c] = stgo_prom

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

    def _color_pct(pct: int) -> tuple[str, str]:
        # (color sólido, color fill semitransparente)
        if pct >= 80:
            return "#2d7a2d", "rgba(45,122,45,0.22)"
        if pct >= 50:
            return "#e67e22", "rgba(230,126,34,0.22)"
        return "#c0392b", "rgba(192,57,43,0.22)"

    def _tanque(pct: int, emoji: str, label: str, sub: str) -> str:
        color, fill = _color_pct(pct)
        h = min(pct, 100)
        return f"""
        <div style="text-align:center;flex:1">
            <div style="position:relative;height:80px;border:2px solid {color};
                        border-radius:6px 6px 8px 8px;overflow:hidden;background:#fafafa;
                        margin:0 auto">
                <div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;
                            background:{fill}"></div>
                <div style="position:absolute;inset:0;display:flex;align-items:center;
                            justify-content:center;z-index:1">
                    <span style="font-size:20px;font-weight:900;color:{color};
                                 text-shadow:0 0 6px #fff,0 0 6px #fff,0 0 6px #fff">
                        {pct}%
                    </span>
                </div>
            </div>
            <div style="font-size:11px;font-weight:700;color:#444;margin-top:5px">
                {emoji} {label}
            </div>
            <div style="font-size:10px;color:#999;margin-top:1px">{sub}</div>
        </div>"""

    cols_por_fila = max(3, -(-len(centros) // 2))
    for i in range(0, len(centros), cols_por_fila):
        cols = st.columns(cols_por_fila)
        for j, centro in enumerate(centros[i:i + cols_por_fila]):
            litros = litros_zona.get(centro, 0)
            prom = prom_zona.get(centro, 0)
            pct_litros = min(int(litros / prom * 100) if prom > 0 else 0, 100)

            fila_loc = local_stats[local_stats["CentroAcopio"] == centro] if not local_stats.empty else pd.DataFrame()
            realizados_loc = int(fila_loc["Realizados"].iloc[0]) if not fila_loc.empty else 0
            total_loc = int(fila_loc["Total"].iloc[0]) if not fila_loc.empty else 0
            pct_loc = int(realizados_loc / total_loc * 100) if total_loc > 0 else 0

            tanque_litros = _tanque(pct_litros, "💧", "Litros", f"{int(litros):,} / {int(prom):,} L")
            tanque_locales = _tanque(pct_loc, "🏪", "Locales", f"{realizados_loc} / {total_loc}")

            cols[j].markdown(f"""
            <div style="border:1px solid #c8e6c9;border-radius:10px;padding:12px 12px 10px;
                        background:#f9fdf9;box-shadow:0 1px 6px rgba(0,0,0,0.05)">
                <div style="font-weight:700;font-size:12px;margin-bottom:10px;color:#1a472a;
                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                            border-bottom:1px solid #e0f0e0;padding-bottom:6px"
                     title="{centro}">{centro}</div>
                <div style="display:flex;gap:10px">
                    {tanque_litros}
                    {tanque_locales}
                </div>
            </div>
            """, unsafe_allow_html=True)


def _donuts_global(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame, tab_nombre: str = "Global"):
    # --- Rutas / Cerradas (antes del filtro _litros para no perder choferes) ---
    n_rutas = df_locales["Chofer"].nunique() if not df_locales.empty else 0
    if not df_rec.empty and "FechaObservacion" in df_rec.columns and "NombreChofer" in df_rec.columns:
        cerradas = int(
            df_rec.groupby("NombreChofer")["FechaObservacion"]
            .apply(lambda x: x.notna().any()).sum()
        )
    else:
        cerradas = 0
    pct_cerradas = round(cerradas / n_rutas * 100) if n_rutas > 0 else 0

    df_rec = _litros(df_rec)
    # --- Litros vs Esperado ---
    litros_hoy = df_rec["Litros"].sum() if not df_rec.empty else 0
    prom_stgo = data_comp["Prom"].sum() if not data_comp.empty else 0
    df_reg_data = cargar_datos_regiones()
    col_prom_reg = next((c for c in df_reg_data.columns if "PROM" in c.upper()), None)
    prom_reg = df_reg_data[col_prom_reg].sum() if (not df_reg_data.empty and col_prom_reg) else 0

    tab_up = tab_nombre.upper()
    if "SANTIAGO" in tab_up:
        prom_total = prom_stgo
    elif "REGION" in tab_up:
        prom_total = prom_reg
    else:
        prom_total = prom_stgo + prom_reg

    pct_lit = round(litros_hoy / prom_total * 100) if prom_total > 0 else 0

    # --- Locales ---
    total_loc = len(df_locales)
    realizados_loc = int((df_locales["Estado"] == "Realizado").sum()) if not df_locales.empty else 0
    pct_loc = round(realizados_loc / total_loc * 100) if total_loc > 0 else 0

    # --- Prioridad alta ---
    if not df_locales.empty and "Prioridad" in df_locales.columns:
        df_alta = df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
        total_alta = len(df_alta)
        real_alta = int((df_alta["Estado"] == "Realizado").sum())
        pct_alta = round(real_alta / total_alta * 100) if total_alta > 0 else 0
    else:
        total_alta = real_alta = pct_alta = 0

    # --- Exitosas/Fallidas ---
    exitosas = int((df_rec["Litros"] > 0).sum()) if not df_rec.empty and "Litros" in df_rec.columns else 0
    fallidas = int(df_rec["Razon"].notna().sum()) if not df_rec.empty and "Razon" in df_rec.columns else 0
    total_ef = exitosas + fallidas
    pct_exit = round(exitosas / total_ef * 100) if total_ef > 0 else 0

    compact = "REGION" in tab_up

    def _card(titulo: str, emoji: str, valor: str, pct: int,
              color_a: str, color_b: str, label_a: str, label_b: str) -> str:
        deg = round(pct * 3.6)
        if compact:
            emoji_px, donut_px, hole_px, pct_px, pad, val_px = 44, 86, 58, 16, "12px 14px 10px", "18px"
        else:
            emoji_px, donut_px, hole_px, pct_px, pad, val_px = 72, 130, 88, 22, "22px 20px 18px", "28px"
        return f"""
        <div style="background:#fff;border:1px solid #e0e8e0;border-radius:14px;
                    padding:{pad};box-shadow:0 2px 12px rgba(0,0,0,0.07);
                    text-align:center">
            <div style="display:flex;align-items:center;justify-content:center;
                        gap:12px;margin-bottom:10px">
                <span style="font-size:{emoji_px}px;line-height:1">{emoji}</span>
                <div style="position:relative;width:{donut_px}px;height:{donut_px}px;flex-shrink:0">
                    <div style="width:{donut_px}px;height:{donut_px}px;border-radius:50%;
                                background:conic-gradient({color_a} {deg}deg, {color_b} {deg}deg)">
                    </div>
                    <div style="position:absolute;inset:0;display:flex;align-items:center;
                                justify-content:center">
                        <div style="width:{hole_px}px;height:{hole_px}px;border-radius:50%;background:#fff;
                                    display:flex;align-items:center;justify-content:center">
                            <span style="font-size:{pct_px}px;font-weight:900;color:#1a472a">{pct}%</span>
                        </div>
                    </div>
                </div>
            </div>
            <div style="font-size:10px;font-weight:700;color:#999;text-transform:uppercase;
                        letter-spacing:1.5px;margin-bottom:6px">{titulo}</div>
            <div style="font-size:{val_px};font-weight:700;color:#1a472a;line-height:1.1;
                        margin-bottom:8px">{valor}</div>
            <div style="display:flex;gap:10px;justify-content:center;font-size:10px;color:#888">
                <span><span style="color:{color_a}">&#9679;</span> {label_a}</span>
                <span><span style="color:{color_b}">&#9679;</span> {label_b}</span>
            </div>
        </div>"""

    cards = "".join([
        _card("Litros vs Esperado", "💧",
              f"{litros_hoy:,.0f} / {prom_total:,.0f} L",
              pct_lit, "#2d7a2d", "#e0e0e0", "Recolectado", "Restante"),
        _card("Locales Realizados", "🏪",
              f"{realizados_loc:,} / {total_loc:,}",
              pct_loc, "#2d7a2d", "#e0e0e0", "Realizados", "Pendientes"),
        _card("Prioridad Alta", "⭐",
              f"{real_alta:,} / {total_alta:,}",
              pct_alta, "#2d7a2d", "#e0e0e0", "Realizados", "Pendientes"),
        _card("Recolecciones", "✅",
              f"{exitosas:,} / {fallidas:,}",
              pct_exit, "#28a745", "#dc3545", "Exitosas", "Fallidas"),
        _card("Rutas Cerradas", "🚦",
              f"{cerradas:,} / {n_rutas:,}",
              pct_cerradas, "#1a6b8a", "#e0e0e0", "Cerradas", "Abiertas"),
    ])
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;'
        f'padding:2px 0 6px">{cards}</div>',
        unsafe_allow_html=True,
    )


def mostrar_dashboard(df_sheets: pd.DataFrame, df_rec: pd.DataFrame, choferes_filter: set, key_prefix: str = "", mostrar_centros: bool = True, mostrar_litros: bool = True, mostrar_peores: bool = True, mostrar_litros_simple: bool = False, mostrar_donuts: bool = False, tab_nombre: str = ""):
    data_comp = pd.DataFrame()
    if not df_sheets.empty and not df_rec.empty:
        result = _preparar_datos(df_sheets, df_rec)
        data_comp = result if result is not None else pd.DataFrame()

    df_locales = cargar_estado_locales()
    df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]

    _css()
    _header(tab_nombre)
    if not mostrar_donuts:
        _kpis(df_rec, data_comp, df_locales)
        st.divider()

    vertical = "REGION" in tab_nombre.upper()

    # Fila 2
    if mostrar_donuts:
        _donuts_global(df_rec, df_locales, data_comp, tab_nombre=tab_nombre)
        st.divider()
        if mostrar_centros:
            _desempeno_centros(df_rec, data_comp, df_locales)
        elif mostrar_litros:
            if "SANTIAGO" in tab_nombre.upper():
                _grid_choferes(df_rec, df_locales, data_comp=data_comp if not data_comp.empty else None, tab_nombre=tab_nombre, key_prefix=key_prefix)
            else:
                c_lit, c_loc = st.columns(2)
                with c_lit:
                    _grafico_litros(data_comp)
                with c_loc:
                    _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)
        elif mostrar_litros_simple:
            if vertical:
                data_comp_reg = _preparar_datos_regiones(df_sheets, df_rec)
                _grid_choferes(df_rec, df_locales, data_comp=data_comp_reg if not data_comp_reg.empty else None, tab_nombre=tab_nombre, key_prefix=key_prefix)
            else:
                _grafico_litros_simple(df_rec, df_locales)
                _grafico_locales(df_locales, key_prefix=key_prefix)
        else:
            _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)
    elif mostrar_litros:
        c_lit, c_loc = st.columns(2)
        with c_lit:
            _grafico_litros(data_comp)
        with c_loc:
            _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)
    elif mostrar_centros:
        if mostrar_litros_simple:
            c_lit_simple, c_loc = st.columns(2)
            with c_lit_simple:
                _grafico_litros_simple(df_rec, df_locales, vertical=vertical)
            with c_loc:
                _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)
            _desempeno_centros(df_rec, pd.DataFrame(), df_locales)
        else:
            c_loc, c_centros = st.columns(2)
            with c_loc:
                _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)
            with c_centros:
                _desempeno_centros(df_rec, pd.DataFrame(), df_locales)
    else:
        if mostrar_litros_simple:
            _grafico_litros_simple(df_rec, df_locales, vertical=vertical)
        _grafico_locales(df_locales, key_prefix=key_prefix, vertical=vertical)

    if not mostrar_donuts:
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
