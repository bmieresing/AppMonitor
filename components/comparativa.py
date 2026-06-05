import streamlit as st
import pandas as pd
import altair as alt


def _preparar_datos(df_sheets: pd.DataFrame, df_mysql: pd.DataFrame) -> pd.DataFrame | None:
    col_prom = next((c for c in df_sheets.columns if "PROM" in c.upper()), None)
    col_patente = next((c for c in df_sheets.columns if "PATENTE" in c.upper()), None)
    if not col_prom or not col_patente:
        return None

    prom_df = df_sheets[[col_patente, col_prom]].copy()
    prom_df["Prom"] = pd.to_numeric(
        prom_df[col_prom].astype(str).str.replace(".", "").str.replace(",", "."),
        errors="coerce",
    )
    prom_df = prom_df[[col_patente, "Prom"]].rename(columns={col_patente: "Patente"})
    prom_df = prom_df[prom_df["Prom"] > 0]

    chofer_por_patente = (
        df_mysql[["Patente_Real", "NombreChofer"]]
        .dropna(subset=["Patente_Real"])
        .drop_duplicates("Patente_Real")
        .rename(columns={"Patente_Real": "Patente"})
    )
    litros_por_patente = (
        df_mysql[df_mysql["Litros"] > 0]
        .groupby("Patente_Real")["Litros"]
        .sum()
        .reset_index()
        .rename(columns={"Patente_Real": "Patente", "Litros": "LitrosHoy"})
    )

    data = (
        prom_df
        .merge(chofer_por_patente, on="Patente", how="left")
        .merge(litros_por_patente, on="Patente", how="left")
    )
    data["LitrosHoy"] = data["LitrosHoy"].fillna(0)
    data["Chofer"] = data["NombreChofer"].fillna(data["Patente"])
    data["Pct"] = (data["LitrosHoy"] / data["Prom"] * 100).round(1)
    data["SobreMeta"] = data["LitrosHoy"] >= data["Prom"]
    return data.sort_values("Pct", ascending=False)


def _kpis(data: pd.DataFrame):
    total_hoy = data["LitrosHoy"].sum()
    total_meta = data["Prom"].sum()
    pct_global = (total_hoy / total_meta * 100) if total_meta > 0 else 0
    sobre = int(data["SobreMeta"].sum())
    bajo = int((~data["SobreMeta"]).sum())
    sin_datos = int((data["LitrosHoy"] == 0).sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Litros hoy", f"{total_hoy:,.0f} L", delta=f"{total_hoy - total_meta:+,.0f} vs meta")
    c2.metric("Meta total", f"{total_meta:,.0f} L")
    c3.metric("% global", f"{pct_global:.1f}%", delta=f"{pct_global - 100:.1f}pp")
    c4.metric("Sobre meta", f"{sobre} rutas", delta=f"{bajo} bajo" if bajo else "todas cumplen")
    c5.metric("Sin recolectar", f"{sin_datos} rutas")


def _grafico(data: pd.DataFrame):
    barras = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Chofer:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30, labelFontSize=12)),
            y=alt.Y("LitrosHoy:Q", title="Litros hoy", axis=alt.Axis(grid=True, gridOpacity=0.3)),
            color=alt.condition(
                alt.datum.SobreMeta,
                alt.value("#28a745"),
                alt.value("#dc3545"),
            ),
            tooltip=[
                alt.Tooltip("Chofer:N", title="Chofer"),
                alt.Tooltip("Patente:N", title="Patente"),
                alt.Tooltip("LitrosHoy:Q", title="Litros hoy", format=",.0f"),
                alt.Tooltip("Prom:Q", title="Promedio 3M", format=",.0f"),
                alt.Tooltip("Pct:Q", title="%", format=".1f"),
            ],
        )
    )

    meta_tick = (
        alt.Chart(data)
        .mark_tick(color="#333", thickness=3, size=44)
        .encode(
            x=alt.X("Chofer:N", sort="-y"),
            y=alt.Y("Prom:Q"),
        )
    )

    pct_label = (
        alt.Chart(data)
        .mark_text(dy=-12, fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("Chofer:N", sort="-y"),
            y=alt.Y("LitrosHoy:Q"),
            text=alt.Text("Pct:Q", format=".0f"),
            color=alt.condition(
                alt.datum.SobreMeta,
                alt.value("#155724"),
                alt.value("#721c24"),
            ),
        )
    )

    return (barras + meta_tick + pct_label).properties(height=380).configure_axis(
        labelColor="#444", titleColor="#444"
    ).configure_view(strokeWidth=0)


def _tabla_resumen(data: pd.DataFrame):
    tabla = data[["Chofer", "Patente", "LitrosHoy", "Prom", "Pct"]].copy()
    tabla.columns = ["Chofer", "Patente", "Litros Hoy", "PROM 3M", "%"]

    def color_pct(val):
        if val >= 100:
            return "background-color:#d4edda; color:#155724; font-weight:bold"
        if val >= 70:
            return "background-color:#fff3cd; color:#856404"
        return "background-color:#f8d7da; color:#721c24; font-weight:bold"

    styled = (
        tabla.style
        .format({"Litros Hoy": "{:,.0f}", "PROM 3M": "{:,.0f}", "%": "{:.1f}%"})
        .apply(lambda col: [color_pct(v) for v in col], subset=["%"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def mostrar_comparativa(df_sheets: pd.DataFrame, df_mysql: pd.DataFrame):
    if df_sheets.empty:
        st.warning("Sin datos del sheet para hoy.")
        return
    if df_mysql.empty or "Patente_Real" not in df_mysql.columns:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    data = _preparar_datos(df_sheets, df_mysql)
    if data is None or data.empty:
        st.warning("Sin coincidencias entre sheet y recolecciones.")
        return

    _kpis(data)
    st.divider()

    col_graf, col_tabla = st.columns([3, 2])
    with col_graf:
        st.subheader("Litros hoy vs promedio 3 meses")
        st.altair_chart(_grafico(data), use_container_width=True)
    with col_tabla:
        st.subheader("Resumen por chofer")
        _tabla_resumen(data)
