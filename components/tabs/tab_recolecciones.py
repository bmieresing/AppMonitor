import streamlit as st
import pandas as pd
from connectors.mysql import cargar_estado_locales
from connectors.postgres import cargar_empleados

_EXCLUIR_LITROS = {"Latas", "Desengrasante"}

_PALETA = [
    ("#1565c0", "#e3f2fd"),  # azul
    ("#2e7d32", "#e8f5e9"),  # verde
    ("#6a1b9a", "#f3e5f5"),  # púrpura
    ("#e65100", "#fff3e0"),  # naranja
    ("#00695c", "#e0f2f1"),  # teal
    ("#4527a0", "#ede7f6"),  # índigo
    ("#c62828", "#ffebee"),  # rojo
    ("#558b2f", "#f9fbe7"),  # lima
]


def _semaforo(pct: int) -> str:
    if pct >= 80:
        return "#2d7a2d"
    if pct >= 50:
        return "#e67e22"
    return "#c0392b"


def _panel_productos(df_rec: pd.DataFrame):
    if df_rec.empty or "Producto" not in df_rec.columns:
        return

    prod_totales = (
        df_rec[df_rec["Litros"] > 0]
        .groupby("Producto")["Litros"]
        .agg(total="sum", visitas="count")
        .sort_values("total", ascending=False)
        .reset_index()
    )
    if prod_totales.empty:
        st.info("Sin recolecciones con litros aún.")
        return

    total_global = float(prod_totales["total"].sum())
    total_aceite = float(
        prod_totales.loc[~prod_totales["Producto"].isin(_EXCLUIR_LITROS), "total"].sum()
    )

    col_met, col_vis = st.columns([1, 4])
    with col_met:
        st.metric("Total litros hoy", f"{total_aceite:,.0f} L",
                  delta=f"{int(prod_totales['visitas'].sum())} visitas totales",
                  delta_color="off")

    chips = ""
    for i, row in prod_totales.iterrows():
        col_t, col_bg = _PALETA[i % len(_PALETA)]
        pct = row["total"] / total_global * 100
        chips += (
            f'<div style="flex:1;min-width:130px;background:{col_bg};'
            f'border:1px solid {col_t}44;border-radius:10px;padding:12px 16px;text-align:center">'
            f'<div style="font-size:12px;font-weight:700;color:{col_t};letter-spacing:.4px;margin-bottom:4px">'
            f'{str(row["Producto"]).upper()}</div>'
            f'<div style="font-size:26px;font-weight:900;color:{col_t};line-height:1.1">'
            f'{row["total"]:,.0f} L</div>'
            f'<div style="font-size:12px;color:{col_t}99;margin-top:3px">'
            f'{int(row["visitas"])} visitas · {pct:.1f}%</div>'
            f'<div style="background:{col_t}22;border-radius:4px;height:5px;margin-top:7px">'
            f'<div style="background:{col_t};width:{pct:.0f}%;height:100%;border-radius:4px"></div>'
            f'</div>'
            f'</div>'
        )

    st.html(
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;padding:2px 0 4px">'
        f'{chips}</div>'
    )


