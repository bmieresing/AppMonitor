# Estado de las cargas de datos, a nivel de proceso (variable de módulo):
# las funciones cacheadas solo corren en cache-miss, así que esto registra
# las recargas REALES contra las fuentes. No usa session_state (es por
# sesión) ni st.error dentro de funciones cacheadas (st.cache_data
# re-reproduce los elementos visuales cacheados en cada rerun — así nacía
# la alerta que no se podía cerrar).
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import TTL_DATOS_SEG, RERUN_SEG

TZ = ZoneInfo("America/Santiago")

_lock = threading.Lock()

_estado = {
    "ultima_falla": None,
    "detalle_falla": "",
    "ultimo_ciclo": None,    # hora del último ciclo CONFIRMADO (todas las tablas OK)
    "ciclo_fallas": 0,       # fallas acumuladas en el intento de ciclo en curso
    "ciclo_ok": False,       # True = el ciclo vigente está confirmado (commit)
    "ciclo_en_curso": None,  # hora de inicio del intento en curso, o None
    "motivo_proximo": None,  # texto para el log del próximo ciclo (botón ↺)
}


def ciclo_vencido() -> bool:
    """True si toca un nuevo ciclo de datos (cada TTL_DATOS_SEG desde el
    último ciclo CONFIRMADO). Si un ciclo falla, no se marca y esto sigue
    True → el próximo rerun (60 s) reintenta el ciclo completo."""
    u = _estado["ultimo_ciclo"]
    return u is None or (datetime.now(TZ) - u).total_seconds() >= TTL_DATOS_SEG


def tomar_ciclo() -> bool:
    """Toma el ciclo de forma ATÓMICA: True solo para el run que debe
    ejecutarlo. Evita ciclos duplicados cuando dos reruns/sesiones coinciden
    (p. ej. botón ↺ + tick de 60 s u otra pestaña abierta): el segundo ve el
    ciclo en curso y sigue sirviendo el último confirmado. Mientras no se
    confirme, los loaders sirven la versión del último ciclo completo."""
    with _lock:
        en_curso = _estado["ciclo_en_curso"]
        # Ciclo colgado (un run murió sin confirmar): se libera a los 120 s
        if en_curso and (datetime.now(TZ) - en_curso).total_seconds() < 120:
            return False
        if not ciclo_vencido():
            return False
        ahora = datetime.now(TZ)
        _estado["ciclo_en_curso"] = ahora
        _estado["ciclo_fallas"] = 0
        _estado["ciclo_ok"] = False
        motivo = _estado["motivo_proximo"] or "recarga automática (ciclo de 5 min)"
        _estado["motivo_proximo"] = None
        print(f"[{ahora:%H:%M:%S}] ── ciclo de datos: {motivo} ──", flush=True)
        return True


def confirmar_ciclo() -> bool:
    """Tras cargar todas las tablas: commit todo-o-nada. Solo si NINGUNA
    falló se confirma el ciclo (los loaders pasan a servir lo nuevo)."""
    ahora = datetime.now(TZ)
    _estado["ciclo_ok"] = _estado["ciclo_fallas"] == 0
    _estado["ciclo_en_curso"] = None
    if _estado["ciclo_ok"]:
        _estado["ultimo_ciclo"] = ahora
        print(f"[{ahora:%H:%M:%S}] ── ciclo confirmado ──", flush=True)
    else:
        print(f"[{ahora:%H:%M:%S}] ── ciclo con fallas: se mantiene el anterior, "
              f"reintento en {RERUN_SEG} s ──", flush=True)
    return _estado["ciclo_ok"]


def ciclo_ok() -> bool:
    return _estado["ciclo_ok"]


def intento_fallido() -> bool:
    """True si el intento de ciclo en curso ya registró alguna falla y aún no
    hay ciclo confirmado: el resto de los loaders ni consulta su fuente
    (fail-fast) — se sirve el último ciclo confirmado y el próximo rerun
    reintenta el ciclo entero."""
    return _estado["ciclo_fallas"] > 0 and not _estado["ciclo_ok"]


def forzar_ciclo():
    """Para el botón ↺: invalida el ciclo vigente — el próximo run ejecuta
    un ciclo completo (clear + recarga de todo + commit)."""
    _estado["ultimo_ciclo"] = None
    _estado["motivo_proximo"] = "botón ↺ presionado"


def hora_ciclo() -> datetime:
    """Hora del último ciclo confirmado — es LA fecha de actualización que ven
    los headers. No avanza si el ciclo falló (los datos en pantalla siguen
    siendo los del ciclo anterior)."""
    return _estado["ultimo_ciclo"] or datetime.now(TZ)


def registrar_carga(fuente: str, tabla: str, filas: int):
    """Log a consola de cada recarga real (cache-miss) con fuente y tabla."""
    print(f"[{datetime.now(TZ):%H:%M:%S}] recarga {fuente} · {tabla}: {filas} filas",
          flush=True)


def registrar_falla(fuente: str, tabla: str, error: Exception):
    ahora = datetime.now(TZ)
    _estado["ultima_falla"] = ahora
    _estado["detalle_falla"] = f"{fuente} · {tabla}: {error}"
    _estado["ciclo_fallas"] += 1
    print(f"[{ahora:%H:%M:%S}] FALLA {fuente} · {tabla}: {error}", flush=True)


def falla_reciente() -> datetime | None:
    """Hora de la última falla si pertenece al ciclo de datos vigente
    (TTL + un rerun de margen). Si pasa un ciclo completo sin fallas
    nuevas, vuelve None y el marcador rojo desaparece solo."""
    f = _estado["ultima_falla"]
    if f and datetime.now(TZ) - f <= timedelta(seconds=TTL_DATOS_SEG + RERUN_SEG):
        return f
    return None


def detalle_falla() -> str:
    return _estado["detalle_falla"]
