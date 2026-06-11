# Constantes compartidas del dashboard. Única fuente de verdad:
# importar desde acá, no redefinir en cada módulo.

# Productos que no cuentan como litros de aceite
EXCLUIR_LITROS = {"Latas", "Desengrasante"}

# Semáforo general (% locales realizados, % litros, % prioridad alta)
UMBRAL_VERDE = 80     # >= verde
UMBRAL_AMARILLO = 50  # >= amarillo y < verde; bajo esto, rojo

# Semáforo de la tabla comparativa litros vs esperado (promedio 3M)
UMBRAL_COMP_VERDE = 100
UMBRAL_COMP_AMARILLO = 70

# Auto-avance de carruseles (segundos)
INTERVALO_CARRUSEL_SEG = 10
INTERVALO_ZONAS_SEG = 20

# Ciclo de datos: TTL de las cachés de los loaders (cuándo VENCEN los datos)
TTL_DATOS_SEG = 300
# Rerun de la página: debe ser << TTL para refrescar apenas venza una caché.
# Con rerun == TTL el desfase podía llegar a ~2x TTL (rerun justo antes del
# vencimiento). El rerun NO consulta las bases: las cachés mandan.
RERUN_SEG = 60
