# App Monitor

Dashboard operacional de recolección de aceite (Streamlit). Muestra en tiempo real
litros recolectados vs esperado, estado de locales por ruta, prioridad alta,
emergencias y rendimiento por chofer, para Santiago y Regiones.

## Cómo correr

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requiere `.streamlit/secrets.toml` — copiar `secrets.example.toml` y completar.

**Auth:** la maneja Streamlit Cloud con whitelist de correos. La app no implementa
autenticación propia.

## Fuentes de datos (solo lectura)

| Fuente | Qué entrega | TTL caché |
|---|---|---|
| MySQL (`appsheet_db`) | `VistaMonitor` (recolecciones del día), `LocalesRuta`, `Emergencias`, `Usuarios` | 5–60 min |
| PostgreSQL (`rendering_db2`) | Empleados, productos, vehículos, razones de fallo (catálogos) | 1 h |
| Google Sheets | Promedios esperados 3M: hoja Santiago y hoja Control Regiones | 5 min |

Si una fuente está caída, el conector muestra `st.error` y retorna un DataFrame
vacío: el dashboard sigue vivo y reintenta cuando vence el TTL de la caché.

## Estructura

```
app.py                      # carga de datos, navegación (solo se renderiza la vista activa)
config.py                   # constantes únicas: umbrales, EXCLUIR_LITROS, intervalos
connectors/                 # mysql.py, postgres.py, sheets.py (todos con @st.cache_data)
components/
  helpers/
    kpis.py                 # cálculo centralizado de los 5 KPIs y exitosa/fallida
    data_prep.py            # comparativas litros vs esperado (Santiago por patente, Regiones por nombre)
    id_resolver.py          # IDs → nombres (chofer, peonetas, patente, producto)
  widgets/                  # tanques, donuts CSS, cards, layout
  tabs/                     # una vista por archivo
```

Inventarios detallados: [DATAFRAMES.md](DATAFRAMES.md) y [WIDGETS.md](WIDGETS.md).
