# DATAFRAMES.md — Inventario de dataframes

Documento generado a partir del código real en `App Monitor/`. Cada entrada indica origen, query SQL exacta (cuando aplica), transformaciones y columnas finales. Lo que no pudo verificarse en el código está marcado **por confirmar**.

> **Refactor 2026-06:** las comparativas `_dc_stgo` / `_dc_reg` / `data_comp_todos` se
> calculan UNA sola vez en app.py y se pasan a todas las vistas (se eliminaron los
> recálculos `_dc_stgo_v2` y los internos de los tabs). Los KPIs globales se calculan en
> `components/helpers/kpis.py`. Las constantes (EXCLUIR_LITROS, umbrales, intervalos)
> viven en `config.py`. Los conectores manejan errores de conexión: si una fuente está
> caída muestran `st.error` y retornan DataFrame vacío (la app no se cae). Las
> referencias a números de línea de app.py pueden estar desplazadas tras el refactor.

---

## Índice

| # | Variable | Categoría | Archivo donde se crea |
|---|----------|-----------|-----------------------|
| 1 | `cargar_recolecciones()` | Conector MySQL | `connectors/mysql.py` |
| 2 | `cargar_estado_locales()` | Conector MySQL | `connectors/mysql.py` |
| 3 | `cargar_emergencias()` | Conector MySQL | `connectors/mysql.py` |
| 4 | `cargar_usuarios_vehiculos()` | Conector MySQL | `connectors/mysql.py` |
| 5 | `cargar_empleados()` | Conector PostgreSQL | `connectors/postgres.py` |
| 6 | `cargar_productos()` | Conector PostgreSQL | `connectors/postgres.py` |
| 7 | `cargar_razones()` | Conector PostgreSQL | `connectors/postgres.py` |
| 8 | `cargar_vehiculos()` | Conector PostgreSQL | `connectors/postgres.py` |
| 9 | `cargar_datos()` / `df_sheets` | Conector Google Sheets | `connectors/sheets.py` |
| 10 | `cargar_datos_regiones()` / `df_regiones` | Conector Google Sheets | `connectors/sheets.py` |
| 11 | `df_rec` | Derivado — app.py | `app.py` |
| 12 | `df_veh` | Derivado — app.py (temporal) | `app.py` |
| 13 | `df_uv` | Derivado — app.py (temporal) | `app.py` |
| 14 | `df_rec_stgo` | Derivado — app.py | `app.py` |
| 15 | `df_rec_reg` | Derivado — app.py | `app.py` |
| 16 | `_dc_stgo` | Derivado — app.py | `app.py` |
| 17 | `_dc_reg` | Derivado — app.py | `app.py` |
| 18 | `data_comp_todos` | Derivado — app.py | `app.py` |
| 19 | ~~`_dc_stgo_v2`~~ (eliminado — se reusa `_dc_stgo`) | — | — |
| 20 | `prom_df` | Intermedio — `_preparar_datos()` | `components/helpers/data_prep.py` |
| 21 | `chofer_por_patente` | Intermedio — `_preparar_datos()` | `components/helpers/data_prep.py` |
| 22 | `litros_por_patente` | Intermedio — `_preparar_datos()` | `components/helpers/data_prep.py` |
| 23 | `prom_s` | Intermedio — `_preparar_datos_regiones()` | `components/helpers/data_prep.py` |
| 24 | `lit_s` | Intermedio — `_preparar_datos_regiones()` | `components/helpers/data_prep.py` |
| 25 | `df_locales` | Interno — tabs | `tab_global.py`, `tab_zonas.py`, `tab_carrusel.py`, `tab_v2.py` |
| 26 | `data_comp` (interno) | Interno — tabs | `tab_global.py`, `tab_zonas.py` |
| 27 | `_data_comp_reg` | Interno — tabs | `app.py` (tab_reg), `tab_carrusel_zonas.py` |
| 28 | `df_emerg_all` | Interno — tab_carrusel | `components/tabs/tab_carrusel.py` |
| 29 | `df_loc_ch` | Interno — tab_carrusel | `components/tabs/tab_carrusel.py` |
| 30 | `df_c` | Interno — tab_carrusel | `components/tabs/tab_carrusel.py` |
| 31 | `razon_counts` | Interno — tab_carrusel | `components/tabs/tab_carrusel.py` |
| 32 | `df_razones` | Interno — tab_rendimiento | `components/tabs/tab_rendimiento.py` |
| 33 | `df_loc` | Interno — tab_recolecciones | `components/tabs/tab_recolecciones.py` |

