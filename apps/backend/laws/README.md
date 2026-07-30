# Laws Directory

Este directorio contiene los PDFs de las leyes chilenas para indexar en el RAG.

## Archivos a incluir

Descarga los PDFs oficiales desde [bcn.cl](https://www.bcn.cl/leyes):

1. `codigo_trabajo.pdf` - Código del Trabajo (DFL 1 de 1994)
2. `codigo_civil.pdf` - Código Civil
3. `codigo_comercio.pdf` - Código de Comercio
4. `ley_proteccion_consumidor.pdf` - Ley 19.496
5. `ley_tribunales_familia.pdf` - Ley 19.968
6. `ley_menores.pdf` - Ley 16.618
7. `ley_sistema_filiacion.pdf` - Ley 19.585

## Indexación

Para indexar las leyes:

```bash
docker exec legal-ai-backend python -m workers.law_indexer /app/laws
```

## Búsqueda automática

El sistema busca automáticamente en las leyes indexadas cuando genera análisis.
