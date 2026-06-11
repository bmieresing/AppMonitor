import urllib.parse

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

from connectors.mysql import cargar_estado_locales
from connectors.estado_carga import falla_reciente, detalle_falla, forzar_ciclo
from components.helpers.data_prep import (
    _pct, _mapa_empleados, _cerrados_set, _datos_centros, _norm_key, _norm_nombre,
    hora_actualizacion,
)
from components.helpers.kpis import calcular_kpis
from config import UMBRAL_VERDE, UMBRAL_AMARILLO

TZ = ZoneInfo("America/Santiago")


def _color_pct(pct: int) -> str:
    return "#2d7a2d" if pct >= UMBRAL_VERDE else "#c0392b" if pct < UMBRAL_AMARILLO else "#e67e22"


def _metricas_choferes(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame) -> list[dict]:
    # Todos los cruces por nombre usan la clave normalizada (_norm_key): el
    # nombre del sheet puede diferir del de PostgreSQL en mayúsculas/tildes
    mapa = _mapa_empleados()
    cerrados_norm = {_norm_nombre(c) for c in _cerrados_set(df_rec)}

    df_loc = df_locales.copy() if not df_locales.empty else pd.DataFrame()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc["NombreChofer"] = pd.to_numeric(df_loc["Chofer"], errors="coerce").map(mapa).fillna(df_loc["Chofer"].astype(str))
        df_loc["_key"] = _norm_key(df_loc["NombreChofer"].astype(str))
        df_loc["EsAlta"] = (
            df_loc["Prioridad"].astype(str).str.upper().str.startswith("ALTA")
            if "Prioridad" in df_loc.columns else False
        )

    no_alc_ch: dict[str, int] = {}
    no_alc_alta_ch: dict[str, int] = {}
    if not df_rec.empty and "Razon" in df_rec.columns and "Chofer" in df_rec.columns:
        cols_dd = ["Chofer", "idLocalSistema"] if "idLocalSistema" in df_rec.columns else ["Chofer"]
        df_na = df_rec[df_rec["Razon"] == 11].drop_duplicates(subset=cols_dd).copy()
        if not df_na.empty:
            df_na["NombreChofer"] = pd.to_numeric(df_na["Chofer"], errors="coerce").map(mapa).fillna(df_na["Chofer"].astype(str))
            df_na["_key"] = _norm_key(df_na["NombreChofer"].astype(str))
            no_alc_ch = df_na.groupby("_key").size().to_dict()
            if not df_loc.empty and "ID_Local" in df_loc.columns and "idLocalSistema" in df_na.columns:
                alta_ids = set(df_loc[df_loc["EsAlta"]]["ID_Local"].astype(int))
                df_na_alta = df_na[df_na["idLocalSistema"].dropna().astype(int).isin(alta_ids)]
                no_alc_alta_ch = df_na_alta.groupby("_key").size().to_dict()

    rows = []
    for _, fila in data_comp.sort_values("Pct", ascending=False).iterrows():
        nombre     = fila["Chofer"]
        litros_hoy = float(fila.get("LitrosHoy", 0))
        prom       = float(fila.get("Prom", 0))
        pct_lit    = _pct(litros_hoy, prom)

        key = _norm_nombre(str(nombre))
        pct_loc = pct_alta = no_alc_pct_loc = no_alc_pct_alta = 0
        sub_loc = sub_alta = None

        if not df_loc.empty and "_key" in df_loc.columns:
            grp = df_loc[df_loc["_key"] == key]
            if not grp.empty:
                t = len(grp)
                r = int((grp["Estado"] == "Realizado").sum())
                na = no_alc_ch.get(key, 0)
                r_exit = max(0, r - na)
                pct_loc = _pct(r_exit, t)
                no_alc_pct_loc = _pct(na, t)
                sub_loc = f"{r_exit}/{t}"

                grp_alta = grp[grp["EsAlta"]]
                if not grp_alta.empty:
                    t_a = len(grp_alta)
                    r_a = int((grp_alta["Estado"] == "Realizado").sum())
                    na_a = no_alc_alta_ch.get(key, 0)
                    r_a_exit = max(0, r_a - na_a)
                    pct_alta = _pct(r_a_exit, t_a)
                    no_alc_pct_alta = _pct(na_a, t_a)
                    sub_alta = f"{r_a_exit}/{t_a}"

        ruta = fila.get("Ruta")
        ruta = str(ruta).strip() if pd.notna(ruta) and str(ruta).strip() else None

        rows.append(dict(
            nombre=nombre,
            ruta=ruta,
            cerrado=key in cerrados_norm,
            litros_hoy=litros_hoy, prom=prom, pct_lit=pct_lit,
            pct_loc=pct_loc, sub_loc=sub_loc, no_alc_pct_loc=no_alc_pct_loc,
            pct_alta=pct_alta, sub_alta=sub_alta, no_alc_pct_alta=no_alc_pct_alta,
        ))
    return rows


