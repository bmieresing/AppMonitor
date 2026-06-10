import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from components.widgets.tanque import C_VERDE_OSC

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
    ahora = datetime.now(TZ)
    badge = (f'<span style="background:rgba(255,255,255,0.18);padding:3px 14px;'
             f'border-radius:12px;font-size:18px;font-weight:700;letter-spacing:2px;'
             f'margin-left:16px">{tab_nombre.upper()}</span>') if tab_nombre else ""

    col_banner, col_btn = st.columns([11, 1])
    with col_banner:
        st.markdown(f"""
        <div style="background:{C_VERDE_OSC};color:white;padding:8px 20px;border-radius:6px;
                    display:flex;justify-content:space-between;align-items:center">
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
    with col_btn:
        st.markdown(f"""
        <style>
          div[data-testid="column"]:last-child button[kind="secondary"] {{
            background:{C_VERDE_OSC} !important;
            color:white !important;
            border:1px solid rgba(255,255,255,0.35) !important;
            font-weight:600 !important;
          }}
        </style>
        """, unsafe_allow_html=True)
        if st.button("↺ Actualizar", use_container_width=True,
                     key=f"hdr_refresh_{key_prefix}{tab_nombre or 'main'}",
                     help="Recarga todos los datos desde MySQL, PostgreSQL y Google Sheets"):
            st.cache_data.clear()
            st.rerun()
    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)
