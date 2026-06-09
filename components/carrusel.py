import streamlit as st
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from connectors.postgres import cargar_productos, cargar_razones
from connectors.mysql import cargar_estado_locales, cargar_emergencias
from connectors.sheets import cargar_datos, cargar_datos_regiones
from components.comparativa import _preparar_datos

INTERVALO_SEG = 10
INTERVALO_ZONAS_SEG = 20

_EXCLUIR_LITROS = {"Latas", "Desengrasante"}


def _donut(exitosas: int, pend_alta: int, pend_normal: int, razon_counts: pd.DataFrame) -> alt.Chart:
    _REDS = ["#e74c3c", "#c0392b", "#a93226", "#7b241c", "#641e16"]
    razones = razon_counts["NombreRazon"].tolist() if not razon_counts.empty else []
    rows = (
        [{"Tipo": "Exitosas", "N": exitosas}]
        + [{"Tipo": r, "N": int(n)} for r, n in zip(razones, razon_counts["N"].tolist() if not razon_counts.empty else [])]
        + [{"Tipo": "Pend. Alta", "N": pend_alta}, {"Tipo": "Pend. Baja/Media", "N": pend_normal}]
    )
    datos = pd.DataFrame([r for r in rows if r["N"] > 0])
    if datos.empty:
        datos = pd.DataFrame([{"Tipo": "Sin datos", "N": 1}])

    domain = ["Exitosas"] + razones + ["Pend. Alta", "Pend. Baja/Media"]
    rng    = ["#28a745"] + _REDS[:len(razones)] + ["#555555", "#95a5a6"]

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
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;
                        opacity:0.8">{label}</div>
            <div style="font-size:26px;font-weight:900;line-height:1.1">{valor}</div>
            <div style="font-size:10px;opacity:0.8;margin-top:2px">{sub}</div>
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
            <div style="min-width:14px;font-weight:800;color:#ccc;font-size:11px">{i}</div>
            <div style="flex:1;overflow:hidden">
                <div style="font-size:10px;font-weight:600;white-space:nowrap;
                            overflow:hidden;text-overflow:ellipsis">{local}</div>
                <div style="background:#eee;border-radius:2px;height:4px;margin-top:3px">
                    <div style="background:{color};width:{pct:.0f}%;height:100%;border-radius:2px"></div>
                </div>
            </div>
            <div style="min-width:44px;text-align:right;font-weight:700;
                        font-size:11px;color:{color}">{litros:,}L</div>
        </div>"""

    st.html(f"""
    <div style="background:white;border:1px solid #e8e8e8;border-radius:8px;
                padding:10px 12px;margin-bottom:8px">
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;color:#555;margin-bottom:4px">{titulo}</div>
        {filas if filas else '<div style="color:#aaa;font-size:11px">Sin datos</div>'}
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
                    padding:10px 12px;color:#aaa;font-size:11px">Sin fallos hoy</div>""")
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
                <div style="font-size:10px;font-weight:600;white-space:nowrap;
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
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
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
                <span style="font-size:11px;font-weight:700;color:#222">{row['Producto']}</span>
                <div style="display:flex;gap:10px;align-items:center">
                    <span style="font-size:10px;color:#999;background:#f5f5f5;
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
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1px;color:#555;margin-bottom:2px">🧴 Por producto</div>
        {filas}
    </div>""")


def _global_strip(df_rec: pd.DataFrame):
    df_rec_lit = df_rec[~df_rec["Producto"].isin(_EXCLUIR_LITROS)] if not df_rec.empty and "Producto" in df_rec.columns else df_rec
    litros_hoy = df_rec_lit["Litros"].sum() if not df_rec_lit.empty else 0
    n_choferes = df_rec["NombreChofer"].nunique() if "NombreChofer" in df_rec.columns else 0
    prom_por_ruta = litros_hoy / n_choferes if n_choferes > 0 else 0

    df_sheets = cargar_datos()
    data_comp = pd.DataFrame()
    if not df_sheets.empty and not df_rec.empty:
        result = _preparar_datos(df_sheets, df_rec)
        data_comp = result if result is not None else pd.DataFrame()
    prom_stgo = data_comp["Prom"].sum() if not data_comp.empty else 0
    df_reg = cargar_datos_regiones()
    col_prom_reg = next((c for c in df_reg.columns if "PROM" in c.upper()), None)
    prom_reg = df_reg[col_prom_reg].sum() if (not df_reg.empty and col_prom_reg) else 0
    prom_total = prom_stgo + prom_reg
    vs_pct = (litros_hoy / prom_total * 100) if prom_total > 0 else 0

    df_locales = cargar_estado_locales()
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


def mostrar_carrusel_zonas(
    df_sheets: pd.DataFrame,
    df_rec: pd.DataFrame,
    df_rec_stgo: pd.DataFrame,
    df_rec_reg: pd.DataFrame,
    df_regiones: pd.DataFrame,
    choferes_todos: set,
    choferes_stgo: set,
    choferes_reg: set,
):
    from components.dashboard import mostrar_dashboard, mostrar_cards_choferes, _preparar_datos_regiones

    _data_comp_reg = _preparar_datos_regiones(df_regiones, df_rec_reg)

    VISTAS = [
        ("Global",    lambda: mostrar_dashboard(
            df_sheets, df_rec, key_prefix="cz_global_",
            choferes_filter=choferes_todos, tab_nombre="Global",
            mostrar_donuts=True, mostrar_peores=False,
        )),
        ("Santiago",  lambda: mostrar_cards_choferes(
            df_sheets, df_rec_stgo, choferes_filter=choferes_stgo,
            key_prefix="cz_stgo_cards_", tab_nombre="Santiago",
        )),
        ("Regiones",  lambda: mostrar_cards_choferes(
            df_regiones, df_rec_reg, choferes_filter=choferes_reg,
            key_prefix="cz_reg_cards_", tab_nombre="Regiones",
            data_comp_override=_data_comp_reg,
        )),
    ]
    n = len(VISTAS)

    for key, val in [("cz_idx", 0), ("cz_tick_prev", 0), ("cz_auto", True)]:
        if key not in st.session_state:
            st.session_state[key] = val

    idx = st.session_state.cz_idx % n

    VISTAS[idx][1]()

    c_prev, c_ind, c_next, c_auto = st.columns([1, 8, 1, 3])
    with c_prev:
        if st.button("◀", key="cz_prev", width='stretch'):
            st.session_state.cz_idx = (idx - 1) % n
            st.rerun()
    with c_ind:
        dots = "  ".join(
            f'<span style="color:#1a472a;font-size:18px">⬤</span>' if i == idx
            else f'<span style="color:#ccc;font-size:18px">⬤</span>'
            for i in range(n)
        )
        labels = "  ·  ".join(
            f'<strong>{v[0]}</strong>' if i == idx else f'<span style="color:#aaa">{v[0]}</span>'
            for i, v in enumerate(VISTAS)
        )
        st.markdown(
            f'<div style="text-align:center;padding:4px 0">{dots}<br>'
            f'<span style="font-size:12px">{labels}</span></div>',
            unsafe_allow_html=True,
        )
    with c_next:
        if st.button("▶", key="cz_next", width='stretch'):
            st.session_state.cz_idx = (idx + 1) % n
            st.rerun()
    with c_auto:
        auto = st.toggle("Auto-avanzar", key="cz_auto")
        if auto:
            tick = st_autorefresh(interval=INTERVALO_ZONAS_SEG * 1000, key="cz_tick")
            if tick != st.session_state.cz_tick_prev:
                st.session_state.cz_idx = (st.session_state.cz_idx + 1) % n
                st.session_state.cz_tick_prev = tick


def mostrar_carrusel(df_rec: pd.DataFrame, data_comp: pd.DataFrame | None = None):
    if df_rec.empty or "NombreChofer" not in df_rec.columns:
        st.warning("Sin datos de recolecciones para hoy.")
        return

    choferes = sorted(df_rec["NombreChofer"].dropna().unique().tolist())
    n = len(choferes)
    if n == 0:
        return

    productos = cargar_productos()
    if not productos.empty:
        df_rec = df_rec.copy()
        df_rec["Producto"] = df_rec["idProducto"].map(
            productos.set_index("id")["name"]
        ).fillna("Sin producto")

    for key, val in [("carrusel_idx", 0), ("carrusel_tick_prev", 0)]:
        if key not in st.session_state:
            st.session_state[key] = val

    # Auto-avanzar
    c_slicer, c_toggle = st.columns([8, 1])
    with c_toggle:
        auto = st.toggle("Auto", value=False, key="carrusel_auto")
    if auto:
        tick = st_autorefresh(interval=INTERVALO_SEG * 1000, key="carrusel_tick")
        if tick != st.session_state.carrusel_tick_prev:
            st.session_state.carrusel_idx = (st.session_state.carrusel_idx + 1) % n
            st.session_state.carrusel_tick_prev = tick

    idx = st.session_state.carrusel_idx % n

    # Slicer — pill por chofer
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

    # Dedup por (local, producto): la vista tiene 1 fila por producto, pero puede duplicar filas
    _id_col = "idLocalSistema" if "idLocalSistema" in df_c.columns else None
    if _id_col and "idProducto" in df_c.columns:
        df_c = df_c.drop_duplicates(subset=[_id_col, "idProducto"])

    df_c_lit = df_c[~df_c["Producto"].isin(_EXCLUIR_LITROS)] if "Producto" in df_c.columns else df_c
    litros_tot = int(df_c_lit["Litros"].sum())

    # Visitas únicas por local
    if _id_col:
        _lit_por_local = df_c_lit.groupby(_id_col)["Litros"].sum() if not df_c_lit.empty else pd.Series(dtype=float)
        exitosas = int((_lit_por_local > 0).sum())
        _dedup_local = df_c.drop_duplicates(subset=_id_col)
        fallidas = int(_dedup_local["Razon"].notna().sum()) if "Razon" in _dedup_local.columns else 0
    else:
        exitosas = int((df_c["Litros"] > 0).sum())
        fallidas = int(df_c["Razon"].notna().sum()) if "Razon" in df_c.columns else 0

    # Pendientes desde df_locales filtrado por ID del chofer
    df_locales_all = cargar_estado_locales()
    chofer_id = None
    if not df_c.empty and "Chofer" in df_c.columns:
        chofer_id = df_c["Chofer"].iloc[0]
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

    # Emergencias asignadas al chofer hoy, cruzadas con VistaMonitor
    emerg_total = emerg_realizadas = 0
    df_emerg_all = cargar_emergencias()
    if not df_emerg_all.empty and "chofer_asignado" in df_emerg_all.columns and chofer_id is not None:
        try:
            df_emerg = df_emerg_all[df_emerg_all["chofer_asignado"].astype(int) == int(chofer_id)]
            emerg_total = len(df_emerg)
            if emerg_total > 0 and "id_local" in df_emerg.columns and _id_col and not df_c.empty:
                locales_ch = set(df_c[_id_col].dropna().astype(int).tolist())
                emerg_realizadas = int(df_emerg["id_local"].dropna().astype(int).isin(locales_ch).sum())
        except (ValueError, TypeError):
            pass

    # Split de fallidas por razón
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

    # ── Tanques del banner ───────────────────────────────────────
    def _tanque_b(pct: int, emoji: str, label: str, sub: str) -> str:
        if pct >= 100: c = "#81c784"
        elif pct >= 80: c = "#a5d6a7"
        elif pct >= 50: c = "#ffb74d"
        else:           c = "#ef9a9a"
        h = min(pct, 100)
        partes = [p.strip() for p in sub.split("/")]
        if len(partes) == 2:
            sub_html = (f'<span style="font-size:22px;font-weight:900;color:white">{partes[0]}</span>'
                        f'<span style="font-size:13px;color:rgba(255,255,255,0.45);margin:0 3px">/</span>'
                        f'<span style="font-size:13px;font-weight:600;color:rgba(255,255,255,0.7)">{partes[1]}</span>')
        else:
            sub_html = f'<span style="font-size:22px;font-weight:900;color:white">{sub}</span>'
        return f"""
        <div style="text-align:center;min-width:90px">
            <div style="font-size:9px;text-transform:uppercase;letter-spacing:1px;
                        color:rgba(255,255,255,0.55);margin-bottom:3px">{emoji} {label}</div>
            <div style="display:flex;align-items:baseline;justify-content:center;gap:1px;margin-bottom:6px">{sub_html}</div>
            <div style="position:relative;height:62px;border:2px solid {c};
                        border-radius:4px 4px 6px 6px;overflow:hidden;background:rgba(255,255,255,0.06)">
                <div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;
                            background:rgba(255,255,255,0.18)"></div>
                <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
                    <span style="font-size:18px;font-weight:900;color:{c}">{pct}%</span>
                </div>
            </div>
        </div>"""

    # Litros vs esperado
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

    # Locales — visitados = exitosas + fallidas (df_rec), total desde df_locales
    visitados = exitosas + fallidas
    if not df_loc_ch.empty:
        _t = len(df_loc_ch)
        pct_loc = int(visitados / _t * 100) if _t > 0 else 0
        sub_loc = f"{visitados}/{_t}"
        if "Prioridad" in df_loc_ch.columns:
            _alta = df_loc_ch[df_loc_ch["Prioridad"].astype(str).str.upper().str.startswith("ALTA")]
            _ta, _ra = len(_alta), int((_alta["Estado"] == "Realizado").sum())
            pct_alta_loc = int(_ra / _ta * 100) if _ta > 0 else 0
            sub_alta_loc = f"{_ra}/{_ta}"
        else:
            _ta = 0; pct_alta_loc = 0; sub_alta_loc = "—"
    else:
        _t = 0; pct_loc = pct_alta_loc = 0; sub_loc = sub_alta_loc = "—"; _ta = 0

    pct_emerg = int(emerg_realizadas / emerg_total * 100) if emerg_total > 0 else 0
    sub_emerg = f"{emerg_realizadas}/{emerg_total}" if emerg_total > 0 else "—"

    tanques_html = (
        _tanque_b(pct_lit, "💧", "Litros", sub_lit)
        + _tanque_b(pct_loc, "🏪", "Locales", sub_loc)
        + (_tanque_b(pct_alta_loc, "⭐", "Alta", sub_alta_loc) if _ta > 0 else "")
        + (_tanque_b(pct_emerg, "🚨", "Emergencias", sub_emerg) if emerg_total > 0 else "")
    )

    # ── Banner ───────────────────────────────────────────────────
    st.html(f"""
    <div style="background:linear-gradient(135deg,#1a472a,#1a6b8a);border-radius:14px;
                padding:16px 28px;color:white;margin-top:6px">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:2px;
                    opacity:0.7;margin-bottom:8px">Chofer</div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap">
            <span style="font-size:38px;font-weight:900;line-height:1">{chofer}</span>
            <div style="display:flex;gap:14px">{tanques_html}</div>
        </div>
    </div>""")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Cuerpo ───────────────────────────────────────────────────
    col_iz, col_der = st.columns([2, 3])

    with col_iz:
        st.altair_chart(_donut(exitosas, pend_alta, pend_normal, razon_counts), width='stretch')
        _mini_kpis(exitosas, fallidas, pend_alta, pend_normal)

    with col_der:
        c_tops, c_prod = st.columns([1, 1])
        with c_tops:
            _top5(df_c, "🏆 Top 5 — Más litros",   ascendente=False, color="#2d7a2d")
            _top5(df_c, "⚠️ Top 5 — Menos litros", ascendente=True,  color="#e67e22")
        with c_prod:
            _productos(df_c)
