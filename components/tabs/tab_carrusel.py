import streamlit as st
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from components.helpers.carrusel_data import datos_chofer
from components.helpers.data_prep import _cerrados_set
from config import INTERVALO_CARRUSEL_SEG

_NO_ALC = "No alcanzamos a pasar"
_NO_ALC_COLOR = "#e53935"
_REDS_OTROS = ["#c0392b", "#922b21", "#7b241c", "#641e16", "#4a0e0e"]


def _donut(exitosas: int, pend_alta: int, pend_normal: int, razon_counts: pd.DataFrame) -> alt.Chart:
    razones = razon_counts["NombreRazon"].tolist() if not razon_counts.empty else []
    rows = (
        [{"Tipo": "Exitosas", "N": exitosas}]
        + [{"Tipo": r, "N": int(n)} for r, n in zip(razones, razon_counts["N"].tolist() if not razon_counts.empty else [])]
        + [{"Tipo": "Pend. Alta", "N": pend_alta}, {"Tipo": "Pend. Baja/Media", "N": pend_normal}]
    )
    datos = pd.DataFrame([r for r in rows if r["N"] > 0])
    if datos.empty:
        datos = pd.DataFrame([{"Tipo": "Sin datos", "N": 1}])

    _oi = 0
    rng_razones = []
    for r in razones:
        if r == _NO_ALC:
            rng_razones.append(_NO_ALC_COLOR)
        else:
            rng_razones.append(_REDS_OTROS[_oi % len(_REDS_OTROS)])
            _oi += 1

    domain = ["Exitosas"] + razones + ["Pend. Alta", "Pend. Baja/Media"]
    rng    = ["#28a745"] + rng_razones + ["#555555", "#95a5a6"]

    arco = (
        alt.Chart(datos)
        .mark_arc(innerRadius=55, outerRadius=100)
        .encode(
            theta=alt.Theta("N:Q"),
            color=alt.Color(
                "Tipo:N",
                scale=alt.Scale(domain=domain, range=rng),
                legend=alt.Legend(orient="bottom", title=None,
                                  labelFontSize=10, symbolSize=80, columns=2),
            ),
            tooltip=[alt.Tooltip("Tipo:N", title=""), alt.Tooltip("N:Q", title="Cant.")],
        )
    )

    return arco.properties(width=240, height=300)


def _mini_kpis(exitosas: int, fallidas: int, pend_alta: int, pend_normal: int):
    datos = [
        ("#2d7a2d", "EXITOSAS",     str(exitosas),    "recolecciones"),
        ("#c0392b", "FALLIDAS",     str(fallidas),    "sin recolección"),
        ("#555555", "PEND. ALTA",   str(pend_alta),   "locales"),
        ("#95a5a6", "PEND. NORMAL", str(pend_normal), "locales"),
    ]
    cols = st.columns(4)
    for col, (color, label, valor, sub) in zip(cols, datos):
        col.html(f"""
        <div style="background:{color};border-radius:10px;padding:10px 12px;
                    color:white;text-align:center">
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;
                        opacity:0.8">{label}</div>
            <div style="font-size:26px;font-weight:900;line-height:1.1">{valor}</div>
            <div style="font-size:12px;opacity:0.8;margin-top:2px">{sub}</div>
        </div>""")


