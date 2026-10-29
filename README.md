# statcan-labour-lab

Cruces de mercado laboral con tablas abiertas de Statistics Canada, en DuckDB + pandas.

## Uso

```bash
pip install -e .
python -m statcan_lab freshness        # rango de fechas y release de cada tabla (WDS)
python -m statcan_lab fetch            # baja las 4 tablas completas y las carga a data/statcan.duckdb
python -m statcan_lab describe 14-10-0471-01   # dimensiones y valores reales de una tabla
python -m statcan_lab run ei_gap       # EI regular por desempleado, por provincia y mes
python -m statcan_lab run immigrant_gap  # brecha de desempleo por estatus migratorio vs nacidos en Canada
python -m statcan_lab run degree_ratio # desempleados por vacante segun nivel educativo
python -m statcan_lab run explore      # panel provincia x mes, correlacion con rezagos, outliers
```

Resultados en `out/*.csv` (listos para Power BI o Looker Studio).

## App web (Streamlit) y refresco automatico

- `app/streamlit_app.py` lee los CSV de `published/` y nunca llama a StatCan en vivo.
- `python -m statcan_lab publish` baja datos frescos y regenera `published/` (con meta.json de frescura y errores).
- `.github/workflows/refresh.yml` corre ese comando cada lunes en GitHub Actions y hace commit si hay cambios.
- `published_demo/` trae datos SINTETICOS para ver la app antes de tener datos reales. La app muestra un
  banner rojo cuando los usa. Cuando exista `published/`, la app usa esa carpeta y ya no muestra el demo
  (puedes borrar `published_demo/`).

Despliegue en Streamlit Community Cloud: repositorio `<usuario>/statcan-labour-lab`, branch `main`,
main file path `app/streamlit_app.py`. Primer refresco real: GitHub, pestana Actions, "Refresh StatCan data", "Run workflow".

## Antes de confiar en los resultados

El entorno donde se escribio este codigo no tenia acceso a StatCan, asi que se probo con datos
sinteticos que imitan el formato de las descargas (`tests/`). Lo que eso valida: la carga, la
conversion de escala (miles a personas), los filtros, los cruces y la deteccion de rezagos.
Lo que NO valida: los nombres exactos de dimensiones y categorias de las tablas reales.

1. Corre `fetch` y luego `describe` en cada tabla.
2. Ajusta los regex de `src/statcan_lab/config.py` a lo que veas.
3. Si un filtro no coincide, el codigo falla con la lista de valores disponibles (no suma categorias por accidente).

Puntos a verificar en particular: `14-10-0287-03` (se asume provincia sin sexo/edad), la categoria
"Born in Canada" y los nombres de grupos migratorios en `14-10-0471-01`, y las dimensiones de
`14-10-0443-01` (el analisis `degree_ratio` es el menos seguro).

## Tests

```bash
PYTHONPATH=src:tests python -m unittest discover -s tests -v
```

## Lecturas con cuidado

- `ei_per_unemployed` no es una tasa de cobertura: beneficiarios (semana de referencia, administrativo)
  y desempleados (LFS, incluye gente que nunca trabajo o no califica) miden cosas distintas.
- Las correlaciones del panel son descriptivas. Con tablas separadas no hay causalidad.
- `14-10-0471-01` es media movil de 3 meses sin ajuste estacional; el resto es ajustado. Sirve para brechas y tendencias, no para comparar niveles mes a mes.
