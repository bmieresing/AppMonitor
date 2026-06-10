# WIDGETS.md — Inventario de widgets

Cada elemento visual distinto es una entrada propia. Tabs orchestradores al final.  
Basado únicamente en el código real. Lo no verificable está marcado **por confirmar**.

> **Refactor 2026-06:** los 5 KPIs globales se calculan ahora en un único módulo
> `components/helpers/kpis.py` (`calcular_kpis`, `exitosas_fallidas`, `no_alcanzados`);
> los donuts CSS, los donuts Plotly y el carrusel solo renderizan. Las constantes
> (umbrales, productos excluidos, intervalos) viven en `config.py`. La navegación
> entre vistas usa `st.segmented_control` en `app.py` — solo se renderiza la vista
> activa (antes `st.tabs` ejecutaba las 11 en cada rerun).

---

## Índice

| # | Widget | Archivo |
|---|--------|---------|
| **Infraestructura** | | |
| 1 | `_css()` | `widgets/layout.py` |
| 2 | `_header()` | `widgets/layout.py` |
| **Tanques** | | |
| 3 | Tanque — Litros | `widgets/tanque.py` vía `cards.py`, `tab_carrusel.py` |
| 4 | Tanque — Locales | `widgets/tanque.py` vía `cards.py`, `tab_carrusel.py` |
| 5 | Tanque — Alta | `widgets/tanque.py` vía `cards.py`, `tab_carrusel.py` |
| 6 | Tanque — Emergencias | `widgets/tanque.py` vía `tab_carrusel.py` |
| **KPI Donuts CSS** (`_donuts_global`) | | |
| 7 | Donut CSS — Litros vs Esperado | `widgets/donuts.py` |
| 8 | Donut CSS — Locales Realizados | `widgets/donuts.py` |
| 9 | Donut CSS — Prioridad Alta | `widgets/donuts.py` |
| 10 | Donut CSS — Recolecciones Exitosas | `widgets/donuts.py` |
| 11 | Donut CSS — Rutas Cerradas | `widgets/donuts.py` |
| **KPI Donuts Plotly** (`_kpi_col` en tab_v2) | | |
| 12 | Donut Plotly — Litros vs Esperado | `tabs/tab_v2.py` |
| 13 | Donut Plotly — Locales Realizados | `tabs/tab_v2.py` |
| 14 | Donut Plotly — Prioridad Alta | `tabs/tab_v2.py` |
| 15 | Donut Plotly — Recolecciones Exitosas | `tabs/tab_v2.py` |
| 16 | Donut Plotly — Rutas Cerradas | `tabs/tab_v2.py` |
| **Donut desglose Altair** | | |
| 17 | Donut Altair — Desglose chofer | `tabs/tab_carrusel.py` |
| **Grids y cards de choferes** | | |
| 18 | ~~Grid compacto de choferes~~ (eliminado — código muerto) | — |
| 19 | Cards de choferes con tanques | `widgets/cards.py` |
| 20 | Cards de centros de acopio | `widgets/cards.py` |
| **Carrusel — subwidgets** | | |
| 21 | Mini KPIs carrusel (4 cajas) | `tabs/tab_carrusel.py` |
| 22 | Top 5 — más litros | `tabs/tab_carrusel.py` |
| 23 | Top 5 — menos litros | `tabs/tab_carrusel.py` |
| 24 | Razones de fallo | `tabs/tab_carrusel.py` |
| 25 | Desglose por producto (carrusel) | `tabs/tab_carrusel.py` |
| **Tab v2 — subwidgets** | | |
| 26 | Mini métrica — Litros | `tabs/tab_v2.py` |
| 27 | Mini métrica — Locales | `tabs/tab_v2.py` |
| 28 | Mini métrica — Alta | `tabs/tab_v2.py` |
| 29 | Card de chofer v2 | `tabs/tab_v2.py` |
| **Recolecciones — subwidgets** | | |
| 30 | Panel de chips por producto | `tabs/tab_recolecciones.py` |
| 31 | Cards de choferes (recolecciones) | `tabs/tab_recolecciones.py` |
| **Parámetros — subwidget** | | |
| 32 | Semáforo de umbrales | `tabs/tab_parametros.py` |
| **Tabs orchestradores** | | |
| 33 | Tab Global | `tabs/tab_global.py` |
| 34 | Tab Santiago | `tabs/tab_zonas.py` |
| 35 | Tab Regiones | `tabs/tab_zonas.py` |
| 36 | Tab Rendimiento | `tabs/tab_rendimiento.py` |
| 37 | Tab Carrusel | `tabs/tab_carrusel.py` |
| 38 | Tab Carrusel Zonas | `tabs/tab_carrusel_zonas.py` |
| 39 | Tab Recolecciones | `tabs/tab_recolecciones.py` |
| 40 | Tab Parametros | `tabs/tab_parametros.py` |
| 41 | Tab Santiago v2 | `tabs/tab_v2.py` |
| 42 | Tab Global v2 | `tabs/tab_v2.py` |
| 43 | Tab Regiones v2 | `tabs/tab_v2.py` |

---

## 1. `_css()`
**Archivo:** `components/widgets/layout.py`  
**Dataframes:** ninguno  
**Función:** Inyecta CSS global que compacta el layout de Streamlit. Se llama una vez al inicio de cada tab.  
**Estilos que aplica:** `block-container` padding `0.5rem`; `stVerticalBlock` gap `0.3rem`; `hr` margin `0.4rem 0`; `stMetric` label `12px`, value `1.6rem`, delta `12px / #444`, ícono delta oculto.

---

