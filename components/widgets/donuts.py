import streamlit as st
import pandas as pd
from connectors.sheets import cargar_datos_regiones
from components.helpers.kpis import calcular_kpis
from components.widgets.tanque import C_VERDE, C_VERDE_OSC, C_NO_ALC


def _donuts_global(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame, tab_nombre: str = "Global"):
    # Promedio esperado según zona: Regiones sale del sheet, no de data_comp
    prom_stgo = data_comp["Prom"].sum() if not data_comp.empty else 0
    df_reg_data = cargar_datos_regiones()
    col_prom_reg = next((c for c in df_reg_data.columns if "PROM" in c.upper()), None)
    prom_reg = df_reg_data[col_prom_reg].sum() if (not df_reg_data.empty and col_prom_reg) else 0

    tab_up = tab_nombre.upper()
    if "SANTIAGO" in tab_up:
        prom_total = prom_stgo
    elif "REGION" in tab_up:
        prom_total = prom_reg
    else:
        prom_total = prom_stgo + prom_reg

    k = calcular_kpis(df_rec, df_locales, data_comp, prom_total=prom_total)

    compact = "REGION" in tab_up

    def _gradient(pct, color_a, color_b, no_alc=0, total=0, realizados=None):
        if total > 0 and realizados is not None:
            t = total or 1
            p1 = realizados / t * 100
            p2 = no_alc / t * 100
            return (
                f"conic-gradient(from -90deg,"
                f"{color_a} 0% {p1:.1f}%,"
                f"{C_NO_ALC} {p1:.1f}% {p1+p2:.1f}%,"
                f"{color_b} {p1+p2:.1f}% 100%)"
            )
        return (
            f"conic-gradient(from -90deg,"
            f"{color_a} 0% {pct}%,"
            f"{color_b} {pct}% 100%)"
        )

    def _card(titulo, emoji, valor, pct, color_a, color_b, label_a, label_b,
              no_alc=0, total=0, realizados=None, idx=0):
        if compact:
            emoji_px, donut_px, hole_px, pct_px, pad, val_px = 44, 86, 58, 16, "12px 14px 10px", "18px"
        else:
            emoji_px, donut_px, hole_px, pct_px, pad, val_px = 72, 130, 88, 22, "22px 20px 18px", "28px"

        gradient = _gradient(pct, color_a, color_b, no_alc, total, realizados)
        no_alc_legend = (
            f'<span><span style="color:{C_NO_ALC}">&#9679;</span> No alc.</span>'
        ) if no_alc > 0 else ""

        return f"""
        <div style="background:#fff;border:1px solid #e0e8e0;border-radius:14px;
                    padding:{pad};box-shadow:0 2px 12px rgba(0,0,0,0.07);text-align:center">
            <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:10px">
                <span style="font-size:{emoji_px}px;line-height:1">{emoji}</span>
                <div style="position:relative;width:{donut_px}px;height:{donut_px}px;flex-shrink:0">
                    <div style="width:{donut_px}px;height:{donut_px}px;border-radius:50%;background:{gradient}"></div>
                    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
                        <div style="width:{hole_px}px;height:{hole_px}px;border-radius:50%;background:#fff;
                                    display:flex;align-items:center;justify-content:center">
                            <span style="font-size:{pct_px}px;font-weight:900;color:{C_VERDE_OSC}">{pct}%</span>
                        </div>
                    </div>
                </div>
            </div>
            <div style="font-size:12px;font-weight:700;color:#999;text-transform:uppercase;
                        letter-spacing:1.5px;margin-bottom:6px">{titulo}</div>
            <div style="font-size:{val_px};font-weight:700;color:{C_VERDE_OSC};
                        line-height:1.1;margin-bottom:4px">{valor}</div>
            <div style="display:flex;gap:10px;justify-content:center;font-size:12px;
                        color:#888;margin-top:6px;flex-wrap:wrap">
                <span><span style="color:{color_a}">&#9679;</span> {label_a}</span>
                {no_alc_legend}
                <span><span style="color:{color_b}">&#9679;</span> {label_b}</span>
            </div>
        </div>"""

    cards = "".join([
        _card("Litros vs Esperado", "💧",
              f"{k['litros']:,.0f} / {k['esperado']:,.0f} L",
              k["pct_lit"], C_VERDE, "#e0e0e0", "Recolectado", "Restante", idx=0),
        _card("Locales Realizados", "🏪",
              f"{k['exitosos_loc']:,} / {k['total_loc']:,}",
              k["pct_loc"], C_VERDE, "#e0e0e0", "Realizados", "Pendientes",
              no_alc=k["no_alc_loc"], total=k["total_loc"], realizados=k["exitosos_loc"], idx=1),
        _card("Prioridad Alta", "⭐",
              f"{k['exitosos_alta']:,} / {k['total_alta']:,}",
              k["pct_alta"], C_VERDE, "#e0e0e0", "Realizados", "Pendientes",
              no_alc=k["no_alc_alta"], total=k["total_alta"], realizados=k["exitosos_alta"], idx=2),
        _card("Recolecciones", "✅",
              f"{k['exitosas']:,} / {k['fallidas']:,}",
              k["pct_exit"], "#28a745", "#ef9a9a", "Exitosas", "Fallidas",
              no_alc=k["fallidas_no_alc"], total=k["exitosas"] + k["fallidas"],
              realizados=k["exitosas"], idx=3),
        _card("Rutas Cerradas", "🚦",
              f"{k['cerradas']:,} / {k['n_rutas']:,}",
              k["pct_cerradas"], "#1a6b8a", "#e0e0e0", "Cerradas", "Abiertas", idx=4),
    ])
    st.html(
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;padding:2px 0 6px">'
        f'{cards}</div>'
    )