---

## Categoría 1: Conectores — datos crudos de fuentes externas

Los conectores están decorados con `@st.cache_data`. El valor del `ttl` indica cada cuánto se refresca la caché.

---

### 1. `cargar_recolecciones()`
**Archivo:** `connectors/mysql.py`  
**TTL caché:** 300 s (5 min)  
**Variable donde se guarda:**
- No tiene nombre propio en `app.py` — se pasa directamente a `resolver_recolecciones(cargar_recolecciones())`

**Base de datos:** MySQL (`appsheet_db`, por confirmar el nombre exacto — viene de `st.secrets["mysql"]["database"]`)  
**Query:**
```sql
SELECT * FROM VistaMonitor WHERE Fecha = '<hoy>'
```
Donde `<hoy>` es la fecha actual en zona horaria `America/Santiago` (`YYYY-MM-DD`).

**Transformaciones:**
1. `Litros` → `pd.to_numeric(..., errors="coerce").fillna(0)` — convierte a float, reemplaza nulos con 0

**Columnas finales:** Todas las de `VistaMonitor` (por confirmar — `SELECT *`).  
Columnas confirmadas como usadas por el resto de la app: `Fecha`, `Litros`, `Chofer`, `Peoneta1`, `Peoneta2`, `Patente`, `idProducto`, `idLocalSistema`, `Razon`, `Emergencia`, `FechaObservacion`.

**Depende de:** —

---

### 2. `cargar_estado_locales()`
**Archivo:** `connectors/mysql.py`  
**TTL caché:** 60 s (1 min — refresco frecuente para ver el estado en tiempo real)  
**Variable donde se guarda:**
- `df_locales` — en `tab_global.py`, `tab_zonas.py`, `tab_v2.py` (ya filtrado por `choferes_filter`)
- `df_locales_all` — en `tab_carrusel.py` (sin filtrar; luego se filtra a `df_loc_ch` por chofer activo)
- `df_loc` — en `cards.py` (`_cards_choferes_tanque`) y en `tab_recolecciones.py` (`_cards_choferes`)

**Base de datos:** MySQL  
**Query:**
```sql
SELECT lr.Ruta        AS NombreRuta,
       lr.ID_Local,
       lr.Local,
       lr.Estado,
       lr.Prioridad,
       lr.CentroAcopio,
       u.Chofer
FROM   LocalesRuta lr
JOIN   Usuarios u ON lr.Mail_Oficial = u.Correo
WHERE  lr.Fecha_Registro = '<hoy>'
```

**Transformaciones:** ninguna posterior al query.

**Columnas finales:** `NombreRuta`, `ID_Local`, `Local`, `Estado`, `Prioridad`, `CentroAcopio`, `Chofer`

**Depende de:** —

---

### 3. `cargar_emergencias()`
**Archivo:** `connectors/mysql.py`  
**TTL caché:** 300 s  
**Variable donde se guarda:**
- `df_emerg_all` — en `tab_carrusel.py` (`mostrar_carrusel`)

**Base de datos:** MySQL  
**Query:**
```sql
SELECT id_local, chofer_asignado
FROM   Emergencias
WHERE  fecha_asignacion_emergencia = '<hoy>'
  AND  chofer_asignado IS NOT NULL
```

**Transformaciones:** ninguna.

**Columnas finales:** `id_local`, `chofer_asignado`

**Depende de:** —

---

### 4. `cargar_usuarios_vehiculos()`
**Archivo:** `connectors/mysql.py`  
**TTL caché:** 3600 s (1 hora — cambia poco)  
**Variable donde se guarda:**
- `df_uv` — en `app.py` (para calcular `choferes_stgo` / `choferes_reg`)
- `usuarios` — en `data_prep.py` (`_preparar_datos`, para cruzar Patente → NombreChofer)
- `usuarios` — en `tab_parametros.py` (expander de diagnóstico)

**Base de datos:** MySQL  
**Query:**
```sql
SELECT Vehiculo, Chofer
FROM   Usuarios
WHERE  Vehiculo IS NOT NULL
  AND  Chofer IS NOT NULL
```

