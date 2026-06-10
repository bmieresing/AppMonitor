from config import UMBRAL_VERDE, UMBRAL_AMARILLO

# Paleta del dashboard — usar estas constantes en lugar de literales hex
C_VERDE     = "#2d7a2d"
C_VERDE_OSC = "#1a472a"
C_VERDE_BG  = "#a8d5a2"
C_ROJO      = "#c0392b"
C_NO_ALC    = "#e53935"


def _color_pct(pct: int) -> tuple[str, str]:
    """Retorna (color_borde, color_relleno) según umbral de porcentaje."""
    if pct >= UMBRAL_VERDE:
        return C_VERDE, "rgba(45,122,45,0.22)"
    if pct >= UMBRAL_AMARILLO:
        return C_ROJO, "rgba(230,126,34,0.22)"
    return C_ROJO, "rgba(192,57,43,0.22)"


def _tanque(pct: int, emoji: str, label: str, sub: str, compact: bool = False, no_alc_pct: int = 0) -> str:
    """HTML de un indicador tipo tanque. compact=True para tarjetas de chofer (más pequeño).
    no_alc_pct: porcentaje adicional a mostrar en rojo encima del fill principal."""
    color, fill = _color_pct(pct)
    h = min(pct, 100)
    h_na = min(no_alc_pct, max(0, 100 - h))
    if compact:
        height, border, br = 52, 1, "4px 4px 6px 6px"
        shadow = "0 0 4px #fff,0 0 4px #fff"
        lbl_style = "font-size:12px;font-weight:700;color:#444;margin-top:2px"
        sub_style = "font-size:12px;font-weight:700;color:#333;margin-top:1px"
    else:
        height, border, br = 80, 2, "6px 6px 8px 8px"
        shadow = "0 0 6px #fff,0 0 6px #fff,0 0 6px #fff"
        lbl_style = "font-size:12px;font-weight:700;color:#444;margin-top:5px"
        sub_style = "font-size:12px;color:#999;margin-top:1px"
    na_layer = (
        f'<div style="position:absolute;bottom:{h}%;left:0;right:0;height:{h_na}%;background:rgba(229,57,53,0.5)"></div>'
    ) if h_na > 0 else ""
    return (
        f'<div style="text-align:center;flex:1">'
        f'<div style="position:relative;height:{height}px;border:{border}px solid {color};'
        f'border-radius:{br};overflow:hidden;background:#fafafa;margin:0 auto">'
        f'<div style="position:absolute;bottom:0;left:0;right:0;height:{h}%;background:{fill}"></div>'
        f'{na_layer}'
        f'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:1">'
        f'<span style="font-size:20px;font-weight:900;color:{color};text-shadow:{shadow}">{pct}%</span>'
        f'</div></div>'
        f'<div style="{lbl_style}">{emoji} {label}</div>'
        f'<div style="{sub_style}">{sub}</div>'
        f'</div>'
    )
