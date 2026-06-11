import html
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from components.helpers.data_prep import hora_actualizacion
from components.widgets.tanque import C_VERDE_OSC
from connectors.estado_carga import falla_reciente, detalle_falla, forzar_ciclo

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
        div[data-testid="stMetric"] label { font-size: 12px !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
            font-size: 12px !important;
            color: #444 !important;
        }
        div[data-testid="stMetricDelta"] svg {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)


def _header(tab_nombre: str = "", key_prefix: str = ""):
    """Banner verde como container nativo (clase .st-key-*): el botón ↺ vive
    dentro del banner, en el lugar que ocupaba el badge EN VIVO."""
    ahora = hora_actualizacion()
    badge = (f'<span style="background:rgba(255,255,255,0.18);padding:3px 14px;'
             f'border-radius:12px;font-size:18px;font-weight:700;letter-spacing:2px;'
             f'margin-left:16px">{tab_nombre.upper()}</span>') if tab_nombre else ""

    ckey = f"hdr_{key_prefix}{tab_nombre or 'main'}".replace(" ", "_")
    st.markdown(f"""
    <style>
        .st-key-{ckey} {{
            background: {C_VERDE_OSC};
            border-radius: 6px;
            padding: 8px 20px;
        }}
        .st-key-{ckey} button {{
            background: rgba(255,255,255,0.12) !important;
            color: white !important;
            border: 1px solid rgba(255,255,255,0.35) !important;
            font-weight: 600 !important;
            min-height: 26px !important;
            height: 26px !important;
            padding: 0 9px !important;
            font-size: 13px !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    with st.container(key=ckey):
        # Botón chico pegado a la fecha (gap small + columna angosta)
        c_tit, c_ts, c_btn = st.columns([9.3, 2.2, 0.5], vertical_alignment="center", gap="small")
        with c_tit:
            st.markdown(
                f'<span style="font-size:16px;font-weight:700;letter-spacing:1px;color:white">'
                f'DASHBOARD OPERACIONAL &ndash; RECOLECCIÓN DE ACEITE{badge}</span>',
                unsafe_allow_html=True,
            )
        with c_ts:
            # Si hubo una falla de carga en el ciclo vigente, hora en rojo claro
            # al lado de la fecha (legible sobre el banner verde); el detalle
            # queda en el tooltip (title)
            falla = falla_reciente()
            falla_html = (
                f' <span style="color:#ff8a80;font-weight:700" '
                f'title="{html.escape(detalle_falla())}">⚠ falla {falla.strftime("%H:%M")}</span>'
            ) if falla else ""
            st.markdown(
                f'<div style="text-align:right;font-size:12px;color:rgba(255,255,255,0.85);'
                f'line-height:1.4">Última actualización<br>'
                f'{ahora.strftime("%d/%m/%Y %H:%M")}{falla_html}</div>',
                unsafe_allow_html=True,
            )
        with c_btn:
            if st.button("↺",
                         key=f"hdr_refresh_{key_prefix}{tab_nombre or 'main'}",
                         help="Recarga todos los datos desde MySQL, PostgreSQL y Google Sheets"):
                forzar_ciclo()  # el próximo run ejecuta un ciclo completo
                st.rerun()
    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)