**Transformaciones:** ninguna.

**Columnas finales:** `Vehiculo` (ID del vehículo), `Chofer` (ID del chofer)

**Depende de:** —

---

### 5. `cargar_empleados()`
**Archivo:** `connectors/postgres.py`  
**TTL caché:** 3600 s  
**Variable donde se guarda:**
- `empleados` — en `id_resolver.py` (`resolver_recolecciones`)
- `empleados` — en `data_prep.py` (`_preparar_datos`)
- `empleados` — en `tab_recolecciones.py` (`_cards_choferes`)
- `empleados_pg` — en `tab_parametros.py` (expander de diagnóstico)
- Implícitamente vía `_mapa_empleados()` en `cards.py` y `tab_v2.py` (retorna una `pd.Series` `id → nombre`, no se guarda como df)

**Base de datos:** PostgreSQL (`rendering_db2`)  
**Query:**
```sql
SELECT id, name, last_name
FROM   personnel_employee
WHERE  active = TRUE
```

**Transformaciones:**
1. `nombre = name + " " + last_name` — concatenación de nombre y apellido
2. Se retorna solo `["id", "nombre"]`

**Columnas finales:** `id`, `nombre`

**Depende de:** —

---

### 6. `cargar_productos()`
**Archivo:** `connectors/postgres.py`  
**TTL caché:** 3600 s  
**Variable donde se guarda:**
- `productos` — en `id_resolver.py` (`resolver_recolecciones`), renombra columna `name → nombre`
- `productos` — en `tab_carrusel.py` (`mostrar_carrusel`), para mapear `idProducto → nombre`

**Base de datos:** PostgreSQL  
**Query:**
```sql
SELECT id, name
FROM   products_product
WHERE  active = TRUE
```

**Transformaciones:** ninguna.

**Columnas finales:** `id`, `name`

**Depende de:** —

---

### 7. `cargar_razones()`
**Archivo:** `connectors/postgres.py`  
**TTL caché:** 3600 s  
**Variable donde se guarda:**
- `df_razones` — en `tab_rendimiento.py` (`mostrar_rendimiento`)
- `razones_df` — en `tab_carrusel.py` (`mostrar_carrusel`)
- `df_razones` — en `tab_carrusel.py` (`_razones_fallo`)

**Base de datos:** PostgreSQL  
**Query:**
```sql
SELECT id, name
FROM   visits_visitfailurereason
WHERE  active = TRUE
```

**Transformaciones:** ninguna.

**Columnas finales:** `id`, `name`

**Depende de:** —

---

### 8. `cargar_vehiculos()`
**Archivo:** `connectors/postgres.py`  
**TTL caché:** 3600 s  
**Variable donde se guarda:**
- `df_veh` — en `app.py` (para calcular `vehiculos_stgo`)
- `vehiculos` — en `data_prep.py` (`_preparar_datos`), para cruzar ID → patente
- `vehiculos` — en `id_resolver.py` (`resolver_recolecciones`), renombra columna `plate → nombre`
- `vehiculos_pg` — en `tab_parametros.py` (expander de diagnóstico)

**Base de datos:** PostgreSQL  
**Query:**
```sql
SELECT id, plate
FROM   visits_vehicle
WHERE  active = TRUE
```

**Transformaciones:** ninguna.

**Columnas finales:** `id`, `plate`

**Depende de:** —

---

### 9. `cargar_datos()`
**Archivo:** `connectors/sheets.py`  
**TTL caché:** 300 s  
**Variable donde se guarda:**
- `df_sheets` — en `app.py` (variable principal, se pasa a tabs)

**Fuente:** Google Sheets — hoja `sheet_name` (configurable en `st.secrets["sheets"]`), rango `A:Z`  
**Transformaciones:**
1. Toma todas las filas a partir de la fila 2 (fila 1 = cabecera)
2. Reemplaza `"#N/A"` y `""` por `None`
3. Filtra columnas: solo las que contienen alguna de estas palabras clave (case-insensitive): `FECHA`, `RUTA`, `CHOFER`, `PEONETA1`, `PEONETA2`, `PATENTE`, `PROM RUTA`
4. Filtra filas: solo las cuya columna FECHA coincide con la fecha de hoy en zona `America/Santiago`
5. Excluye filas donde la columna CHOFER contiene `"TOTALES"` (fila de totales del sheet)

