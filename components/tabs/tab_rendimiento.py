import streamlit as st
import pandas as pd
import altair as alt
from connectors.postgres import cargar_razones
from config import UMBRAL_VERDE, UMBRAL_AMARILLO


def mostrar_rendimiento(df_rec: pd.DataFrame):
    if df_rec.empty:
        st.warning("Sin datos de recolecciones para hoy.")
        return

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

    df = df_rec.copy()
    if razones_excluidas and "Razon" in df.columns:
        df = df[~df["Razon"].isin(razones_excluidas)]

    if "NombreChofer" not in df.columns or df.empty:
        st.warning("Sin datos suficientes.")
        return

    # Fallida = tiene razón de fallo y no juntó litros; el resto exitosa
    if "Razon" in df.columns:
        fallida = df["Razon"].notna() & (df["Litros"] == 0)
    else:
        fallida = pd.Series(False, index=df.index)
    df["Resultado"] = fallida.map({True: "Fallida", False: "Exitosa"})

    if "idLocalSistema" in df.columns:
        # Una visita (local) es exitosa si alguna de sus filas por producto lo es
        exito_local = (
            (df["Resultado"] == "Exitosa")
            .groupby([df["NombreChofer"], df["idLocalSistema"]])
            .any()
        )
        df_vis = (
            exito_local.map({True: "Exitosa", False: "Fallida"})
            .rename("Resultado")
            .reset_index()
        )
    else:
        df_vis = df[["NombreChofer", "Resultado"]]

    stats = (
        df_vis.groupby(["NombreChofer", "Resultado"])
        .size()
        .reset_index(name="N")
    )
    total = stats.groupby("NombreChofer")["N"].sum().reset_index(name="Total")
    stats = stats.merge(total, on="NombreChofer")
    stats["Pct"] = (stats["N"] / stats["Total"] * 100).round(1)

    orden = (
        stats[stats["Resultado"] == "Exitosa"]
        .sort_values("Pct", ascending=True)["NombreChofer"]
        .tolist()
    )
    todos = df_vis["NombreChofer"].unique().tolist()
    faltantes = [c for c in todos if c not in orden]
    orden = faltantes + orden

    col_scale = alt.Scale(
        domain=["Exitosa", "Fallida"],
        range=["#28a745", "#dc3545"]
    )

    # % de exitosas por chofer, visible al final de cada barra con color semáforo
    pct_lbl = total.merge(
        stats[stats["Resultado"] == "Exitosa"][["NombreChofer", "Pct"]],
        on="NombreChofer", how="left",
    ).fillna({"Pct": 0})
    pct_lbl["PctTxt"] = pct_lbl["Pct"].round(0).astype(int).astype(str) + "%"
    pct_lbl["Color"] = pct_lbl["Pct"].apply(
        lambda p: "#2d7a2d" if p >= UMBRAL_VERDE
        else "#e67e22" if p >= UMBRAL_AMARILLO else "#c0392b"
    )
    max_total = int(total["Total"].max()) if not total.empty else 1

    barras = (
        alt.Chart(stats)
        .mark_bar()
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden, title=None,
                    axis=alt.Axis(labelFontSize=11)),
            x=alt.X("N:Q", stack="zero", title="Visitas",
                    scale=alt.Scale(domain=[0, max_total * 1.14])),
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
        # align right + dx negativo: el número queda DENTRO de su segmento,
        # no montado sobre el borde con el segmento siguiente
        .mark_text(fontSize=10, fontWeight="bold", color="white", align="right", dx=-5)
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("N:Q", stack="zero"),
            detail="Resultado:N",
            text=alt.Text("N:Q", format=".0f"),
        )
    )

    etiq_pct = (
        alt.Chart(pct_lbl)
        .mark_text(align="left", dx=6, fontSize=12, fontWeight="bold")
        .encode(
            y=alt.Y("NombreChofer:N", sort=orden),
            x=alt.X("Total:Q"),
            text="PctTxt:N",
            color=alt.Color("Color:N", scale=None),
            tooltip=[
                alt.Tooltip("NombreChofer:N", title="Chofer"),
                alt.Tooltip("Pct:Q", title="% Exitosas", format=".1f"),
            ],
        )
    )

    chart = (
        (barras + etiquetas + etiq_pct)
        .resolve_scale(color="independent")
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

    st.altair_chart(chart, width='stretch')

    st.divider()
    base = (
        df_vis.groupby("NombreChofer")["Resultado"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["Exitosa", "Fallida"], fill_value=0)
        .reset_index()
        .rename(columns={"NombreChofer": "Chofer", "Exitosa": "N Exitosas", "Fallida": "N Fallidas"})
    )
    base["Total"] = base["N Exitosas"] + base["N Fallidas"]
    base["% Exitosas"] = (base["N Exitosas"] / base["Total"] * 100).round(1)
    base["% Fallidas"] = (base["N Fallidas"] / base["Total"] * 100).round(1)
    resumen = base[["Chofer", "N Exitosas", "N Fallidas", "% Exitosas", "% Fallidas"]].sort_values("% Exitosas", ascending=False)

    def _color_exitosas(col):
        return [
            "color:#155724;font-weight:bold" if v >= 80 else
            ("color:#721c24;font-weight:bold" if v < 50 else "")
            for v in col
        ]

    styled = (
        resumen.style
        .format({"N Exitosas": "{:.0f}", "N Fallidas": "{:.0f}",
                 "% Exitosas": "{:.1f}%", "% Fallidas": "{:.1f}%"})
        .apply(_color_exitosas, subset=["% Exitosas"])
    )
    st.dataframe(styled, width='stretch', hide_index=True)