## 2. `_header()`
**Archivo:** `components/widgets/layout.py`  
**Firma:** `_header(tab_nombre, key_prefix="")`  
**Dataframes:** ninguno  
**Función:** Banner superior con nombre del tab, timestamp y botón "↺ Actualizar". El botón llama `st.cache_data.clear()` + `st.rerun()`.  
**Estilos:** fondo `#1a472a`, padding `8px 20px`, border-radius `6px`; título `16px / 700 / letter-spacing 1px`; badge tab `rgba(255,255,255,0.18) / 18px / 700 / letter-spacing 2px`; timestamp `12px / line-height 1.6`; badge EN VIVO `#28a745 / bold`; botón `#1a472a / blanco / borde rgba(255,255,255,0.35) / 600`.

---

## 3. Tanque — Litros
**Archivo:** `components/widgets/tanque.py` (función `_tanque()`), llamado desde `cards.py` y `tab_carrusel.py`  
**Dataframes usados para calcular los valores de entrada:**
- `data_comp["LitrosHoy"]` → litros recolectados hoy por el chofer
- `data_comp["Prom"]` → promedio esperado (3 meses)
- `pct = _pct(litros_hoy, prom)` = `int(litros_hoy / prom * 100)`
- `sub = f"{int(litros_hoy):,} / {int(prom):,} L"`

**Función:** Barra de nivel que indica cuántos litros recolectó el chofer hoy vs su promedio esperado.  
**Modo:** normal en `_desempeno_centros()` (80 px); compacto en `_cards_choferes_tanque()` (52 px); banner en carrusel vía `_tanque_b()` (62 px).  
**Colores:** `≥80%` → borde/texto `#2d7a2d`, relleno `rgba(45,122,45,0.22)` · `≥50%` → `#c0392b / rgba(230,126,34,0.22)` · `<50%` → `#c0392b / rgba(192,57,43,0.22)`.

---

## 4. Tanque — Locales
**Archivo:** `components/widgets/tanque.py` (función `_tanque()`), llamado desde `cards.py` y `tab_carrusel.py`  
**Dataframes usados para calcular los valores de entrada:**
- `df_locales["Estado"]` → conteo de locales realizados y total asignados al chofer
- `df_rec["Razon"] == 11` deduplicado por `idLocalSistema` → `no_alc` (locales "no alcanzamos a pasar")
- `pct = _pct(realizados - no_alc, total_locales)`
- `no_alc_pct = _pct(no_alc, total_locales)` → capa roja superpuesta en el tanque
- `sub = f"{realizados - no_alc}/{total_locales}"`

**Función:** Barra de nivel que indica cuántos locales del recorrido del chofer fueron realizados exitosamente (excluyendo "no alcanzamos a pasar").  
**Estilos:** idénticos al Tanque Litros. La capa `no_alc_pct` se muestra en `rgba(229,57,53,0.5)` sobre el relleno principal.

---

## 5. Tanque — Alta
**Archivo:** `components/widgets/tanque.py` (función `_tanque()`), llamado desde `cards.py` y `tab_carrusel.py`  
**Dataframes usados para calcular los valores de entrada:**
- `df_locales[df_locales["Prioridad"].str.upper().str.startswith("ALTA")]` → locales de prioridad alta del chofer
- `df_rec["Razon"] == 11` cruzado con IDs de alta → `no_alc_alta`
- `pct = _pct(real_alta - no_alc_alta, total_alta)`
- `no_alc_pct = _pct(no_alc_alta, total_alta)`
- `sub = f"{real_alta - no_alc_alta}/{total_alta}"`

**Función:** Barra de nivel para los locales de prioridad alta únicamente. Solo se muestra si `total_alta > 0`.  
**Estilos:** idénticos al Tanque Locales.

---

## 6. Tanque — Emergencias
**Archivo:** `components/widgets/tanque.py` (función `_tanque_b()`), llamado solo desde `tab_carrusel.py`  
**Dataframes usados para calcular los valores de entrada:**
- `df_emerg_all["chofer_asignado"] == chofer_id` → `emerg_total` (emergencias asignadas al chofer hoy)
- `df_c["Emergencia"].astype(bool)` deduplicado por `idLocalSistema` → `emerg_realizadas`
- `pct = int(emerg_realizadas / emerg_total * 100)`
- `sub = f"{emerg_realizadas}/{emerg_total}"`

**Función:** Barra de nivel para emergencias asignadas al chofer activo en el carrusel. Solo aparece si `emerg_total > 0`.  
**Estilos:** usa `_tanque_b()` — diseño oscuro para el banner; borde/texto `≥100%` → `#81c784`, `≥80%` → `#a5d6a7`, `≥50%` → `#ffb74d`, `<50%` → `#ef9a9a`.

---

## 7. Donut CSS — Litros vs Esperado
**Archivo:** `components/widgets/donuts.py` (función interna `_card()` de `_donuts_global()`)  
**Dataframes:**
- `df_rec["Litros"]` filtrado por `_litros()` (excluye Latas/Desengrasante) → `litros_hoy`
- `data_comp["Prom"].sum()` → `prom_stgo` (Santiago)
- `cargar_datos_regiones()` columna PROM → `prom_reg` (Regiones)
- `prom_total`: solo Santiago / solo Regiones / suma de ambos según `tab_nombre`
- `pct_lit = round(litros_hoy / prom_total * 100)`

**Función:** Tarjeta KPI con donut CSS (conic-gradient) que muestra litros recolectados hoy sobre el promedio esperado total de la zona.  
**Valor mostrado:** `f"{litros_hoy:,.0f} / {prom_total:,.0f} L"`  
**Colores donut:** verde `#2d7a2d` (realizado) · gris `#e0e0e0` (restante).  
**Estilos card:** borde `1px solid #e0e8e0`, border-radius `14px`, shadow `0 2px 12px rgba(0,0,0,0.07)`. Modo normal: emoji `72px`, donut `130px`, agujero `88px`, pct `22px/900/#1a472a`, valor `28px`. Modo compacto (Regiones): emoji `44px`, donut `86px`, agujero `58px`, pct `16px`, valor `18px`.