**Columnas finales:** Las que existen en el sheet y cuyos nombres contienen las palabras clave. Nombres exactos: **por confirmar** (dependen del sheet real). Columnas conocidas como usadas por la app: la que contiene `"PATENTE"` y la que contiene `"PROM"` (detectadas por búsqueda de substring).

**Depende de:** —

---

### 10. `cargar_datos_regiones()`
**Archivo:** `connectors/sheets.py`  
**TTL caché:** 300 s  
**Variable donde se guarda:**
- `df_regiones` — en `app.py` (variable principal, se pasa a tabs)
- `df_reg_data` — en `donuts.py` (`_donuts_global`), para obtener el promedio esperado de Regiones
- `df_reg` — en `cards.py` (`_desempeno_centros`), para obtener el promedio por zona

**Fuente:** Google Sheets — hoja `sheet_name_regiones` (default `"Control Regiones"`), rango `A:F`  
**Transformaciones:**
1. Toma todas las filas a partir de la fila 2 (fila 1 = cabecera)
2. Reemplaza `"#N/A"`, `"#DIV/0!"`, `""`, `"-"` por `None`
3. Filtra filas: solo las cuya columna FECHA coincide con la fecha de hoy
4. Excluye filas donde la columna TRIPULACION contiene `"TOTALES"`
5. Agrega columna `Zona`: aplica `mapear_zona()` sobre la columna TRIPULACION; cada fila recibe la zona según el prefijo de la tripulación (mapa `ZONA_MAP` con 10 zonas definidas en código)
6. Parsea numérico la columna PROM: `str → quitar "." → reemplazar "," por "." → float`; idem para columna LITROS (si existe)

**Columnas finales:** Las 6 columnas del rango A:F del sheet (nombres **por confirmar**) + `Zona` (calculada).  
Columnas conocidas como usadas: la que contiene `"CHOFER"` o `"TRIPULACI"`, la que contiene `"PROM"`, la que contiene `"LITROS"`, `Zona`.

**Depende de:** —

---

## Categoría 2: Dataframes principales de `app.py`

Estos se crean una sola vez al inicio de la aplicación y se pasan como argumentos a los tabs.

---

### 11. `df_rec`
**Archivo:** `app.py` (línea 35)  
**Origen:** `resolver_recolecciones(cargar_recolecciones())`  
**Transformaciones** (realizadas por `resolver_recolecciones()` en `components/helpers/id_resolver.py`):
1. Agrega columna `NombreChofer`: mapea `Chofer` (ID) → nombre completo usando `cargar_empleados()`
2. Agrega columna `NombrePeoneta1`: mapea `Peoneta1` (ID) → nombre usando `cargar_empleados()`
3. Agrega columna `NombrePeoneta2`: mapea `Peoneta2` (ID) → nombre usando `cargar_empleados()`
4. Agrega columna `Patente_Real`: mapea `Patente` (ID numérico) → patente alfanumérica usando `cargar_vehiculos()` (`plate`)
5. Agrega columna `Producto`: mapea `idProducto` (ID numérico) → nombre del producto usando `cargar_productos()` (`name`)
6. Deduplica por `(idLocalSistema, idProducto)` — elimina filas repetidas de la vista MySQL

**Columnas finales:** Todas las de `VistaMonitor` (por confirmar) + `NombreChofer`, `NombrePeoneta1`, `NombrePeoneta2`, `Patente_Real`, `Producto`

**Depende de:** `cargar_recolecciones()`, `cargar_empleados()`, `cargar_vehiculos()`, `cargar_productos()`

---

### 12. `df_veh` (temporal)
**Archivo:** `app.py` (línea 44)  
**Origen:** `cargar_vehiculos()`  
**Transformaciones:** ninguna posterior.  
**Uso:** Solo se usa para calcular `vehiculos_stgo` (IDs de vehículos que tienen patente en el sheet Santiago). No se pasa a ningún tab.  
**Columnas finales:** `id`, `plate`  
**Depende de:** `cargar_vehiculos()`

---