def _donut_fig(
    pct: int,
    color_fill: str,
    color_bg: str = "#e0e0e0",
    segmento_alerta: int = 0,
    color_alerta: str = "#e53935",
    emoji: str = "",
    compact: bool = False,
    labels: list[str] | None = None,
    cantidades: list[str] | None = None,
) -> go.Figure:
    """Anillo con emoji y % en el centro (el emoji va dentro del donut para
    que escale con el gráfico y no le quite ancho en ventanas angostas).
    compact=True: versión reducida para Regiones (espeja el modo compacto v1).
    cantidades: 3 strings (segmento principal, alerta, restante) para mostrar
    la cantidad real en el hover, en una fila aparte del porcentaje."""
    pct_clamp    = min(pct, 100)
    pct_alerta   = min(segmento_alerta, max(0, 100 - pct_clamp))
    pct_restante = 100 - pct_clamp - pct_alerta

    # El donut ocupa la franja superior del lienzo (domain y 0.12–1): la franja
    # inferior queda libre para que el tooltip no se corte en el borde
    altura     = 115 if compact else 170
    fs_emoji   = 22 if compact else 34
    fs_pct     = 13 if compact else 20
    fs_pct_solo = 15 if compact else 22

    if cantidades:
        hover = "<b>%{label}</b><br>%{customdata}<br>%{value}%<extra></extra>"
    else:
        hover = "<b>%{label}</b><br>%{value}%<extra></extra>"

    fig = go.Figure(go.Pie(
        labels=labels or ["Realizado", "No alc.", "Restante"],
        values=[pct_clamp, pct_alerta, pct_restante],
        marker_colors=[color_fill, color_alerta, color_bg],
        customdata=cantidades or ["", "", ""],
        hole=0.72,
        sort=False,
        direction="clockwise",
        textinfo="none",
        hovertemplate=hover,
        domain=dict(y=[0.12, 1]),
    ))
    # Centro del anillo en y=0.56 (mitad del domain 0.12–1)
    if emoji:
        annotations = [
            dict(text=emoji, x=0.5, y=0.70, font_size=fs_emoji, showarrow=False),
            dict(text=f"<b>{pct}%</b>", x=0.5, y=0.39,
                 font_size=fs_pct, showarrow=False, font_color="#1a472a"),
        ]
    else:
        annotations = [
            dict(text=f"<b>{pct}%</b>", x=0.5, y=0.56,
                 font_size=fs_pct_solo, showarrow=False, font_color="#1a472a"),
        ]
    fig.update_layout(
        showlegend=False,
        margin=dict(t=0, b=0, l=0, r=0),
        height=altura,
        annotations=annotations,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _mini_metrica(col, emoji: str, label: str, pct: int, sub: str | None,
                  compact: bool = False, no_alc_pct: int = 0, grande: bool = False):
    """grande=True (banner de los carruseles): el número principal del sub va
    en 20px negrita y el denominador discreto, como los tanques del banner v1."""
    color = _color_pct(pct)
    fill  = ("rgba(45,122,45,0.22)" if pct >= UMBRAL_VERDE
             else "rgba(192,57,43,0.22)" if pct < UMBRAL_AMARILLO
             else "rgba(230,126,34,0.22)")
    h     = min(pct, 100)
    # Capa roja de "no alcanzamos a pasar" sobre el relleno (igual que los tanques v1)
    h_na  = min(no_alc_pct, max(0, 100 - h))
    na_layer = (
        f'<div style="position:absolute;bottom:{h}%;left:0;right:0;height:{h_na}%;'
        f'background:rgba(229,57,53,0.5)"></div>'
    ) if h_na > 0 else ""
    # Piso tipográfico de 12px: nada del dashboard baja de ahí
    alto, fs_pct, fs_txt = (38, 13, "12px") if compact else (52, 16, "12px")

    if grande and sub and sub != "—":
        partes = [p.strip() for p in str(sub).split("/")]
        if len(partes) == 2:
            sub_html = (
                f'<span style="font-size:20px;font-weight:800">{partes[0]}</span>'
                f'<span style="font-size:12px;opacity:0.75"> / {partes[1]}</span>'
            )
        else:
            sub_html = f'<span style="font-size:20px;font-weight:800">{sub}</span>'
    else:
        sub_html = sub or "—"

    with col:
        st.markdown(
            f'<div style="position:relative;height:{alto}px;border:1px solid {color};'
            f'border-radius:4px;overflow:hidden;background:#fafafa">'
            f'  <div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;background:{fill}"></div>'
            f'  {na_layer}'
            f'  <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">'
            f'    <span style="font-size:{fs_pct}px;font-weight:900;color:{color};white-space:nowrap">{pct}%</span>'
            f'  </div>'
            f'</div>'
            f'<p style="font-size:{fs_txt};color:#888;margin:4px 0 0;text-align:center;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{emoji} {label}</p>'
            f'<p style="font-size:{fs_txt};color:#999;margin:1px 0 0;text-align:center;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{sub or ""}">{sub_html}</p>',
            unsafe_allow_html=True,
        )


def _card_chofer(ch: dict, compact: bool = False, nav_param: str = "nav_carrusel_v2"):
    with st.container(border=True):
        prefijo = "🔒 " if ch["cerrado"] else ""
        fs_nombre = "13px" if compact else "1rem"
        # Ruta en la misma línea del nombre para no aumentar el alto de la card
        ruta_line = (
            f" <span style='font-size:12px;color:#777;white-space:nowrap'>🗺️ {ch['ruta']}</span>"
            if ch.get("ruta") else ""
        )
        # El nombre navega al carrusel de su misma familia (v2 o v3)
        link = f"?{nav_param}={urllib.parse.quote(ch['nombre'])}"
        st.markdown(
            f"<div style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:{fs_nombre}' "
            f"title=\"{ch['nombre']}{' — ' + ch['ruta'] if ch.get('ruta') else ''}\">"
            f"<strong>{prefijo}<a href='{link}' target='_self' "
            f"style='text-decoration:none;color:inherit'>{ch['nombre']}</a></strong>{ruta_line}</div>",
            unsafe_allow_html=True,
        )

        has_alta = bool(ch["sub_alta"])
        cols = st.columns(3 if has_alta else 2)

        _mini_metrica(cols[0], "💧", "Litros", ch["pct_lit"],
                      f"{int(ch['litros_hoy']):,} / {int(ch['prom']):,} L", compact=compact)
        _mini_metrica(cols[1], "🏪", "Locales", ch["pct_loc"], ch["sub_loc"],
                      compact=compact, no_alc_pct=ch.get("no_alc_pct_loc", 0))
        if has_alta:
            _mini_metrica(cols[2], "⭐", "Alta", ch["pct_alta"], ch["sub_alta"],
                          compact=compact, no_alc_pct=ch.get("no_alc_pct_alta", 0))


def _card_centro(c: dict):
    """Card de centro de acopio con componentes nativos (espejo v2 del widget #20)."""
    with st.container(border=True):
        st.markdown(
            f"<div style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis' "
            f"title=\"{c['centro']}\"><strong>{c['centro']}</strong></div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        _mini_metrica(cols[0], "💧", "Litros", _pct(c["litros"], c["prom"]),
                      f"{int(c['litros']):,} / {int(c['prom']):,} L")
        _mini_metrica(cols[1], "🏪", "Locales", _pct(c["realizados"], c["total"]),
                      f"{c['realizados']}/{c['total']}")


def _css_responsive():
    """st.columns no tiene breakpoints: solo comprime hasta romper el contenido.
    Esto permite que las columnas de nivel superior salten a la fila siguiente
    cuando bajan de un ancho mínimo (las anidadas, p. ej. las mini métricas
    dentro de una card, quedan sin mínimo para no deformar las cards)."""
    st.markdown("""
    <style>
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            min-width: 170px;
        }
        div[data-testid="stColumn"] div[data-testid="stColumn"],
        div[data-testid="column"] div[data-testid="column"] {
            min-width: 0;
        }
        /* El tooltip de Plotly se dibuja dentro del SVG del gráfico y se
           recortaba en el borde inferior de los donuts (alto 100-150px):
           dejar que desborde para que el hover se vea completo */
        div[data-testid="stPlotlyChart"],
        div[data-testid="stPlotlyChart"] .js-plotly-plot,
        div[data-testid="stPlotlyChart"] .svg-container,
        div[data-testid="stPlotlyChart"] svg.main-svg {
            overflow: visible !important;
        }
    </style>
    """, unsafe_allow_html=True)


def mostrar_tab_v2(
    df_rec: pd.DataFrame,
    choferes_filter: set,
    data_comp: pd.DataFrame,
    tab_nombre: str = "Santiago",
    data_comp_centros: pd.DataFrame | None = None,
    key_prefix: str = "",
    emoji_lado: bool = False,
):
    """emoji_lado=True (variante v3): el emoji va grande a la izquierda de la
    dona (como en v1) en vez de dentro del anillo. Misma lógica y datos."""
    _css_responsive()
    if emoji_lado:
        # Cards más anchas en v3: con el emoji al lado, la dona necesita más
        # ancho mínimo — bajo 260px la card salta a la fila siguiente en vez
        # de comprimir (y cortar) la dona. OJO: el mínimo es solo para las
        # columnas de nivel superior; las anidadas (emoji|dona, mini métricas)
        # quedan libres y sin wrap para que no se apilen en vertical.
        st.markdown("""
        <style>
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                min-width: 260px;
            }
            div[data-testid="stColumn"] div[data-testid="stColumn"],
            div[data-testid="column"] div[data-testid="column"] {
                min-width: 0 !important;
            }
            div[data-testid="stColumn"] div[data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
            }
        </style>
        """, unsafe_allow_html=True)
    df_locales = cargar_estado_locales()
    if not df_locales.empty:
        df_locales = df_locales[df_locales["Chofer"].isin(choferes_filter)]

    ahora = hora_actualizacion()
    titulo = f"Dashboard Operacional – Recolección de Aceite | {tab_nombre}"
    # Botón ↺ chico pegado a la fecha de actualización
    bkey = f"{key_prefix}v2_btn_{tab_nombre}".replace(" ", "_")
    st.markdown(f"""
    <style>
        .st-key-{bkey} button {{
            min-height: 24px !important;
            height: 24px !important;
            padding: 0 8px !important;
            font-size: 13px !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    _toggle_kwargs = dict(
        value="REGION" in tab_nombre.upper(),
        key=f"{key_prefix}v2_compact_{tab_nombre}",
        help="Widgets y letras reducidos para que quepa más en pantalla",
    )

    # Encabezado v2/v3: título a la izquierda; fecha + ↺ + Compacto comparten fila.
    # Container horizontal (flex): cada elemento ocupa solo su ancho real,
    # así el botón queda pegado a la fecha sin columnas de por medio.
    col_titulo, col_der = st.columns([7, 4], vertical_alignment="center")
    with col_titulo:
        st.subheader(titulo)
    with col_der:
        with st.container(horizontal=True, vertical_alignment="center",
                          horizontal_alignment="right", key=bkey):
            # Sub-container sin gap: el ↺ queda pegado a la fecha; el gap normal
            # del container exterior separa este bloque del toggle Compacto
            with st.container(horizontal=True, vertical_alignment="center",
                              gap=None, width="content"):
                _falla = falla_reciente()
                _txt = f"Última actualización: {ahora.strftime('%d/%m/%Y %H:%M')}"
                if _falla:
                    _txt += f" · :red[⚠ falla {_falla.strftime('%H:%M')}]"
                st.caption(_txt, help=detalle_falla() if _falla else None)
                if st.button("↺", key=f"{key_prefix}v2_refresh_{tab_nombre}",
                             help="Recarga todos los datos desde MySQL, PostgreSQL y Google Sheets"):
                    forzar_ciclo()  # el próximo run ejecuta un ciclo completo
                    st.rerun()
            # Modo compacto (espeja el compacto de _donuts_global v1). Activado por
            # defecto en Regiones; quien necesite ver más grande lo apaga acá
            compact = st.toggle("Compacto", **_toggle_kwargs)

    if compact:
        st.markdown("""
        <style>
            div[data-testid="stVerticalBlock"] > div { gap: 0.25rem !important; }
            div[data-testid="stVerticalBlockBorderWrapper"] > div {
                padding: 0.4rem 0.5rem !important;
            }
            /* El divider entre donas y cards trae márgenes grandes por defecto */
            hr { margin: 0.25rem 0 !important; }
            div[data-testid="stElementContainer"]:has(> hr) {
                margin: 0 !important;
                padding: 0 !important;
            }
        </style>
        """, unsafe_allow_html=True)

    k = calcular_kpis(df_rec, df_locales, data_comp)
    _cfg = {"displayModeBar": False}

    c1, c2, c3, c4, c5 = st.columns(5)

    def _kpi_col(col, emoji, label, valor, pct, color_fill, key,
                 color_bg="#e0e0e0", segmento_alerta=0, leyenda=None,
                 etiquetas=None, cantidades=None):
        # Donut a ancho completo con el emoji dentro del anillo: en ventanas
        # angostas la columna anidada de emoji dejaba el donut sin espacio.
        # El margen negativo sube la etiqueta sobre la franja vacía del lienzo
        # (reservada solo para que el tooltip no se corte).
        # Piso tipográfico de 12px para etiqueta y leyenda
        fs_lbl, fs_val = ("12px", "0.95rem") if compact else ("12px", "1.4rem")
        mt_lbl = "-12px" if compact else "-22px"
        with col:
            with st.container(border=True):
                if emoji_lado:
                    # Variante v3: emoji grande a la izquierda, dona sin emoji al centro
                    c_emo, c_don = st.columns([1, 2.4], gap="small",
                                              vertical_alignment="center")
                    with c_emo:
                        st.markdown(
                            f'<p style="font-size:{"40px" if compact else "64px"};'
                            f'line-height:1;margin:0;text-align:center">{emoji}</p>',
                            unsafe_allow_html=True,
                        )
                    with c_don:
                        st.plotly_chart(
                            _donut_fig(pct, color_fill, color_bg=color_bg,
                                       segmento_alerta=segmento_alerta, emoji="",
                                       compact=compact, labels=etiquetas, cantidades=cantidades),
                            width='stretch', config=_cfg, key=key,
                        )
                else:
                    st.plotly_chart(
                        _donut_fig(pct, color_fill, color_bg=color_bg,
                                   segmento_alerta=segmento_alerta, emoji=emoji,
                                   compact=compact, labels=etiquetas, cantidades=cantidades),
                        width='stretch', config=_cfg, key=key,
                    )
                dots = " &nbsp; ".join(
                    f'<span style="color:{c}">●</span> {l}'
                    for c, l in (leyenda or [])
                )
                st.markdown(
                    f'<p style="font-size:{fs_lbl};color:#999;text-transform:uppercase;'
                    f'letter-spacing:0.07em;margin:{mt_lbl} 0 0;white-space:nowrap;overflow:hidden;'
                    f'text-overflow:ellipsis" title="{label}">{label}</p>'
                    f'<p style="font-size:{fs_val};font-weight:700;color:#1a472a;margin:2px 0 0;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{valor}">{valor}</p>'
                    + (f'<p style="font-size:{fs_lbl};color:#888;margin:4px 0 0;'
                       f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{dots}</p>' if dots else ""),
                    unsafe_allow_html=True,
                )

    _kpi_col(c1, "💧", "Litros vs Esperado",
             f"{k['litros']:,.0f} / {k['esperado']:,.0f} L",
             k["pct_lit"], "#2d7a2d", key=f"{key_prefix}v2_donut_lit_{tab_nombre}",
             leyenda=[("#2d7a2d", "Recolectado"), ("#e0e0e0", "Restante")],
             etiquetas=["Recolectado", "No alc.", "Restante"],
             cantidades=[f"{k['litros']:,.0f} L", "",
                         f"{max(k['esperado'] - k['litros'], 0):,.0f} L"])

    _kpi_col(c2, "🏪", "Locales Realizados",
             f"{k['exitosos_loc']:,} / {k['total_loc']:,}",
             k["pct_loc"], "#2d7a2d", key=f"{key_prefix}v2_donut_loc_{tab_nombre}",
             segmento_alerta=k["no_alc_loc"] * 100 // max(k["total_loc"], 1),
             leyenda=[("#2d7a2d", "Realizados"), ("#e53935", "No alc."), ("#e0e0e0", "Pendientes")],
             etiquetas=["Realizados", "No alc.", "Pendientes"],
             cantidades=[f"{k['exitosos_loc']:,} locales", f"{k['no_alc_loc']:,} locales",
                         f"{max(k['total_loc'] - k['exitosos_loc'] - k['no_alc_loc'], 0):,} locales"])

    _kpi_col(c3, "⭐", "Prioridad Alta",
             f"{k['exitosos_alta']:,} / {k['total_alta']:,}",
             k["pct_alta"], "#2d7a2d", key=f"{key_prefix}v2_donut_alta_{tab_nombre}",
             segmento_alerta=k["no_alc_alta"] * 100 // max(k["total_alta"], 1),
             leyenda=[("#2d7a2d", "Realizados"), ("#e53935", "No alc."), ("#e0e0e0", "Pendientes")],
             etiquetas=["Realizados", "No alc.", "Pendientes"],
             cantidades=[f"{k['exitosos_alta']:,} locales", f"{k['no_alc_alta']:,} locales",
                         f"{max(k['total_alta'] - k['exitosos_alta'] - k['no_alc_alta'], 0):,} locales"])

    _total_rec = k["exitosas"] + k["fallidas"]
    _kpi_col(c4, "✅", "Recolecciones",
             f"{k['exitosas']:,} exit. / {k['fallidas']:,} fall.",
             k["pct_exit"], "#28a745", key=f"{key_prefix}v2_donut_rec_{tab_nombre}",
             color_bg="#ef9a9a",
             segmento_alerta=k["fallidas_no_alc"] * 100 // max(_total_rec, 1),
             leyenda=[("#28a745", "Exitosas"), ("#e53935", "No alc."), ("#ef9a9a", "Otras fallidas")],
             etiquetas=["Exitosas", "No alc.", "Otras fallidas"],
             cantidades=[f"{k['exitosas']:,} visitas", f"{k['fallidas_no_alc']:,} visitas",
                         f"{k['fallidas'] - k['fallidas_no_alc']:,} visitas"])

    _kpi_col(c5, "🚦", "Rutas Cerradas",
             f"{k['cerradas']:,} / {k['n_rutas']:,}",
             k["pct_cerradas"], "#1a6b8a", key=f"{key_prefix}v2_donut_rut_{tab_nombre}",
             leyenda=[("#1a6b8a", "Cerradas"), ("#e0e0e0", "Abiertas")],
             etiquetas=["Cerradas", "No alc.", "Abiertas"],
             cantidades=[f"{k['cerradas']:,} rutas", "",
                         f"{max(k['n_rutas'] - k['cerradas'], 0):,} rutas"])

    st.divider()

    # Con flex-wrap, un card que cae solo a una fila nueva se estiraba a todo
    # el ancho (p. ej. Los Lagos en Global v3). flex-grow: 0 en las columnas
    # del grid: todas las cards quedan del MISMO ancho (su base de st.columns,
    # o el min-width responsive si la base es menor); la que no cabe baja sola
    # manteniendo el tamaño, como en una grilla de verdad.
    grid_key = f"{key_prefix}v2_cards_{tab_nombre}".replace(" ", "_")
    st.markdown(f"""
    <style>
        .st-key-{grid_key} div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
        .st-key-{grid_key} div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
            flex-grow: 0 !important;
        }}
        /* Las columnas anidadas (mini métricas dentro de cada card) sí crecen
           para repartirse el ancho del card como siempre */
        .st-key-{grid_key} div[data-testid="stColumn"] div[data-testid="stColumn"],
        .st-key-{grid_key} div[data-testid="column"] div[data-testid="column"] {{
            flex-grow: 1 !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # Global v2 espeja al Global v1: cards de centros de acopio, no de choferes
    if "GLOBAL" in tab_nombre.upper():
        centros = _datos_centros(
            df_rec,
            data_comp_centros if data_comp_centros is not None else data_comp,
            df_locales,
        )
        if not centros:
            st.info("Sin datos de centros de acopio para hoy.")
            return
        # Mismo criterio dinámico que las cards de choferes (Regiones/Santiago):
        # con 11 centros da 5 por fila (5/5/1) en vez de 6 (5/1/5 al envolver)
        n_c = len(centros)
        cols_por_fila = 6 if n_c > 12 else 5 if n_c > 6 else 4
        with st.container(key=grid_key):
            for i in range(0, len(centros), cols_por_fila):
                cols = st.columns(cols_por_fila)
                for j, c in enumerate(centros[i : i + cols_por_fila]):
                    with cols[j]:
                        _card_centro(c)
        return

    if data_comp.empty or "Chofer" not in data_comp.columns:
        st.info("Sin datos de choferes para hoy.")
        return

    choferes = _metricas_choferes(df_rec, df_locales, data_comp)
    # Mismo criterio dinámico que las cards v1: menos columnas si hay pocos choferes
    n = len(choferes)
    COLS = 6 if n > 12 else 5 if n > 6 else 4
    nav_param = "nav_carrusel_v3" if emoji_lado else "nav_carrusel_v2"
    with st.container(key=grid_key):
        for i in range(0, n, COLS):
            cols = st.columns(COLS)
            for j, ch in enumerate(choferes[i : i + COLS]):
                with cols[j]:
                    _card_chofer(ch, compact=compact, nav_param=nav_param)