---

## 8. Donut CSS — Locales Realizados
**Archivo:** `components/widgets/donuts.py`  
**Dataframes:**
- `df_locales["Estado"]` → `realizados_loc` (count "Realizado"), `total_loc` (len)
- `df_rec["Razon"] == 11` deduplicado por `idLocalSistema` → `no_alc_loc`
- `exitosos_loc = max(0, realizados_loc - no_alc_loc)`
- `pct_loc = round(exitosos_loc / total_loc * 100)`

**Función:** Donut que muestra locales realizados exitosamente. El segmento naranja-rojo del donut representa los "no alcanzamos a pasar" (razón 11).  
**Valor mostrado:** `f"{exitosos_loc:,} / {total_loc:,}"`  
**Colores donut:** verde `#2d7a2d` (realizados) · rojo `#e53935` (no alc.) · gris `#e0e0e0` (pendientes).

---

## 9. Donut CSS — Prioridad Alta
**Archivo:** `components/widgets/donuts.py`  
**Dataframes:**
- `df_locales[df_locales["Prioridad"].str.upper().contains("ALTA")]` → `df_alta`
- `df_rec["Razon"] == 11` cruzado con `df_locales["ID_Local"]` donde Prioridad contiene "ALTA" → `no_alc_alta`
- `exitosos_alta = max(0, real_alta - no_alc_alta)`
- `pct_alta = round(exitosos_alta / total_alta * 100)`

**Función:** Donut para locales de prioridad alta únicamente.  
**Valor mostrado:** `f"{exitosos_alta:,} / {total_alta:,}"`  
**Colores donut:** verde `#2d7a2d` · rojo `#e53935` · gris `#e0e0e0`.

---

## 10. Donut CSS — Recolecciones Exitosas
**Archivo:** `components/widgets/donuts.py` — valores de `exitosas_fallidas()` en `helpers/kpis.py`  
**Criterio (por local único):** exitosa si la suma de `Litros` del local > 0; fallida si tiene `Razon` y no juntó litros. Mutuamente excluyentes e inmune al orden de las filas por producto de `VistaMonitor`.  
- `pct_exit = _pct(exitosas, exitosas + fallidas)`

**Función:** Donut que muestra el ratio de visitas exitosas vs fallidas.  
**Valor mostrado:** `f"{exitosas:,} / {fallidas:,}"` (exitosas / fallidas)  
**Colores donut:** verde `#28a745` (exitosas) · rojo `#dc3545` (fallidas).

---

## 11. Donut CSS — Rutas Cerradas
**Archivo:** `components/widgets/donuts.py`  
**Dataframes:**
- `_cerrados_set(df_rec)` → choferes con `df_rec["FechaObservacion"]` no nula → `cerradas`
- `df_locales["Chofer"].nunique()` → `n_rutas`
- `pct_cerradas = round(cerradas / n_rutas * 100)`

**Función:** Donut que indica cuántas rutas ya cerraron el día operativo.  
**Valor mostrado:** `f"{cerradas:,} / {n_rutas:,}"`  
**Colores donut:** azul `#1a6b8a` (cerradas) · gris `#e0e0e0` (abiertas).

---

## 12. Donut Plotly — Litros vs Esperado
**Archivo:** `components/tabs/tab_v2.py` (función `_kpi_col()` dentro de `mostrar_tab_v2()`)  
**Dataframes:** (los KPIs vienen de `calcular_kpis()` en `helpers/kpis.py`)
- `calcular_kpis(df_rec, df_locales, data_comp)["litros"]` → litros hoy (suma de `df_rec` filtrado por `_litros()`)
- `calcular_kpis(...)["esperado"]` → `data_comp["Prom"].sum()`
- `pct = calcular_kpis(...)["pct_lit"]`

**Función:** Donut Plotly (hole 0.72) con pct como anotación central. Mismo KPI que el Donut CSS #7 pero tecnología Plotly y estilos distintos.  
**Leyenda:** verde `#2d7a2d` Recolectado · gris `#e0e0e0` Restante.  
**Estilos:** emoji `72px / margin-top 20px`; donut `height 130px`; label `0.72rem / #999 / uppercase`; valor `1.4rem / 700 / #1a472a`.

---

## 13. Donut Plotly — Locales Realizados
**Archivo:** `components/tabs/tab_v2.py`  
**Dataframes:**
- `calcular_kpis(...)["pct_loc"]`, `["exitosos_loc"]`, `["total_loc"]`, `["no_alc_loc"]`
- Mismas fuentes que Donut CSS #8 (`df_locales`, `df_rec["Razon"] == 11`)
- `segmento_alerta = no_alc_loc * 100 // max(total_loc, 1)` → segmento rojo adicional

**Función:** Donut Plotly para locales realizados. Agrega un tercer segmento rojo (`#e53935`) para los "no alc.". Muestra nota `"N no alc."` si `no_alc_loc > 0`.  
**Leyenda:** verde Realizados · rojo No alc. · gris Pendientes.

---

## 14. Donut Plotly — Prioridad Alta
**Archivo:** `components/tabs/tab_v2.py`  
**Dataframes:**
- `calcular_kpis(...)["pct_alta"]`, `["exitosos_alta"]`, `["total_alta"]`, `["no_alc_alta"]`
- Mismas fuentes que Donut CSS #9 (`df_locales["Prioridad"]`, `df_rec["Razon"] == 11`)
- `segmento_alerta = no_alc_alta * 100 // max(total_alta, 1)`

**Función:** Donut Plotly para prioridad alta, con segmento rojo para "no alc." y nota si aplica.  
**Leyenda:** verde Realizados · rojo No alc. · gris Pendientes.