### 13. `df_uv` (temporal)
**Archivo:** `app.py` (líneas 47–49)  
**Origen:** `cargar_usuarios_vehiculos()`  
**Transformaciones:**
1. Columna `Vehiculo` → `.astype(str)` para evitar mismatch de tipos con los IDs de PostgreSQL

**Uso:** Solo para calcular `choferes_stgo`, `choferes_todos`, `choferes_reg`. No se pasa a ningún tab.  
**Columnas finales:** `Vehiculo` (str), `Chofer`  
**Depende de:** `cargar_usuarios_vehiculos()`

---

### 14. `df_rec_stgo`
**Archivo:** `app.py` (línea 53)  
**Origen:** `df_rec`  
**Transformaciones:**
1. Filtro: `df_rec[df_rec["Chofer"].isin(choferes_stgo)].copy()`  
   — `choferes_stgo` es el conjunto de IDs de chofer que conducen vehículos con patente en el sheet Santiago

**Columnas finales:** Idénticas a `df_rec`  
**Depende de:** `df_rec`, `choferes_stgo` (calculado de `df_uv` + `df_veh` + `df_sheets`)

---

### 15. `df_rec_reg`
**Archivo:** `app.py` (línea 54)  
**Origen:** `df_rec`  
**Transformaciones:**
1. Filtro: `df_rec[df_rec["Chofer"].isin(choferes_reg)].copy()`  
   — `choferes_reg = choferes_todos - choferes_stgo`

**Columnas finales:** Idénticas a `df_rec`  
**Depende de:** `df_rec`, `choferes_reg`

---

### 16. `_dc_stgo`
**Archivo:** `app.py` (línea 57)  
**Origen:** `_preparar_datos(df_sheets, df_rec_stgo)`  
**Función:** Comparativa de litros vs esperado para los choferes de Santiago.  
**Transformaciones** (realizadas por `_preparar_datos()` en `data_prep.py`):
1. Extrae `Patente` y `Prom` del sheet (columnas detectadas por búsqueda de substring `"PATENTE"` y `"PROM"`)
2. Parsea `Prom`: `str → quitar "." → reemplazar "," por "." → float`; excluye filas con Prom ≤ 0
3. Construye `chofer_por_patente`: Patente → NombreChofer (usando `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()`)
4. Construye `litros_por_patente`: agrupa `df_rec_stgo` por `Patente_Real`, suma `Litros` (excluyendo productos en `_EXCLUIR_LITROS = {"Latas", "Desengrasante"}`)
5. Merge de los tres: prom_df LEFT JOIN chofer_por_patente ON Patente, LEFT JOIN litros_por_patente ON Patente
6. Rellena `LitrosHoy` nulo con 0
7. `Chofer = NombreChofer` si no es null, si no `Patente` (fallback)
8. `Pct = LitrosHoy / Prom * 100` (redondeado a 1 decimal)
9. `SobreMeta = LitrosHoy >= Prom` (bool)
10. Ordena descendente por `Pct`

**Columnas finales:** `Patente`, `Prom`, `NombreChofer`, `LitrosHoy`, `Chofer`, `Pct`, `SobreMeta`  
**Depende de:** `df_sheets`, `df_rec_stgo`, `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()`  
**Retorna `None`** si el sheet no tiene columna PATENTE o PROM. En app.py se convierte a `pd.DataFrame()` vacío en ese caso.

---

### 17. `_dc_reg`
**Archivo:** `app.py` (línea 58)  
**Origen:** `_preparar_datos_regiones(df_regiones, df_rec_reg)`  
**Función:** Comparativa de litros vs esperado para los choferes de Regiones.  
**Transformaciones** (realizadas por `_preparar_datos_regiones()` en `data_prep.py`):
1. Extrae del sheet Regiones: columna CHOFER (como `Chofer`) y columna PROM (como `Prom`)
2. Excluye filas con nombre de chofer nulo
3. Crea clave de join: `_key = Chofer.str.strip().str.lower()`
4. Construye `lit_s`: agrupa `df_rec_reg` por `NombreChofer`, suma `Litros` (filtrado por `_litros()` — excluye Latas y Desengrasante)
5. Crea `_key` en `lit_s`: `Chofer_rec.str.strip().str.lower()`
6. Merge `outer` de `prom_s` con `lit_s` por `_key` — incluye choferes que solo están en el sheet o solo en MySQL
7. Rellena `Chofer` nulo (choferes en MySQL pero no en el sheet) con el nombre real del driver desde `lit_s`
8. Elimina columna `_key`
9. Rellena nulos: `LitrosHoy → 0`, `Prom → 0`
10. `Pct = LitrosHoy / Prom * 100` (solo si Prom > 0, en caso contrario 0; redondeado a 1 decimal)
11. Ordena descendente por `LitrosHoy`

