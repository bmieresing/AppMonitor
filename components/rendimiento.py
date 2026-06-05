import streamlit as st
import pandas as pd
import altair as alt
from connectors.postgres import cargar_razones


def mostrar_rendimiento(df_rec: pd.DataFrame):
    if df_rec.empty:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    # Dropdown para excluir razones de fallo
    df_razones = cargar_razones()
    razones_excluidas = []
    if not df_razones.empty:
        opciones = df_razones.set_index("id")["name"].to_dict()
        excluir = st.multiselect(
            "Excluir razones de fallo del cálculo",
            options=list(opciones.keys()),
            format_func=lambda x: opciones[x],
            default=[],
        )
        razones_excluidas = excluir

    # Filtrar filas con razones excluidas
    df = df_rec.copy()
    if razones_excluidas and "Razon" in df.columns:
        df = df[~df["Razon"].isin(razones_excluidas)]

    if "NombreChofer" not in df.columns or df.empty:
        st.warning("Sin datos suficientes.")
        return

    # Calcular exitosas y fallidas por chofer
    def clasificar(row):
        if pd.notna(row.get("Razon")) and row.get("Litros", 0) == 0:
            return "Fallida"
        return "Exitosa"

    df["Resultado"] = df.apply(clasificar, axis=1)

    stats = (
        df.groupby(["NombreChofer", "Resultado"])
        .size()
        .reset_index(name="N")
    )
    total = stats.groupby("NombreChofer")["N"].sum().reset_index(name="Total")
    stats = stats.merge(total, on="NombreChofer")
    stats["Pct"] = (stats["N"] / stats["Total"] * 100).round(1)

    # Orden por % exitosas descendente
    orden = (
        stats[stats["Resultado"] == "Exitosa"]
        .sort_values("Pct", ascending=True)["NombreChofer"]
        .tolist()
    )
    # Choferes sin exitosas van al final
    todos = df["NombreChofer"].unique().tolist()
    faltantes = [c for c in todos if c not in orden]
    orden = faltantes + orden

    col_scale = alt.Scale(
        domain=["Exitosa", "Fallida"],
        range=["#28a745", "#dc3545"]
    )

    barras = (
        alt.Chart(stats)
        .mark_bar()
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden, title=None,
                    axis=alt.Axis(labelFontSize=11)),
            x=alt.X("N:Q", stack="zero", title="Visitas"),
            color=alt.Color("Resultado:N", scale=col_scale,
                            legend=alt.Legend(title=None, orient="top")),
            tooltip=[
                alt.Tooltip("NombreChofer:N", title="Chofer"),
                alt.Tooltip("Resultado:N", title="Resultado"),
                alt.Tooltip("N:Q", title="Visitas"),
                alt.Tooltip("Pct:Q", title="%", format=".1f"),
            ],
        )
    )

    etiquetas = (
        alt.Chart(stats[stats["N"] > 2])
        .mark_text(fontSize=10, fontWeight="bold", color="white")
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("N:Q", stack="zero"),
            detail="Resultado:N",
            text=alt.Text("N:Q", format=".0f"),
        )
    )

    chart = (
        (barras + etiquetas)
        .properties(
            title=alt.TitleParams(
                "EFECTIVIDAD POR CHOFER — EXITOSAS VS FALLIDAS (%)",
                fontSize=13, fontWeight="bold", anchor="start"
            ),
            height=max(300, len(orden) * 28),
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )

    st.altair_chart(chart, use_container_width=True)

    # Tabla resumen
    st.divider()
    base = df.groupby("NombreChofer").apply(lambda g: pd.Series({
        "N Exitosas":  int((g["Resultado"] == "Exitosa").sum()),
        "N Fallidas":  int((g["Resultado"] == "Fallida").sum()),
        "Total":       len(g),
    })).reset_index().rename(columns={"NombreChofer": "Chofer"})
    base["% Exitosas"] = (base["N Exitosas"] / base["Total"] * 100).round(1)
    base["% Fallidas"] = (base["N Fallidas"] / base["Total"] * 100).round(1)
    resumen = base[["Chofer", "N Exitosas", "N Fallidas", "% Exitosas", "% Fallidas"]].sort_values("% Exitosas", ascending=False)

    styled = (
        resumen.style
        .format({"N Exitosas": "{:.0f}", "N Fallidas": "{:.0f}",
                 "% Exitosas": "{:.1f}%", "% Fallidas": "{:.1f}%"})
        .applymap(lambda v: "color:#155724;font-weight:bold" if v >= 80 else
                            ("color:#721c24;font-weight:bold" if v < 50 else ""),
                  subset=["% Exitosas"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
