import streamlit as st
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from connectors.postgres import cargar_razones
from connectors.mysql import cargar_estado_locales, cargar_emergencias
from components.helpers.data_prep import _litros
from components.helpers.kpis import exitosas_fallidas
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


def _top5(df: pd.DataFrame, titulo: str, ascendente: bool, color: str):
    filtrado = df[df["Litros"] > 0].copy()
    if "idLocalSistema" in filtrado.columns and "Local" in filtrado.columns:
        filtrado = (
            filtrado.groupby("idLocalSistema")
            .agg(Local=("Local", "first"), Litros=("Litros", "sum"))
            .reset_index(drop=True)
        )
    top = filtrado.nsmallest(5, "Litros") if ascendente else filtrado.nlargest(5, "Litros")
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


def _razones_fallo(df_c: pd.DataFrame):
    if "Razon" not in df_c.columns:
        return
    df_razones = cargar_razones()
    if df_razones.empty:
        return
    mapa = df_razones.set_index("id")["name"]
    fallidas = df_c[df_c["Razon"].notna()].copy()
    if fallidas.empty:
        st.html("""<div style="background:white;border:1px solid #e8e8e8;border-radius:8px;
                    padding:10px 12px;color:#aaa;font-size:12px">Sin fallos hoy</div>""")
        return
    fallidas["NombreRazon"] = fallidas["Razon"].map(mapa).fillna("Desconocida")
    conteo = (
        fallidas.groupby("NombreRazon").size()
        .reset_index(name="N")
        .sort_values("N", ascending=False)
    )
    max_n = conteo["N"].max()
    filas = ""
    for _, row in conteo.iterrows():
        pct = row["N"] / max_n * 100
        filas += f"""
        <div style="display:flex;align-items:center;gap:6px;padding:5px 0;
                    border-bottom:1px solid #f0f0f0">
            <div style="flex:1;overflow:hidden">
                <div style="font-size:12px;font-weight:600;white-space:nowrap;
                            overflow:hidden;text-overflow:ellipsis">{row['NombreRazon']}</div>
                <div style="background:#eee;border-radius:2px;height:4px;margin-top:3px">
                    <div style="background:#e74c3c;width:{pct:.0f}%;height:100%;border-radius:2px"></div>
                </div>
            </div>
            <div style="min-width:24px;text-align:right;font-weight:700;
                        font-size:12px;color:#e74c3c">{int(row['N'])}</div>
        </div>"""
    st.html(f"""
    <div style="background:white;border:1px solid #e8e8e8;border-radius:8px;padding:10px 12px">
        <div style="font-size:12px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;color:#555;margin-bottom:4px">
            ❌ Razones de fallo ({int(fallidas.shape[0])} total)</div>
        {filas}
    </div>""")