def _top5(lit_local: pd.DataFrame, titulo: str, ascendente: bool, color: str):
    if lit_local.empty:
        top = lit_local
    else:
        top = lit_local.nsmallest(5, "Litros") if ascendente else lit_local.nlargest(5, "Litros")
    max_val = top["Litros"].max() if not top.empty else 1

    filas = ""
    for i, (_, row) in enumerate(top.iterrows(), 1):
        local = str(row.get("Local", "—"))[:24]
        litros = int(row["Litros"])
        pct = litros / max_val * 100
        filas += f"""
        <div style="display:flex;align-items:center;gap:6px;padding:5px 0;
                    border-bottom:1px solid #f0f0f0">
            <div style="min-width:14px;font-weight:800;color:#ccc;font-size:12px">{i}</div>
            <div style="flex:1;overflow:hidden">
                <div style="font-size:12px;font-weight:600;white-space:nowrap;
                            overflow:hidden;text-overflow:ellipsis">{local}</div>
                <div style="background:#eee;border-radius:2px;height:4px;margin-top:3px">
                    <div style="background:{color};width:{pct:.0f}%;height:100%;border-radius:2px"></div>
                </div>
            </div>
            <div style="min-width:44px;text-align:right;font-weight:700;
                        font-size:12px;color:{color}">{litros:,}L</div>
        </div>"""

    st.html(f"""
    <div style="background:white;border:1px solid #e8e8e8;border-radius:8px;
                padding:10px 12px;margin-bottom:8px">
        <div style="font-size:12px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;color:#555;margin-bottom:4px">{titulo}</div>
        {filas if filas else '<div style="color:#aaa;font-size:12px">Sin datos</div>'}
    </div>""")


def _productos(prod: pd.DataFrame):
    if prod.empty:
        return
    max_litros = prod["Litros"].max()
    filas = ""
    for _, row in prod.iterrows():
        pct = row["Litros"] / max_litros * 100
        filas += f"""
        <div style="padding:8px 0;border-bottom:1px solid #f0f0f0">
            <div style="display:flex;justify-content:space-between;align-items:center;
                        margin-bottom:4px">
                <span style="font-size:12px;font-weight:700;color:#222">{row['Producto']}</span>
                <div style="display:flex;gap:10px;align-items:center">
                    <span style="font-size:12px;color:#999;background:#f5f5f5;
                                 padding:1px 6px;border-radius:10px">
                        {int(row['Visitas'])} visitas</span>
                    <span style="font-size:12px;font-weight:800;color:#1a6b8a">
                        {int(row['Litros']):,} L</span>
                </div>
            </div>
            <div style="background:#e8f4f8;border-radius:4px;height:6px">
                <div style="background:linear-gradient(90deg,#1a6b8a,#28a5d0);
                            width:{pct:.0f}%;height:100%;border-radius:4px"></div>
            </div>
        </div>"""
    st.html(f"""
    <div style="background:white;border:1px solid #e8e8e8;border-radius:10px;
                padding:12px 16px;margin-top:8px">
        <div style="font-size:12px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;color:#555;margin-bottom:2px">🧴 Por producto</div>
        {filas}
    </div>""")