**Columnas finales:** `Chofer`, `Prom`, `LitrosHoy`, `Pct`  
**Depende de:** `df_regiones`, `df_rec_reg`

---

### 18. `data_comp_todos`
**Archivo:** `app.py` (línea 61)  
**Origen:** `pd.concat([_dc_stgo, _dc_reg], ignore_index=True)`  
**Función:** Comparativa combinada de Santiago + Regiones. Se usa en el Carrusel general y en los tabs "Global v2".  
**Transformaciones:**
1. Concatenación vertical de `_dc_stgo` y `_dc_reg`, reindexando
2. Si ambos están vacíos, el resultado es `pd.DataFrame()` vacío

**Columnas finales:** `Patente`, `Prom`, `NombreChofer`, `LitrosHoy`, `Chofer`, `Pct`, `SobreMeta` (de `_dc_stgo`), más `Chofer`, `Prom`, `LitrosHoy`, `Pct` (de `_dc_reg`). Las columnas exclusivas de uno de los dos tendrán `NaN` en las filas del otro.  
**Depende de:** `_dc_stgo`, `_dc_reg`

---

### 19. `_dc_stgo_v2` — ELIMINADO
**Eliminado en el refactor 2026-06.** Era un recálculo idéntico a `_dc_stgo` dentro del
bloque del tab v2; ahora el tab Santiago v2 recibe directamente `_dc_stgo` desde app.py.

---

## Categoría 3: Dataframes intermedios en `data_prep.py`

Estos existen solo dentro de las funciones `_preparar_datos()` y `_preparar_datos_regiones()`. Se documentan para entender el pipeline de transformación.

---

### 20. `prom_df` (interna de `_preparar_datos`)
**Archivo:** `components/helpers/data_prep.py`  
**Origen:** `df_sheets` (columnas PATENTE y PROM)  
**Transformaciones:**
1. Copia de `df_sheets[[col_patente, col_prom]]`
2. Parsea `Prom`: quitar `"."`, reemplazar `","` por `"."`, convertir a float
3. Renombra columna PATENTE → `Patente`
4. Filtra filas con `Prom > 0`

**Columnas finales:** `Patente`, `Prom`  
**Depende de:** `df_sheets`

---

### 21. `chofer_por_patente` (interna de `_preparar_datos`)
**Archivo:** `components/helpers/data_prep.py`  
**Origen:** `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()`  
**Transformaciones:**
1. `mapa_placa`: `vehiculos.set_index("id")["plate"]` — ID → patente
2. `mapa_nombre`: `empleados.set_index("id")["nombre"]` — ID → nombre
3. A `usuarios` le agrega `Patente = Vehiculo.map(mapa_placa)` y `NombreChofer = Chofer.map(mapa_nombre)`
4. Selecciona `["Patente", "NombreChofer"]`, elimina nulos, deduplica por Patente

**Columnas finales:** `Patente`, `NombreChofer`  
**Depende de:** `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()`

---

### 22. `litros_por_patente` (interna de `_preparar_datos`)
**Archivo:** `components/helpers/data_prep.py`  
**Origen:** `df_mysql` (= `df_rec_stgo` en el contexto de app.py)  
**Transformaciones:**
1. Filtra productos en `_EXCLUIR_LITROS` ({"Latas", "Desengrasante"}) si la columna `Producto` existe
2. Filtra filas con `Litros > 0`
3. Agrupa por `Patente_Real`, suma `Litros`
4. Renombra: `Patente_Real → Patente`, `Litros → LitrosHoy`

**Columnas finales:** `Patente`, `LitrosHoy`  
**Depende de:** `df_rec_stgo`

---

