# Contributing

Gracias por interesarte en contribuir.

## Cómo empezar

1. Instala dependencias con `uv sync`.
2. Ejecuta las pruebas con `uv run pytest`.
3. Mantén los cambios pequeños y enfocados.

## Criterios generales

- Las pruebas deben ser deterministas y usar fixtures locales.
- No dependas de endpoints en vivo para validar cambios.
- Conserva la estructura existente de configuración y pipeline.
- Si agregas un nuevo dataset, documenta su comportamiento y salidas.

## Antes de abrir un PR

- Verifica que el README siga siendo correcto.
- Asegúrate de no romper la CLI ni el formato de metadatos.
- Incluye pruebas para cualquier cambio de comportamiento.

## Estilo

- Sigue el estilo existente del repositorio.
- Prefiere cambios pequeños, trazables y fáciles de revisar.