@st.fragment
def mostrar_carrusel(df_rec: pd.DataFrame, data_comp: pd.DataFrame | None = None):
    if df_rec.empty or "NombreChofer" not in df_rec.columns:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    choferes = sorted(df_rec["NombreChofer"].dropna().unique().tolist())
    n = len(choferes)
    if n == 0:
        return

    for key, val in [("carrusel_idx", 0), ("carrusel_tick_prev", 0)]:
        if key not in st.session_state:
            st.session_state[key] = val

    c_slicer, c_toggle = st.columns([8, 1])
    with c_toggle:
        auto = st.toggle("Auto", value=False, key="carrusel_auto")
    if auto:
        tick = st_autorefresh(interval=INTERVALO_CARRUSEL_SEG * 1000, key="carrusel_tick")
        if tick != st.session_state.carrusel_tick_prev:
            st.session_state.carrusel_idx = (st.session_state.carrusel_idx + 1) % n
            st.session_state.carrusel_tick_prev = tick

    idx = st.session_state.carrusel_idx % n

    # Candado en el selector para ver de un vistazo quién ya cerró ruta
    cerrados = _cerrados_set(df_rec)
    labels = [f"🔒 {c}" if c in cerrados else c for c in choferes]

    with c_slicer:
        selected = st.pills(
            "Chofer",
            options=labels,
            default=labels[idx],
            label_visibility="collapsed",
            key="slicer_chofer",
        )

    if selected and selected in labels:
        new_idx = labels.index(selected)
        if new_idx != st.session_state.carrusel_idx:
            st.session_state.carrusel_idx = new_idx
            st.rerun()
        chofer = choferes[new_idx]
    else:
        chofer = choferes[idx]

    # Toda la lógica de datos vive en helpers/carrusel_data.py (compartida con v2)
    d = datos_chofer(df_rec, chofer, data_comp)

    def _tanque_b(pct: int, emoji: str, label: str, sub: str, no_alc_pct: int = 0) -> str:
        if pct >= 100: c = "#81c784"
        elif pct >= 80: c = "#a5d6a7"
        elif pct >= 50: c = "#ffb74d"
        else:           c = "#ef9a9a"
        h = min(pct, 100)
        h_na = min(no_alc_pct, max(0, 100 - h))
        na_layer = (
            f'<div style="position:absolute;bottom:{h}%;left:0;right:0;height:{h_na}%;background:rgba(229,57,53,0.75)"></div>'
        ) if h_na > 0 else ""
        partes = [p.strip() for p in sub.split("/")]
        if len(partes) == 2:
            sub_html = (f'<span style="font-size:22px;font-weight:900;color:white">{partes[0]}</span>'
                        f'<span style="font-size:12px;color:rgba(255,255,255,0.45);margin:0 3px">/</span>'
                        f'<span style="font-size:12px;font-weight:600;color:rgba(255,255,255,0.7)">{partes[1]}</span>')
        else:
            sub_html = f'<span style="font-size:22px;font-weight:900;color:white">{sub}</span>'
        return f"""
        <div style="text-align:center;min-width:90px">
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;
                        color:rgba(255,255,255,0.55);margin-bottom:3px">{emoji} {label}</div>
            <div style="display:flex;align-items:baseline;justify-content:center;gap:1px;margin-bottom:6px">{sub_html}</div>
            <div style="position:relative;height:62px;border:2px solid {c};
                        border-radius:4px 4px 6px 6px;overflow:hidden;background:rgba(255,255,255,0.06)">
                <div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;
                            background:rgba(255,255,255,0.18)"></div>
                {na_layer}
                <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
                    <span style="font-size:18px;font-weight:900;color:{c}">{pct}%</span>
                </div>
            </div>
        </div>"""

    tanques_html = (
        _tanque_b(d["pct_lit"], "💧", "Litros", d["sub_lit"])
        + _tanque_b(d["pct_loc"], "🏪", "Locales", d["sub_loc"], no_alc_pct=d["no_alc_pct_loc"])
        + (_tanque_b(d["pct_alta"], "⭐", "Alta", d["sub_alta"], no_alc_pct=d["no_alc_pct_alta"]) if d["tiene_alta"] else "")
    )

    st.html(f"""
    <div style="background:linear-gradient(135deg,#1a472a,#1a6b8a);border-radius:14px;
                padding:16px 28px;color:white;margin-top:6px">
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:2px;
                    opacity:0.7;margin-bottom:8px">Chofer</div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap">
            <span style="font-size:38px;font-weight:900;line-height:1">{"🔒 " if chofer in cerrados else ""}{chofer}</span>
            <div style="display:flex;gap:14px">{tanques_html}</div>
        </div>
    </div>""")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    col_iz, col_der = st.columns([2, 3])

    with col_iz:
        st.altair_chart(_donut(d["exitosas"], d["pend_alta"], d["pend_normal"], d["razon_counts"]), width='stretch')
        _mini_kpis(d["exitosas"], d["fallidas"], d["pend_alta"], d["pend_normal"])

    with col_der:
        c_tops, c_prod = st.columns([1, 1])
        with c_tops:
            _top5(d["lit_local"], "🏆 Top 5 — Más litros",   ascendente=False, color="#2d7a2d")
            _top5(d["lit_local"], "⚠️ Top 5 — Menos litros", ascendente=True,  color="#c0392b")
        with c_prod:
            _productos(d["productos"])
