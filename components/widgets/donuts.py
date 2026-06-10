import streamlit as st
import pandas as pd
from connectors.sheets import cargar_datos_regiones
from components.helpers.data_prep import _cerrados_set, _litros, _pct
from components.widgets.tanque import C_VERDE, C_VERDE_OSC, C_ROJO, C_NO_ALC


def _donuts_global(df_rec: pd.DataFrame, df_locales: pd.DataFrame, data_comp: pd.DataFrame, tab_nombre: str = "Global"):
    # Rutas cerradas — antes de filtrar _litros para no perder choferes
    n_rutas = df_locales["Chofer"].nunique() if not df_locales.empty else 0
    cerradas = len(_cerrados_set(df_rec))
    pct_cerradas = round(cerradas / n_rutas * 100) if n_rutas > 0 else 0

    # "No alcanzamos a pasar" (Razon == 11) — calcular ANTES de filtrar por litros
    no_alc_loc = no_alc_alta = 0
    if not df_rec.empty and "Razon" in df_rec.columns and "idLocalSistema" in df_rec.columns:
        _df_na = df_rec[df_rec["Razon"] == 11].drop_duplicates(subset="idLocalSistema")
        no_alc_loc = len(_df_na)
        if not df_locales.empty and "Prioridad" in df_locales.columns and "ID_Local" in df_locales.columns:
            _alta_ids = set(
                df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
                ["ID_Local"].astype(int).tolist()
            )
            no_alc_alta = int(_df_na["idLocalSistema"].dropna().astype(int).isin(_alta_ids).sum())

    df_rec = _litros(df_rec)

    # Litros vs Esperado
    litros_hoy = df_rec["Litros"].sum() if not df_rec.empty else 0
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

    pct_lit = round(litros_hoy / prom_total * 100) if prom_total > 0 else 0

    # Locales
    total_loc = len(df_locales)
    realizados_loc = int((df_locales["Estado"] == "Realizado").sum()) if not df_locales.empty else 0
    exitosos_loc = max(0, realizados_loc - no_alc_loc)
    pct_loc = round(exitosos_loc / total_loc * 100) if total_loc > 0 else 0

    # Prioridad alta
    if not df_locales.empty and "Prioridad" in df_locales.columns:
        df_alta = df_locales[df_locales["Prioridad"].str.upper().str.contains("ALTA", na=False)]
        total_alta = len(df_alta)
        real_alta = int((df_alta["Estado"] == "Realizado").sum())
        exitosos_alta = max(0, real_alta - no_alc_alta)
        pct_alta = round(exitosos_alta / total_alta * 100) if total_alta > 0 else 0
    else:
        total_alta = real_alta = pct_alta = exitosos_alta = 0

    # Exitosas / Fallidas
    if not df_rec.empty and "idLocalSistema" in df_rec.columns:
        _dedup_vis = df_rec.drop_duplicates(subset="idLocalSistema")
        exitosas = int((_dedup_vis["Litros"] > 0).sum()) if "Litros" in _dedup_vis.columns else 0
        fallidas = int(_dedup_vis["Razon"].notna().sum()) if "Razon" in _dedup_vis.columns else 0
    else:
        exitosas = int((df_rec["Litros"] > 0).sum()) if not df_rec.empty and "Litros" in df_rec.columns else 0
        fallidas = int(df_rec["Razon"].notna().sum()) if not df_rec.empty and "Razon" in df_rec.columns else 0
    total_ef = exitosas + fallidas
    pct_exit = round(exitosas / total_ef * 100) if total_ef > 0 else 0

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
              f"{litros_hoy:,.0f} / {prom_total:,.0f} L",
              pct_lit, C_VERDE, "#e0e0e0", "Recolectado", "Restante", idx=0),
        _card("Locales Realizados", "🏪",
              f"{exitosos_loc:,} / {total_loc:,}",
              pct_loc, C_VERDE, "#e0e0e0", "Realizados", "Pendientes",
              no_alc=no_alc_loc, total=total_loc, realizados=exitosos_loc, idx=1),
        _card("Prioridad Alta", "⭐",
              f"{exitosos_alta:,} / {total_alta:,}",
              pct_alta, C_VERDE, "#e0e0e0", "Realizados", "Pendientes",
              no_alc=no_alc_alta, total=total_alta, realizados=exitosos_alta, idx=2),
        _card("Recolecciones", "✅",
              f"{exitosas:,} / {fallidas:,}",
              pct_exit, "#28a745", "#dc3545", "Exitosas", "Fallidas", idx=3),
        _card("Rutas Cerradas", "🚦",
              f"{cerradas:,} / {n_rutas:,}",
              pct_cerradas, "#1a6b8a", "#e0e0e0", "Cerradas", "Abiertas", idx=4),
    ])
    st.html(
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;padding:2px 0 6px">'
        f'{cards}</div>'
    )
