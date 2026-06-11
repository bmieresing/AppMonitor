import streamlit as st
import pandas as pd
from connectors.postgres import cargar_razones
from config import UMBRAL_VERDE, UMBRAL_AMARILLO

C_EXITOSA = "#28a745"
C_FALLIDA = "#dc3545"


def _color_sem(pct: float) -> str:
    if pct >= UMBRAL_VERDE:
        return "#2d7a2d"
    if pct >= UMBRAL_AMARILLO:
        return "#e67e22"
    return "#c0392b"


def _caja_chofer(nombre: str, n_exit: int, n_fall: int, pct: float) -> str:
    """Caja horizontal estilo tanque (de lado): nombre a la izquierda y, en la
    misma fila, dos segmentos proporcionales exitosas/fallidas con el número
    de visitas dentro. Los % van en el hover (las cantidades ya se ven en el
    gráfico). Borde con color semáforo, como los tanques."""
    color = _color_sem(pct)
    segs = ""
    # min-width: que el número siga legible aunque el segmento sea chico
    for n, fondo in ((n_exit, C_EXITOSA), (n_fall, C_FALLIDA)):
        if n > 0:
            segs += (
                f'<div style="flex:{n} 1 0;min-width:34px;background:{fondo};'
                f'display:flex;align-items:center;justify-content:center">'
                f'<span style="font-size:15px;font-weight:900;color:white;'
                f'text-shadow:0 1px 2px rgba(0,0,0,0.25)">{n}</span></div>'
            )
    pct_fall = 100 - pct
    return (
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px" '
        f'title="{nombre}: {pct:.0f}% exitosas · {pct_fall:.0f}% fallidas">'
        f'<span style="flex:0 0 150px;font-size:12px;font-weight:700;color:#333;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right">{nombre}</span>'
        f'<div style="flex:1;display:flex;height:30px;border:2px solid {color};border-radius:6px;'
        f'overflow:hidden;background:#fafafa">{segs}</div>'
        f'</div>'
    )


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

    base = (
        df_vis.groupby("NombreChofer")["Resultado"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["Exitosa", "Fallida"], fill_value=0)
        .reset_index()
    )
    base["Total"] = base["Exitosa"] + base["Fallida"]
    base["Pct"] = (base["Exitosa"] / base["Total"] * 100).round(1)

    # Cajas por chofer (estilo tanque de lado), peores % primero como en el
    # gráfico anterior, repartidas en dos columnas
    st.markdown(
        '<div style="font-size:13px;font-weight:700;margin-bottom:2px">'
        'EFECTIVIDAD POR CHOFER — EXITOSAS VS FALLIDAS</div>'
        f'<div style="font-size:12px;color:#666;margin-bottom:10px">'
        f'<span style="color:{C_EXITOSA}">●</span> Exitosas&nbsp;&nbsp;'
        f'<span style="color:{C_FALLIDA}">●</span> Fallidas&nbsp;&nbsp;'
        f'(número = visitas)</div>',
        unsafe_allow_html=True,
    )
    filas = base.sort_values("Pct", ascending=True)
    cajas = [
        _caja_chofer(r["NombreChofer"], int(r["Exitosa"]), int(r["Fallida"]), r["Pct"])
        for _, r in filas.iterrows()
    ]
    mitad = -(-len(cajas) // 2)
    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        st.markdown("".join(cajas[:mitad]), unsafe_allow_html=True)
    with col_b:
        st.markdown("".join(cajas[mitad:]), unsafe_allow_html=True)