### 23. `prom_s` (interna de `_preparar_datos_regiones`)
**Archivo:** `components/helpers/data_prep.py`  
**Origen:** `df_reg` (= `df_regiones`)  
**Transformaciones:**
1. Extrae columna CHOFER (buscada por substring `"CHOFER"`) → renombrada `Chofer`
2. Extrae columna PROM (buscada por substring `"PROM"`) → como `Prom`; rellena nulos con 0
3. Filtra filas con `Chofer` no nulo
4. Agrega `_key = Chofer.str.strip().str.lower()`

**Columnas finales:** `Chofer`, `Prom`, `_key`  
**Depende de:** `df_regiones`

---

### 24. `lit_s` (interna de `_preparar_datos_regiones`)
**Archivo:** `components/helpers/data_prep.py`  
**Origen:** `df_rec` (= `df_rec_reg` en el contexto de app.py)  
**Transformaciones:**
1. Aplica `_litros(df_rec)` — filtra productos en `_EXCLUIR_LITROS`
2. Agrupa por `NombreChofer`, suma `Litros`
3. Renombra: `NombreChofer → Chofer_rec`, `Litros → LitrosHoy`
4. Agrega `_key = Chofer_rec.str.strip().str.lower()`

**Columnas finales:** `Chofer_rec`, `LitrosHoy`, `_key`  
**Depende de:** `df_rec_reg`

---

## Categoría 4: Dataframes internos en tabs y widgets

Estos se crean dentro de funciones de tab y nunca salen de su scope. Se documentan porque cargan datos externos o realizan transformaciones con nombre relevante.

---

### 25. `df_locales`
**Archivos:** `tab_global.py`, `tab_zonas.py`, `tab_carrusel.py`, `tab_v2.py`  
**Origen:** `cargar_estado_locales()`  
**Transformaciones:**
- En todos los casos: filtro `df_locales[df_locales["Chofer"].isin(choferes_filter)]` — solo los locales de los choferes de la zona

**Columnas finales:** `NombreRuta`, `ID_Local`, `Local`, `Estado`, `Prioridad`, `CentroAcopio`, `Chofer`  
**Depende de:** `cargar_estado_locales()`, `choferes_filter`

---