def _productos(df_c: pd.DataFrame):
    if "Producto" not in df_c.columns:
        return
    prod = (
        df_c[df_c["Litros"] > 0]
        .groupby("Producto")
        .agg(Visitas=("Litros", "count"), Litros=("Litros", "sum"))
        .reset_index()
        .sort_values("Litros", ascending=False)
    )
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

    with c_slicer:
        selected = st.pills(
            "Chofer",
            options=choferes,
            default=choferes[idx],
            label_visibility="collapsed",
            key="slicer_chofer",
        )

    if selected and selected in choferes:
        new_idx = choferes.index(selected)
        if new_idx != st.session_state.carrusel_idx:
            st.session_state.carrusel_idx = new_idx
            st.rerun()
        chofer = selected
    else:
        chofer = choferes[idx]

    df_c = df_rec[df_rec["NombreChofer"] == chofer].copy()

    _id_col = "idLocalSistema" if "idLocalSistema" in df_c.columns else None
    if _id_col and "idProducto" in df_c.columns:
        df_c = df_c.drop_duplicates(subset=[_id_col, "idProducto"])

    df_c_lit = _litros(df_c)
    litros_tot = int(df_c_lit["Litros"].sum())

    # Mismo criterio que los donuts globales (helpers/kpis.py)
    exitosas, fallidas = exitosas_fallidas(df_c)

    df_locales_all = cargar_estado_locales()
    chofer_id = None
    if not df_c.empty and "Chofer" in df_c.columns:
        chofer_id = df_c["Chofer"].iloc[0]
    if chofer_id is not None and not df_locales_all.empty and "Chofer" in df_locales_all.columns:
        df_loc_ch = df_locales_all[df_locales_all["Chofer"] == chofer_id]
    else:
        df_loc_ch = pd.DataFrame()

    pendientes = df_loc_ch[df_loc_ch["Estado"] != "Realizado"] if not df_loc_ch.empty else pd.DataFrame()
    if not pendientes.empty and "Prioridad" in pendientes.columns:
        es_alta = pendientes["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
        pend_alta   = int(es_alta.sum())
        pend_normal = len(pendientes) - pend_alta
    else:
        pend_alta = pend_normal = 0

    emerg_total = emerg_realizadas = 0
    df_emerg_all = cargar_emergencias()
    if not df_emerg_all.empty and "chofer_asignado" in df_emerg_all.columns and chofer_id is not None:
        try:
            emerg_total = int((df_emerg_all["chofer_asignado"].astype(int) == int(chofer_id)).sum())
        except (ValueError, TypeError):
            pass
    if emerg_total > 0 and "Emergencia" in df_c.columns and _id_col:
        emerg_realizadas = len(
            df_c[df_c["Emergencia"].astype(bool)].drop_duplicates(subset=_id_col)
        )

    razones_df = cargar_razones()
    mapa_razones = razones_df.set_index("id")["name"] if not razones_df.empty else pd.Series(dtype=str)
    if not df_c.empty and "Razon" in df_c.columns and fallidas > 0:
        df_fall = df_c[df_c["Razon"].notna()].copy()
        if _id_col:
            df_fall = df_fall.drop_duplicates(subset=_id_col)
        df_fall["NombreRazon"] = df_fall["Razon"].map(mapa_razones).fillna("Desconocida")
        razon_counts = (
            df_fall.groupby("NombreRazon").size()
            .reset_index(name="N")
            .sort_values("N", ascending=False)
        )
    else:
        razon_counts = pd.DataFrame(columns=["NombreRazon", "N"])

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

    if data_comp is not None and not data_comp.empty and "Chofer" in data_comp.columns:
        fila = data_comp[data_comp["Chofer"] == chofer]
        if not fila.empty:
            _lh  = float(fila.iloc[0].get("LitrosHoy", litros_tot))
            _pr  = float(fila.iloc[0].get("Prom", 0))
            pct_lit = int(_lh / _pr * 100) if _pr > 0 else 0
            sub_lit = f"{int(_lh):,} / {int(_pr):,} L"
        else:
            pct_lit = 0; sub_lit = f"{litros_tot:,} L"
    else:
        pct_lit = 0; sub_lit = f"{litros_tot:,} L"

    if not df_loc_ch.empty:
        _t = len(df_loc_ch)
        pct_loc = int(exitosas / _t * 100) if _t > 0 else 0
        sub_loc = f"{exitosas}/{_t}"
        if "Prioridad" in df_loc_ch.columns:
            _alta = df_loc_ch[df_loc_ch["Prioridad"].astype(str).str.upper().str.startswith("ALTA")]
            _ta, _ra = len(_alta), int((_alta["Estado"] == "Realizado").sum())
            pct_alta_loc = int(_ra / _ta * 100) if _ta > 0 else 0
            sub_alta_loc = f"{_ra}/{_ta}"
        else:
            _ta = 0; pct_alta_loc = 0; sub_alta_loc = "—"
    else:
        _t = 0; pct_loc = pct_alta_loc = 0; sub_loc = sub_alta_loc = "—"; _ta = 0

    no_alc_loc = 0
    if not df_c.empty and "Razon" in df_c.columns and _id_col:
        _df_na_c = df_c[df_c["Razon"] == 11].drop_duplicates(subset=_id_col)
        no_alc_loc = len(_df_na_c)
    no_alc_pct_loc = int(no_alc_loc / _t * 100) if _t > 0 else 0

    pct_emerg = int(emerg_realizadas / emerg_total * 100) if emerg_total > 0 else 0
    sub_emerg = f"{emerg_realizadas}/{emerg_total}" if emerg_total > 0 else "—"

    tanques_html = (
        _tanque_b(pct_lit, "💧", "Litros", sub_lit)
        + _tanque_b(pct_loc, "🏪", "Locales", sub_loc, no_alc_pct=no_alc_pct_loc)
        + (_tanque_b(pct_alta_loc, "⭐", "Alta", sub_alta_loc) if _ta > 0 else "")
        + (_tanque_b(pct_emerg, "🚨", "Emergencias", sub_emerg) if emerg_total > 0 else "")
    )

    st.html(f"""
    <div style="background:linear-gradient(135deg,#1a472a,#1a6b8a);border-radius:14px;
                padding:16px 28px;color:white;margin-top:6px">
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:2px;
                    opacity:0.7;margin-bottom:8px">Chofer</div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap">
            <span style="font-size:38px;font-weight:900;line-height:1">{chofer}</span>
            <div style="display:flex;gap:14px">{tanques_html}</div>
        </div>
    </div>""")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    col_iz, col_der = st.columns([2, 3])

    with col_iz:
        st.altair_chart(_donut(exitosas, pend_alta, pend_normal, razon_counts), width='stretch')
        _mini_kpis(exitosas, fallidas, pend_alta, pend_normal)

    with col_der:
        c_tops, c_prod = st.columns([1, 1])
        with c_tops:
            _top5(df_c, "🏆 Top 5 — Más litros",   ascendente=False, color="#2d7a2d")
            _top5(df_c, "⚠️ Top 5 — Menos litros", ascendente=True,  color="#c0392b")
        with c_prod:
            _productos(df_c)