def _cards_choferes(df_rec: pd.DataFrame):
    empleados = cargar_empleados()
    mapa = empleados.set_index("id")["nombre"] if not empleados.empty else pd.Series(dtype=str)

    df = df_rec.copy() if not df_rec.empty else pd.DataFrame()
    if not df.empty and "NombreChofer" not in df.columns and "Chofer" in df.columns:
        df["NombreChofer"] = df["Chofer"].map(mapa).fillna(df["Chofer"].astype(str))

    df_loc = cargar_estado_locales()
    if not df_loc.empty and "Chofer" in df_loc.columns:
        df_loc = df_loc.copy()
        df_loc["NombreChofer"] = df_loc["Chofer"].map(mapa).fillna(df_loc["Chofer"].astype(str))
        if "Prioridad" in df_loc.columns:
            df_loc["Prio"] = df_loc["Prioridad"].str.strip().str.capitalize()
        else:
            df_loc["Prio"] = "Normal"

    litros_ch: dict[str, float] = {}
    prod_ch: dict[str, dict] = {}
    if not df.empty and "NombreChofer" in df.columns:
        for nombre, grp in df[df["Litros"] > 0].groupby("NombreChofer"):
            litros_ch[nombre] = float(grp["Litros"].sum())
            if "Producto" in df.columns:
                prod_ch[nombre] = (
                    grp.groupby("Producto")["Litros"].sum()
                    .sort_values(ascending=False)
                    .to_dict()
                )

    loc_ch: dict[str, dict] = {}
    if not df_loc.empty and "NombreChofer" in df_loc.columns:
        for (nombre, prio), grp in df_loc.groupby(["NombreChofer", "Prio"]):
            if nombre not in loc_ch:
                loc_ch[nombre] = {}
            loc_ch[nombre][prio] = (int((grp["Estado"] == "Realizado").sum()), len(grp))

    todos = sorted(
        set(list(litros_ch.keys()) + list(loc_ch.keys())),
        key=lambda n: litros_ch.get(n, 0), reverse=True,
    )
    if not todos:
        st.info("Sin datos de choferes para hoy.")
        return

    max_lit = max(litros_ch.values(), default=1)

    prods_orden = sorted(
        {p for prods in prod_ch.values() for p in prods},
        key=lambda p: -sum(prods.get(p, 0) for prods in prod_ch.values()),
    )
    col_prod = {p: _PALETA[i % len(_PALETA)] for i, p in enumerate(prods_orden)}

    cards = []
    for nombre in todos:
        total = litros_ch.get(nombre, 0)
        pct_lit = int(total / max_lit * 100) if max_lit > 0 and total > 0 else 0
        color_lit = _semaforo(pct_lit) if total > 0 else "#9e9e9e"

        barra = (
            f'<div style="background:#e0e0e0;border-radius:3px;height:7px;margin:5px 0 7px">'
            f'<div style="background:{color_lit};width:{pct_lit}%;height:100%;border-radius:3px"></div>'
            f'</div>'
        )

        prods_html = ""
        for prod, lit in prod_ch.get(nombre, {}).items():
            col_t, col_bg = col_prod.get(prod, ("#555", "#f0f0f0"))
            prods_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">'
                f'<span style="font-size:12px;background:{col_bg};color:{col_t};padding:1px 5px;'
                f'border-radius:3px;font-weight:600;max-width:65%;overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap">{prod}</span>'
                f'<span style="font-size:12px;color:#333;font-weight:700">{lit:,.0f} L</span>'
                f'</div>'
            )

        locs_html = ""
        for prio, emoji in [("Normal", "📋")]:
            if prio in loc_ch.get(nombre, {}):
                r, t = loc_ch[nombre][prio]
                pct = int(r / t * 100) if t > 0 else 0
                c = _semaforo(pct)
                w = min(pct, 100)
                locs_html += (
                    f'<div style="margin-bottom:3px">'
                    f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#555;margin-bottom:1px">'
                    f'<span>{emoji} {prio}</span>'
                    f'<span style="color:{c};font-weight:700">{r}/{t}</span></div>'
                    f'<div style="background:#e0e0e0;border-radius:2px;height:4px">'
                    f'<div style="background:{c};width:{w}%;height:100%;border-radius:2px"></div>'
                    f'</div></div>'
                )

        sep_prods = '<div style="border-top:1px solid #e8e8e8;margin:6px 0 5px"></div>' if prods_html else ""
        sep_locs = '<div style="border-top:1px solid #e8e8e8;margin:6px 0 5px"></div>' if locs_html else ""

        cards.append(
            f'<div style="border:1px solid {color_lit}44;border-top:3px solid {color_lit};'
            f'border-radius:7px;padding:9px 11px;background:#fafafa">'
            f'<div style="font-weight:700;font-size:12px;color:#1a2e1a;margin-bottom:2px;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{nombre}">{nombre}</div>'
            f'<div style="font-size:20px;font-weight:900;color:{color_lit};line-height:1">'
            f'{total:,.0f} L</div>'
            f'{barra}'
            f'{sep_prods}{prods_html}'
            f'{sep_locs}{locs_html}'
            f'</div>'
        )

    grid = "".join(cards)
    st.html(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:2px 0">'
        f'{grid}</div>'
    )


def mostrar_tab_recolecciones(df_rec: pd.DataFrame):
    if df_rec.empty:
        st.info("Sin datos de recolecciones para hoy.")
        return

    _panel_productos(df_rec)
    st.divider()
    _cards_choferes(df_rec)