### 26. `data_comp` (interno de `mostrar_dashboard` y `mostrar_cards_choferes`)
**Archivos:** `tab_global.py`, `tab_zonas.py`  
**Origen:** Llega como `data_comp_override` desde app.py (`_dc_stgo` para Global/Santiago, `_dc_reg` para Regiones). El cálculo local con `_preparar_datos()` quedó solo como fallback cuando no se pasa override.  
**Columnas finales:** Idénticas a `_dc_stgo` (ver #16)  
**Depende de:** `df_sheets` (o `df_regiones`), `df_rec`

---

### 27. `_data_comp_reg`
**Archivo:** `tab_carrusel_zonas.py`  
**Origen:** Alias de `_dc_reg` — llega como parámetro `data_comp_reg` desde app.py. Solo se recalcula con `_preparar_datos_regiones(df_regiones, df_rec_reg)` como fallback si no se pasa. (Antes del refactor 2026-06 se recalculaba también en el bloque tab_reg de app.py.)  
**Columnas finales:** Idénticas a `_dc_reg` (ver #17)  
**Depende de:** `_dc_reg` (o `df_regiones` + `df_rec_reg` en el fallback)

---

### 28. `df_emerg_all`
**Archivo:** `components/tabs/tab_carrusel.py`  
**Origen:** `cargar_emergencias()`  
**Transformaciones:** ninguna posterior.  
**Uso:** Filtrado dentro del carrusel para contar emergencias del chofer activo.  
**Columnas finales:** `id_local`, `chofer_asignado`  
**Depende de:** `cargar_emergencias()`

---

### 29. `df_loc_ch`
**Archivo:** `components/tabs/tab_carrusel.py`  
**Origen:** `cargar_estado_locales()` (llamado como `df_locales_all`) filtrado por `Chofer == chofer_id`  
**Transformaciones:**
1. `df_locales_all = cargar_estado_locales()` — todos los locales del día
2. Filtro: `df_locales_all[df_locales_all["Chofer"] == chofer_id]` donde `chofer_id` es el ID del chofer activo en el carrusel

**Columnas finales:** `NombreRuta`, `ID_Local`, `Local`, `Estado`, `Prioridad`, `CentroAcopio`, `Chofer`  
**Depende de:** `cargar_estado_locales()`, `df_c` (para extraer `chofer_id`)

---

### 30. `df_c`
**Archivo:** `components/tabs/tab_carrusel.py`  
**Origen:** `df_rec` filtrado para el chofer activo del carrusel  
**Transformaciones:**
1. Filtro: `df_rec[df_rec["NombreChofer"] == chofer].copy()`
2. Deduplica por `(idLocalSistema, idProducto)` si ambas columnas existen

**Nota:** la columna `Producto` ya viene resuelta por `resolver_recolecciones()` en app.py (se eliminó el re-mapeo con `cargar_productos()` que hacía el carrusel).  
**Columnas finales:** Las de `df_rec`  
**Depende de:** `df_rec`

---

### 31. `razon_counts`
**Archivo:** `components/tabs/tab_carrusel.py`  
**Origen:** `df_c` (filas con `Razon` no nula)  
**Transformaciones:**
1. Filtra `df_c` donde `Razon.notna()`
2. Deduplica por `idLocalSistema` (si existe la columna)
3. Mapea `Razon` (ID) → nombre usando `cargar_razones()`
4. Agrupa por `NombreRazon`, cuenta ocurrencias
5. Ordena descendente por `N`

**Columnas finales:** `NombreRazon`, `N`  
**Depende de:** `df_c`, `cargar_razones()`  
**Nota:** Si no hay fallos, se retorna `pd.DataFrame(columns=["NombreRazon", "N"])` vacío.

---

### 32. `df_razones`
**Archivo:** `components/tabs/tab_rendimiento.py`  
**Origen:** `cargar_razones()`  
**Transformaciones:** ninguna.  
**Uso:** Rellena el `st.multiselect` de razones a excluir del cálculo de efectividad.  
**Columnas finales:** `id`, `name`  
**Depende de:** `cargar_razones()`

---

### 33. `df_loc` (interno de `_cards_choferes` en tab_recolecciones)
**Archivo:** `components/tabs/tab_recolecciones.py`  
**Origen:** `cargar_estado_locales()`  
**Transformaciones:**
1. Agrega `NombreChofer`: mapea `Chofer` (ID) → nombre usando `cargar_empleados()`
2. Agrega `Prio`: `Prioridad.str.strip().str.capitalize()` (o `"Normal"` si no hay columna Prioridad)

**Columnas finales:** `NombreRuta`, `ID_Local`, `Local`, `Estado`, `Prioridad`, `CentroAcopio`, `Chofer`, `NombreChofer`, `Prio`  
**Depende de:** `cargar_estado_locales()`, `cargar_empleados()`

---

## Tabla resumen: dataframe → fuente de datos

| Dataframe | Fuente primaria | TTL caché |
|-----------|----------------|-----------|
| `cargar_recolecciones()` | MySQL · `VistaMonitor` | 5 min |
| `cargar_estado_locales()` | MySQL · `LocalesRuta JOIN Usuarios` | 1 min |
| `cargar_emergencias()` | MySQL · `Emergencias` | 5 min |
| `cargar_usuarios_vehiculos()` | MySQL · `Usuarios` | 1 hora |
| `cargar_empleados()` | PostgreSQL · `personnel_employee` | 1 hora |
| `cargar_productos()` | PostgreSQL · `products_product` | 1 hora |
| `cargar_razones()` | PostgreSQL · `visits_visitfailurereason` | 1 hora |
| `cargar_vehiculos()` | PostgreSQL · `visits_vehicle` | 1 hora |
| `df_sheets` | Google Sheets Santiago (A:Z) | 5 min |
| `df_regiones` | Google Sheets Regiones (A:F) | 5 min |
| `df_rec` | `cargar_recolecciones()` + 3 tablas PG | — |
| `df_rec_stgo` | `df_rec` | — |
| `df_rec_reg` | `df_rec` | — |
| `_dc_stgo` | `df_sheets` + `df_rec_stgo` + 3 tablas PG | — |
| `_dc_reg` | `df_regiones` + `df_rec_reg` | — |
| `data_comp_todos` | `_dc_stgo` + `_dc_reg` | — |
| `df_locales` (en tabs) | `cargar_estado_locales()` filtrado | — |
| `df_emerg_all` | `cargar_emergencias()` | — |
| `razon_counts` | `df_c` + `cargar_razones()` | — |