---

## 15. Donut Plotly — Recolecciones Exitosas
**Archivo:** `components/tabs/tab_v2.py`  
**Dataframes:**
- `calcular_kpis(...)["pct_exit"]`, `["exitosas"]`, `["fallidas"]` — mismo criterio que el widget #10 (`helpers/kpis.py`)
- `color_fill="#28a745"`, `color_bg="#dc3545"` → no hay segmento gris, el "bg" es el rojo de fallidas

**Función:** Donut Plotly para exitosas vs fallidas. El agujero verde representa exitosas; el relleno externo rojo representa fallidas.  
**Leyenda:** verde Exitosas · rojo Fallidas.

---

## 16. Donut Plotly — Rutas Cerradas
**Archivo:** `components/tabs/tab_v2.py`  
**Dataframes:**
- `calcular_kpis(...)["pct_cerradas"]`, `["cerradas"]`, `["n_rutas"]`
- `_cerrados_set(df_rec)` y `df_locales["Chofer"].nunique()`

**Función:** Donut Plotly para rutas cerradas del día.  
**Leyenda:** azul `#1a6b8a` Cerradas · gris `#e0e0e0` Abiertas.

---

## 17. Donut Altair — Desglose chofer
**Archivo:** `components/tabs/tab_carrusel.py` (función `_donut()`)  
**Firma:** `_donut(exitosas, pend_alta, pend_normal, razon_counts)`  
**Dataframes:**
- `exitosas`: locales únicos de `df_c` con `Litros > 0`
- `pend_alta`, `pend_normal`: locales pendientes de `df_loc_ch` particionados por `Prioridad`
- `razon_counts`: agrupación de `df_c["Razon"]` mapeada con `cargar_razones()` → columnas `NombreRazon`, `N`

**Función:** Donut Altair con un segmento por razón de fallo + pendientes. Solo para el chofer activo del carrusel.  
**Estilos:** `innerRadius 55`, `outerRadius 100`, `width 240`, `height 300`; leyenda `orient bottom / labelFontSize 10 / symbolSize 80 / columns 2`.  
**Colores:** exitosas `#28a745` · "No alcanzamos a pasar" `#e53935` · otros fallos `["#c0392b", "#922b21", "#7b241c", "#641e16", "#4a0e0e"]` · pend. alta `#555555` · pend. normal `#95a5a6`.

---

## 18. Grid compacto de choferes — ELIMINADO
**Eliminado en el refactor 2026-06.** `_grid_choferes()` no se llamaba desde ningún tab
(código muerto) y además referenciaba `C_ROJO` sin importarlo (NameError latente).
Si se necesita de nuevo, recuperarlo desde el historial de git.

---

