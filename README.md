# bcra-pagos-minoristas-xlsx-to-parquet

Herramienta en Python para descubrir, descargar, parsear, normalizar y almacenar los archivos XLSX publicados por el BCRA como datasets listos para análisis.

## Qué resuelve

Este proyecto convierte planillas XLSX dispersas en salidas reproducibles y orientadas a analítica, con énfasis en:

- descubrimiento automático de archivos publicados, incluso cuando cambian los nombres o URLs
- descarga trazable de los originales
- parseo de libros de Excel con metadatos de estructura
- normalización de tablas con columnas consistentes, sin acentos y en snake_case
- preservación de la fecha original y creación de una fecha mensual canónica al inicio de mes
- almacenamiento en Parquet y, de forma opcional, Delta Lake
- metadatos de ingesta para auditoría y repetibilidad

## Flujo general

El pipeline sigue esta secuencia:

1. Discovery: localiza los XLSX candidatos.
2. Downloader: baja los archivos seleccionados al directorio raw.
3. Parser: extrae hojas, filas, columnas y tipos inferidos.
4. Normalizer: aplica reglas de normalización y metadatos de ingesta.
5. Storage: escribe salidas en data/curated.

## Estructura del repositorio

- src/bcra_pagos_minoristas_xlsx_to_parquet: paquete principal.
- specs: especificaciones funcionales y de ingeniería.
- data/raw: archivos XLSX descargados.
- data/curated: datasets normalizados y almacenados.
- data/metadata: metadatos generados por los comandos CLI.
- tests: pruebas unitarias e integrales con fixtures locales.

## Requisitos

- Python 3.10 o superior.
- uv para instalar dependencias y ejecutar comandos.

## Instalación

```bash
uv sync
```

## Configuración

La configuración se lee desde bcra.toml por defecto. También se pueden usar variables de entorno con el prefijo BCRA__.

Ejemplo mínimo:

```toml
[source]
url = "https://www.bcra.gob.ar"
match_rules = ["\\.xlsx$"]

[download]
output_dir = "data/raw"
retries = 3
timeout_seconds = 30

[parser]
engine = "polars"

[storage]
format = "parquet"
output_dir = "data/curated"
partition_by = []
mode = "append"
```

Ejemplo de override por entorno:

```bash
set BCRA__PARSER__ENGINE=pandas
```

## Uso

La CLI expone cuatro comandos principales:

```bash
bcra-pagos-minoristas-xlsx-to-parquet fetch
bcra-pagos-minoristas-xlsx-to-parquet parse
bcra-pagos-minoristas-xlsx-to-parquet build
bcra-pagos-minoristas-xlsx-to-parquet run
```

Opciones globales:

- --config PATH: ruta al archivo TOML de configuración.
- --log-level LEVEL: nivel de logging.

Comandos:

- fetch: descubre y descarga XLSX.
- parse: convierte los libros descargados en datasets estructurados.
- build: normaliza y persiste en Parquet o Delta Lake.
- run: ejecuta el pipeline completo de punta a punta.

## Salidas esperadas

- data/raw: XLSX originales descargados.
- data/curated: datos listos para consulta analítica.
- data/metadata: JSON con metadatos de discovery, download, parse, build y run.

## Pruebas

Las pruebas deben ser deterministas y no depender de endpoints en vivo.

```bash
uv run python -m pytest
```

## Estado del proyecto

El repositorio está alineado con una arquitectura modular y declarativa, pensada para sumar nuevos conjuntos de datos del BCRA sin romper el flujo existente.

## Licencia

Este proyecto se publica bajo la licencia MIT. Ver el archivo LICENSE.