## 19. Cards de choferes con tanques
**Archivo:** `components/widgets/cards.py` (función `_cards_choferes_tanque()`)  
**Firma:** `_cards_choferes_tanque(df_rec, df_locales, data_comp, key_prefix="", cols_por_fila=4)`  
**Dataframes:**
- `data_comp["Chofer"]`, `data_comp["LitrosHoy"]`, `data_comp["Prom"]`, `data_comp["Pct"]` → valores para Tanque Litros (widget #3)
- `df_locales["Estado"]`, `df_locales["Prioridad"]`, `df_locales["ID_Local"]` → valores para Tanques Locales (#4) y Alta (#5)
- `df_rec["Razon"] == 11` + `df_locales` → `no_alc_pct` para el overlay rojo en los tanques
- `df_rec["FechaObservacion"]` → `_cerrados_set()` para 🔒

**Función:** Grilla de tarjetas por chofer, cada una con 2 o 3 tanques compactos (Litros + Locales; Alta solo si hay locales de alta prioridad). Ordenadas por `data_comp["Pct"]` descendente.  
**Estilos:** card `border 1px solid #c8e6c9 / br 7px / padding 5px 6px 4px / shadow 0 1px 4px rgba(0,0,0,0.04) / margin 2px`; fondo cerrado `#f0f4f0` / abierto `#f9fdf9`; nombre `14px/700/#1a472a`; tanques `flex / gap 5px`.

---

## 20. Cards de centros de acopio
**Archivo:** `components/widgets/cards.py` (función `_desempeno_centros()`)  
**Firma:** `_desempeno_centros(df_rec, data_comp, df_locales)`  
**Dataframes:**
- `df_locales["CentroAcopio"]`, `df_locales["Estado"]` → realizados/total por centro para Tanque Locales (#4)
- `data_comp["LitrosHoy"].sum()` y `data_comp["Prom"].sum()` → litros Santiago para Tanque Litros (#3)
- `cargar_datos_regiones()` columna PROM → promedio por zona para centros de Regiones
- `df_rec["Litros"]` agrupado por `CentroAcopio` (mapeado desde `df_locales`) → litros reales por centro

**Función:** Una tarjeta por centro de acopio (zona) con dos tanques en modo normal (Litros y Locales).  
**Estilos:** card `border 1px solid #c8e6c9 / br 10px / padding 12px 12px 10px / bg #f9fdf9 / shadow 0 1px 6px rgba(0,0,0,0.05)`; nombre `12px/700/#1a472a`; tanques `flex / gap 10px`.

---

## 21. Mini KPIs carrusel (4 cajas)
**Archivo:** `components/tabs/tab_carrusel.py` (función `_mini_kpis()`)  
**Firma:** `_mini_kpis(exitosas, fallidas, pend_alta, pend_normal)`  
**Dataframes:**
- `exitosas`, `fallidas`: de `df_c` (locales únicos por `idLocalSistema`), calculados en `mostrar_carrusel()`
- `pend_alta`, `pend_normal`: de `df_loc_ch["Estado"] != "Realizado"` particionado por `Prioridad`

**Función:** Fila de 4 cajas de color bajo el donut del carrusel. Muestra exitosas, fallidas, pendientes alta y pendientes normal del chofer activo.  
**Estilos:** `br 10px / padding 10px 12px / texto blanco`; colores: exitosas `#2d7a2d` · fallidas `#c0392b` · pend. alta `#555555` · pend. normal `#95a5a6`; label `12px/uppercase/letter-spacing 1px/opacity 0.8`; valor `26px/900/line-height 1.1`; sub `12px/opacity 0.8`.

---

## 22. Top 5 — más litros
**Archivo:** `components/tabs/tab_carrusel.py` (función `_top5(df, titulo, ascendente=False, color)`)  
**Dataframes:**
- `df_c["Litros"]`, `df_c["idLocalSistema"]`, `df_c["Local"]` → slice de `df_rec` para el chofer activo
- Agrupa por `idLocalSistema`, suma litros, toma los 5 mayores (`nlargest(5, "Litros")`)

**Función:** Lista de los 5 locales con más litros del chofer activo, con barra proporcional.  
**Estilos:** contenedor `white / border 1px solid #e8e8e8 / br 8px / padding 10px 12px`; barra `h 4px / bg #eee / relleno color #2d7a2d`; litros `min-width 44px / right / 700 / 12px`.

---

## 23. Top 5 — menos litros
**Archivo:** `components/tabs/tab_carrusel.py` (función `_top5(df, titulo, ascendente=True, color)`)  
**Dataframes:** idénticos al widget #22 — misma fuente `df_c`, pero toma los 5 menores (`nsmallest(5, "Litros")`).

**Función:** Lista de los 5 locales con menos litros del chofer activo (los más problemáticos).  
**Estilos:** idénticos al widget #22 pero `color="#c0392b"` para la barra y el valor de litros.

---

## 24. Razones de fallo
**Archivo:** `components/tabs/tab_carrusel.py` (función `_razones_fallo()`)  
**Firma:** `_razones_fallo(df_c)`  
**Dataframes:**
- `df_c["Razon"]` filtrado a no nulos, deduplicado por `idLocalSistema`
- `cargar_razones()` → mapa ID → nombre de razón
- Agrupa por `NombreRazon`, cuenta occurrencias, ordena descendente

**Función:** Lista de razones de fallo del chofer activo con barra proporcional y conteo. Si no hay fallos muestra "Sin fallos hoy".  
**Estilos:** contenedor `white / border 1px solid #e8e8e8 / br 8px / padding 10px 12px`; barra `h 4px / relleno #e74c3c`; conteo `12px/700/#e74c3c`.

---

## 25. Desglose por producto (carrusel)
**Archivo:** `components/tabs/tab_carrusel.py` (función `_productos()`)  
**Firma:** `_productos(df_c)`  
**Dataframes:**
- `df_c["Producto"]`, `df_c["Litros"]` filtrado a `Litros > 0`
- Agrupa por `Producto`, cuenta visitas y suma litros

**Función:** Lista de productos recolectados por el chofer activo con barra de gradiente y conteo de visitas.  
**Estilos:** contenedor `white / border 1px solid #e8e8e8 / br 10px / padding 12px 16px / mt 8px`; barra `bg #e8f4f8 / h 6px / relleno linear-gradient(90deg, #1a6b8a, #28a5d0)`; litros `12px/800/#1a6b8a`.

---

## 26. Mini métrica — Litros
**Archivo:** `components/tabs/tab_v2.py` (función `_mini_metrica()`)  
**Dataframes:**
- `data_comp["LitrosHoy"]` y `data_comp["Prom"]` para el chofer → `pct_lit = _pct(litros_hoy, prom)`
- `sub = f"{int(litros_hoy):,} / {int(prom):,} L"`

**Función:** Caja compacta con relleno de fondo proporcional que muestra el % de litros vs promedio. Usada dentro de `_card_chofer()`.  
**Estilos:** `h 52px / border 1px solid {color} / br 4px / bg #fafafa`; relleno `rgba(…,0.22)` posición absoluta; pct `18px/900`; label `0.65rem/#888`; sub `0.65rem/#999`. Color: ≥80% `#2d7a2d` · ≥50% `#e67e22` · <50% `#c0392b`.

---

## 27. Mini métrica — Locales
**Archivo:** `components/tabs/tab_v2.py` (función `_mini_metrica()`)  
**Dataframes:**
- `df_locales["Estado"]` y `df_rec["Razon"] == 11` → `pct_loc = _pct(realizados - no_alc, total)`
- `sub = f"{realizados - no_alc}/{total}"`

**Función:** Caja compacta con % de locales realizados (descontando "no alc."). Usada dentro de `_card_chofer()`.  
**Estilos:** idénticos al widget #26.

---

## 28. Mini métrica — Alta
**Archivo:** `components/tabs/tab_v2.py` (función `_mini_metrica()`)  
**Dataframes:**
- `df_locales["Prioridad"]` filtrado a "ALTA" + `df_rec["Razon"] == 11` → `pct_alta = _pct(real_alta - no_alc_alta, total_alta)`
- `sub = f"{real_alta - no_alc_alta}/{total_alta}"`

**Función:** Caja compacta con % de locales de prioridad alta. Solo aparece en `_card_chofer()` si hay locales de alta.  
**Estilos:** idénticos al widget #26.

---

## 29. Card de chofer v2
**Archivo:** `components/tabs/tab_v2.py` (función `_card_chofer()`)  
**Firma:** `_card_chofer(ch: dict)`  
**Dataframes:**
- `ch` es un dict construido por `_metricas_choferes(df_rec, df_locales, data_comp)`. Claves:
  - `nombre`: de `data_comp["Chofer"]`
  - `cerrado`: `nombre in _cerrados_set(df_rec)` — True si `df_rec["FechaObservacion"]` es no nula
  - `litros_hoy`, `prom`, `pct_lit`: de `data_comp["LitrosHoy"]`, `["Prom"]`, `["Pct"]`
  - `pct_loc`, `sub_loc`: de `df_locales["Estado"]` descontando `df_rec["Razon"] == 11`
  - `pct_alta`, `sub_alta`: de `df_locales["Prioridad"]` + `df_rec["Razon"] == 11`; `None` si no hay locales de alta

**Función:** Tarjeta de chofer con `st.container(border=True)`. Muestra nombre (🔒 si cerrado) y 2 o 3 mini métricas (widgets #26, #27, #28).

---

## 30. Panel de chips por producto
**Archivo:** `components/tabs/tab_recolecciones.py` (función `_panel_productos()`)  
**Firma:** `_panel_productos(df_rec)`  
**Dataframes:**
- `df_rec["Producto"]`, `df_rec["Litros"]` filtrado a `Litros > 0`
- Agrupa por `Producto`, suma litros y cuenta visitas
- Excluye `{"Latas", "Desengrasante"}` del total de aceite en el `st.metric`

**Función:** Fila de chips con totales por producto: litros, visitas, % del total y barra de proporción.  
**Estilos:** `flex-wrap / gap 8px`; chip `flex 1 / min-width 130px / br 10px / padding 12px 16px`; paleta cíclica de 8 colores; litros `26px/900`; barra `h 5px / br 4px`.

---

## 31. Cards de choferes (recolecciones)
**Archivo:** `components/tabs/tab_recolecciones.py` (función `_cards_choferes()`)  
**Firma:** `_cards_choferes(df_rec)`  
**Dataframes:**
- `df_rec["NombreChofer"]`, `df_rec["Producto"]`, `df_rec["Litros"]` → litros y desglose por producto
- `cargar_estado_locales()` + `cargar_empleados()` → `df_loc` con `NombreChofer`, `Estado`, `Prioridad`

**Función:** Grid 4 columnas con tarjeta por chofer. Cada tarjeta muestra litros totales, barra relativa al máximo del día, badges de productos y barra de locales Normal.  
**Estilos:** grid `repeat(4,1fr) / gap 8px`; card `border 1px solid {color}44 / border-top 3px solid {color} / br 7px / padding 9px 11px / bg #fafafa`; nombre `12px/700/#1a2e1a`; litros `20px/900`; barra litros `h 7px`; semáforo: ≥80% `#2d7a2d` · ≥50% `#e67e22` · <50% `#c0392b` · sin datos `#9e9e9e`.

---

## 32. Semáforo de umbrales
**Archivo:** `components/tabs/tab_parametros.py` (función `_widget_semaforo()`)  
**Firma:** `_widget_semaforo(titulo, verde, amarillo, descripcion="")`  
**Dataframes:** ninguno — los umbrales son constantes del módulo (`UMBRAL_VERDE=80`, `UMBRAL_AMARILLO=50`)  
**Función:** Barra horizontal con tres zonas coloreadas proporcionales que visualiza los umbrales del sistema.  
**Estilos:** `br 6px / overflow hidden / h 28px / 12px/700`; rojo `#c0392b` ancho `amarillo%`; amarillo `#e67e22` ancho `(verde-amarillo)%`; verde `#2d7a2d` ancho `(100-verde)%`.

---

## 33. Tab Global
**Archivo:** `components/tabs/tab_global.py`  
**Llamada desde app.py:** `mostrar_dashboard(df_sheets, df_rec, choferes_filter=choferes_todos, key_prefix="global_", tab_nombre="Global")`  
**Dataframes recibidos:** `df_sheets` (sheet Santiago), `df_rec` (todas las recolecciones)  
**Dataframes calculados internamente:**
- `data_comp` — llega como `data_comp_override=_dc_stgo` desde app.py (solo se recalcula con `_preparar_datos()` si no se pasa override)
- `df_locales = cargar_estado_locales()` filtrado por `choferes_todos`

**Función:** Renderiza `_css()` → `_header("Global")` → 5 Donuts CSS (widgets #7–#11) → `st.divider()` → Cards de centros de acopio (widget #20).

---

## 34. Tab Santiago
**Archivo:** `components/tabs/tab_zonas.py`  
**Llamada desde app.py:** `mostrar_cards_choferes(df_sheets, df_rec_stgo, choferes_filter=choferes_stgo, key_prefix="stgo_cards_", tab_nombre="Santiago")`  
**Dataframes recibidos:** `df_sheets` (sheet Santiago), `df_rec_stgo` (recolecciones solo choferes Santiago)  
**Dataframes calculados internamente:**
- `data_comp` — llega como `data_comp_override=_dc_stgo` desde app.py (solo se recalcula si no se pasa override)
- `df_locales = cargar_estado_locales()` filtrado por `choferes_stgo`

**Función:** Renderiza `_css()` → `_header("Santiago")` → 5 Donuts CSS modo normal (widgets #7–#11) → `st.divider()` → Cards de choferes con tanques (widget #19). `cols_por_fila` calculado dinámicamente (4/5/6 según cantidad de choferes).

---

## 35. Tab Regiones
**Archivo:** `components/tabs/tab_zonas.py`  
**Llamada desde app.py:** `mostrar_cards_choferes(df_regiones, df_rec_reg, choferes_filter=choferes_reg, key_prefix="reg_cards_", tab_nombre="Regiones", data_comp_override=_dc_reg)`  
**Dataframes recibidos:**
- `df_regiones` (sheet Regiones — TRIPULACION, PROM, LITROS ESPERADO, Zona)
- `df_rec_reg` (recolecciones solo choferes Regiones)
- `data_comp_override=_dc_reg` — comparativa calculada una sola vez en app.py con `_preparar_datos_regiones(df_regiones, df_rec_reg)`

**Dataframes calculados internamente:**
- `data_comp = data_comp_override` (no recalcula — usa el override)
- `df_locales = cargar_estado_locales()` filtrado por `choferes_reg`

**Función:** Idéntica al Tab Santiago pero con datos de Regiones. `tab_nombre="Regiones"` hace que `_donuts_global()` active el modo compacto (emoji 44px, donut 86px). Sin cards de centros de acopio (solo tanques por chofer).  
**Diferencia clave respecto al Tab Santiago:** `_preparar_datos_regiones()` une por nombre de chofer (sin intermediar por patente) porque los choferes de Regiones no tienen patente en el sheet.

---

## 36. Tab Rendimiento
**Archivo:** `components/tabs/tab_rendimiento.py`  
**Llamada desde app.py:** `mostrar_rendimiento(df_rec)`  
**Dataframes:** `df_rec` (todas las recolecciones); carga internamente `cargar_razones()` para el multiselect de exclusión.  
**Función:** Gráfico de barras apiladas Altair (exitosas vs fallidas por chofer) + tabla de resumen coloreada. Permite excluir razones del cálculo.  
**Estilos gráfico:** colores `#28a745/#dc3545`; etiquetas dentro de barras `10px/bold/blanco` solo si N>2; altura `max(300, choferes * 28)px`. Tabla: ≥80% `#155724/bold` · <50% `#721c24/bold`.

---

## 37. Tab Carrusel
**Archivo:** `components/tabs/tab_carrusel.py` — decorado con `@st.fragment`  
**Llamada desde app.py:** `mostrar_carrusel(df_rec, data_comp=data_comp_todos)`  
**Dataframes:**
- `df_rec` — todas las recolecciones
- `data_comp_todos` — comparativa Santiago + Regiones concatenadas

**Dataframes cargados internamente:** `cargar_estado_locales()`, `cargar_emergencias()`, `cargar_razones()` (la columna `Producto` ya viene resuelta por `resolver_recolecciones()` en app.py)  
**Función:** Slideshow por chofer con `st.pills` + toggle auto-avance (10 seg). Para el chofer activo renderiza: banner con Tanques Litros/Locales/Alta/Emergencias (widget #3–#6 vía `_tanque_b()`) → Donut Altair (#17) + Mini KPIs (#21) → Top5+ (#22) + Top5- (#23) + Productos (#25) + Razones (#24).

---

## 38. Tab Carrusel Zonas
**Archivo:** `components/tabs/tab_carrusel_zonas.py` — decorado con `@st.fragment`  
**Llamada desde app.py:** `mostrar_carrusel_zonas(df_sheets, df_rec, df_rec_stgo, df_rec_reg, df_regiones, choferes_todos, choferes_stgo, choferes_reg, data_comp_stgo=_dc_stgo, data_comp_reg=_dc_reg)`  
**Dataframes:** todos los dfs principales de app.py  
**Función:** Cicla entre 3 vistas: Global (#33) → Santiago (#34) → Regiones (#35). Navegación con ◀/▶ y auto-avance (20 seg). Usa las comparativas `_dc_stgo`/`_dc_reg` que llegan de app.py; solo recalcula `_preparar_datos_regiones()` como fallback si no se pasan.

---

## 39. Tab Recolecciones
**Archivo:** `components/tabs/tab_recolecciones.py`  
**Llamada desde app.py:** `mostrar_tab_recolecciones(df_rec)`  
**Dataframes:** `df_rec` (todas las recolecciones)  
**Función:** Renderiza Panel de chips por producto (#30) → `st.divider()` → Cards de choferes recolecciones (#31).

---

## 40. Tab Parametros
**Archivo:** `components/tabs/tab_parametros.py`  
**Llamada desde app.py:** `mostrar_parametros(df_rec, df_sheets, df_regiones, choferes_stgo, choferes_reg)`  
**Dataframes:**
- `df_rec["Patente_Real"]`, `df_rec["Litros"]` — en expander de diagnóstico
- `df_sheets` — tabla de columnas y diagnóstico Patente→Chofer
- `df_regiones["Zona"]` — tabla del mapa de zonas

**Carga internamente:** `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()` (dentro del expander de diagnóstico)  
**Función:** Muestra 2 Semáforos (#32) → 4 `st.metric` operacionales → tabla mapa de zonas → tablas de columnas de sheets → expander diagnóstico Patente→Chofer → expander configuración activa.

---

## 41. Tab Santiago v2
**Archivo:** `components/tabs/tab_v2.py`  
**Llamada desde app.py:** `mostrar_tab_v2(df_rec_stgo, choferes_filter=choferes_stgo, data_comp=_dc_stgo, tab_nombre="Santiago")`  
**Dataframes:**
- `df_rec_stgo` — recolecciones Santiago
- `_dc_stgo` — la misma comparativa Santiago calculada una sola vez en app.py (antes existía un recálculo `_dc_stgo_v2`, eliminado)
- `df_locales = cargar_estado_locales()` filtrado por `choferes_stgo`

**Función:** 5 Donuts Plotly KPI (#12–#16) + grid 6col de Cards de chofer v2 (#29), cada una con Mini métricas Litros/Locales/Alta (#26–#28).

---

## 42. Tab Global v2
**Archivo:** `components/tabs/tab_v2.py`  
**Llamada desde app.py:** `mostrar_tab_v2(df_rec, choferes_filter=choferes_todos, data_comp=data_comp_todos, tab_nombre="Global")`  
**Dataframes:**
- `df_rec` — todas las recolecciones
- `data_comp_todos` — comparativa Santiago + Regiones
- `df_locales = cargar_estado_locales()` filtrado por `choferes_todos`

**Función:** Idéntica al Tab Santiago v2 pero con datos de todos los choferes.

---

## 43. Tab Regiones v2
**Archivo:** `components/tabs/tab_v2.py`  
**Llamada desde app.py:** `mostrar_tab_v2(df_rec_reg, choferes_filter=choferes_reg, data_comp=_dc_reg, tab_nombre="Regiones")`  
**Dataframes:**
- `df_rec_reg` — recolecciones Regiones
- `_dc_reg = _preparar_datos_regiones(df_regiones, df_rec_reg)` — comparativa Regiones
- `df_locales = cargar_estado_locales()` filtrado por `choferes_reg`

**Función:** Idéntica al Tab Santiago v2 pero con datos de choferes de Regiones y comparativa calculada por nombre (sin patente).

---

## Tabla resumen: widget → dataframe que usa

| # | Widget | Dataframes de entrada | Carga internamente |
|---|--------|-----------------------|--------------------|
| 1 | `_css()` | — | — |
| 2 | `_header()` | — | — |
| 3 | Tanque Litros | `data_comp["LitrosHoy"]`, `data_comp["Prom"]` | — |
| 4 | Tanque Locales | `df_locales["Estado"]`, `df_rec["Razon"]` | — |
| 5 | Tanque Alta | `df_locales["Prioridad"]`, `df_rec["Razon"]` | — |
| 6 | Tanque Emergencias | `df_emerg_all`, `df_c["Emergencia"]` | — |
| 7 | Donut CSS Litros | `df_rec["Litros"]`, `data_comp["Prom"]` | `cargar_datos_regiones()` |
| 8 | Donut CSS Locales | `df_locales["Estado"]`, `df_rec["Razon"]` | — |
| 9 | Donut CSS Alta | `df_locales["Prioridad"]`, `df_rec["Razon"]` | — |
| 10 | Donut CSS Recolecciones | `df_rec["Litros"]`, `df_rec["Razon"]` | — |
| 11 | Donut CSS Rutas | `df_rec["FechaObservacion"]`, `df_locales["Chofer"]` | — |
| 12 | Donut Plotly Litros | `df_rec["Litros"]`, `data_comp["Prom"]`, `df_locales` | — |
| 13 | Donut Plotly Locales | `df_locales["Estado"]`, `df_rec["Razon"]` | — |
| 14 | Donut Plotly Alta | `df_locales["Prioridad"]`, `df_rec["Razon"]` | — |
| 15 | Donut Plotly Recolecciones | `df_rec["Litros"]`, `df_rec["Razon"]` | — |
| 16 | Donut Plotly Rutas | `df_rec["FechaObservacion"]`, `df_locales["Chofer"]` | — |
| 17 | Donut Altair desglose | `df_c["Razon"]`, `df_loc_ch["Estado","Prioridad"]` | `cargar_razones()` |
| 18 | ~~Grid compacto choferes~~ (eliminado) | — | — |
| 19 | Cards choferes con tanques | `df_rec`, `df_locales`, `data_comp` | — |
| 20 | Cards centros de acopio | `df_rec`, `data_comp`, `df_locales` | `cargar_datos_regiones()` |
| 21 | Mini KPIs carrusel | `df_c["Litros","Razon"]`, `df_loc_ch["Estado","Prioridad"]` | — |
| 22 | Top 5 más litros | `df_c["Litros","idLocalSistema","Local"]` | — |
| 23 | Top 5 menos litros | `df_c["Litros","idLocalSistema","Local"]` | — |
| 24 | Razones de fallo | `df_c["Razon"]` | `cargar_razones()` |
| 25 | Desglose productos (carrusel) | `df_c["Producto","Litros"]` | — |
| 26 | Mini métrica Litros | `data_comp["LitrosHoy","Prom"]` | — |
| 27 | Mini métrica Locales | `df_locales["Estado"]`, `df_rec["Razon"]` | — |
| 28 | Mini métrica Alta | `df_locales["Prioridad"]`, `df_rec["Razon"]` | — |
| 29 | Card chofer v2 | `data_comp`, `df_locales`, `df_rec` (vía `_metricas_choferes`) | — |
| 30 | Panel chips productos | `df_rec["Producto","Litros"]` | — |
| 31 | Cards choferes recolecciones | `df_rec["NombreChofer","Producto","Litros"]` | `cargar_estado_locales()`, `cargar_empleados()` |
| 32 | Semáforo umbrales | — (constantes del módulo) | — |
| 33 | Tab Global | `df_sheets`, `df_rec` | `cargar_estado_locales()` |
| 34 | Tab Santiago | `df_sheets`, `df_rec_stgo` | `cargar_estado_locales()` |
| 35 | Tab Regiones | `df_regiones`, `df_rec_reg`, `_dc_reg` | `cargar_estado_locales()` |
| 36 | Tab Rendimiento | `df_rec` | `cargar_razones()` |
| 37 | Tab Carrusel | `df_rec`, `data_comp_todos` | `cargar_estado_locales()`, `cargar_emergencias()`, `cargar_razones()` |
| 38 | Tab Carrusel Zonas | `df_sheets`, `df_rec`, `df_rec_stgo`, `df_rec_reg`, `df_regiones` | vía tabs internos |
| 39 | Tab Recolecciones | `df_rec` | vía sub-widgets |
| 40 | Tab Parametros | `df_rec`, `df_sheets`, `df_regiones` | `cargar_usuarios_vehiculos()`, `cargar_vehiculos()`, `cargar_empleados()` |
| 41 | Tab Santiago v2 | `df_rec_stgo`, `_dc_stgo` | `cargar_estado_locales()` |
| 42 | Tab Global v2 | `df_rec`, `data_comp_todos` | `cargar_estado_locales()` |
| 43 | Tab Regiones v2 | `df_rec_reg`, `_dc_reg` | `cargar_estado_locales()` |
