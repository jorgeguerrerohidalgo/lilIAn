# Corpus Legal Chileno — Estrategia y Operación

> Documento vivo. Última revisión: 2026-08-29.
> Audiencia: equipo técnico + producto + legal.

## 1. Resumen ejecutivo

Lilian mantiene un **corpus legal chileno** indexado en `law_chunks` para alimentar el RAG jurídico. La fuente primaria es el **dataset abierto de la BCN** (`https://datos.bcn.cl`), enriquecido con texto curado para normas que el SPARQL no entrega en formato usable. El corpus soporta:

- Búsqueda híbrida (embedding + keyword + RRF) con filtros por área legal, jerarquía (libro / título / capítulo), y **versionado temporal** (`as_of`).
- Trazabilidad: cada chunk sabe qué versión de qué norma es, qué rango temporal cubría, y desde qué fuente se ingirió.
- Knowledge graph de relaciones (`modifica`, `deroga`, `rectifica`, `refunde`, `prorroga`, `reglamenta`) entre normas.

**Métricas objetivo**:
- Tier 1 (5 Códigos + Ley 21.719 + Ley 19.628 + 25 leyes frecuentes) → **~6.000 chunks**
- Golden dataset de 20 preguntas → `recall@5 ≥ 0.85`
- Latencia RAG p95 < 200 ms

---

## 2. Arquitectura del corpus

```
BCN Open Data (SPARQL endpoint)
       │
       │ SPARQL query (catalog, versions, relations)
       ▼
BCNClient (apps/backend/scripts/bcn_client.py)
       │
       │ cache en disco: apps/backend/.cache/bcn/
       ▼
HTMLParser (apps/backend/scripts/html_parser.py)
       │
       │ ParsedChunk[] jerárquico (libro/titulo/capitulo/artículo)
       ▼
DBWriter (apps/backend/scripts/db_writer.py)
       │
       │ UPSERT idempotente
       ▼
norm_catalog + law_chunk_versions + law_chunks
       │
       │ JOIN via version_id + norm_id
       ▼
hybrid_search() en app/services/rag.py
       │
       │ con filtros: legal_area, law_code, libro, capitulo, as_of
       ▼
/api/v1/corpus/search → /precedents en el frontend
```

### 2.1 Modelo de datos (ver `app/models/`)

| Tabla | Propósito | Filas típicas |
|---|---|---|
| `norm_catalog` | 1 fila por norma (BCN id, tipo, número, título, área legal, estado, current_version_id, repealed_by_norm_id) | ~6.000 (Tier 3 completo) |
| `law_chunk_versions` | N filas por norma, una por snapshot histórico (valid_from, valid_until, is_current, source_url, raw_source_hash) | 6.000 × ~2 versiones = ~12.000 |
| `norm_relations` | Aristas del grafo (from_norm_id, to_norm_id, relation_type, article_ref) | ~50.000 (Tier 3) |
| `law_chunks` | El corpus en sí. Cada chunk tiene jerarquia_path, parent_chunk_id, libro/titulo/capitulo/articulo/inciso/numeral/letra, norm_id, version_id | ~24.000 (Tier 3) |

### 2.2 Versionado temporal

`law_chunks.version_id` apunta a `law_chunk_versions.id`. La query RAG aplica este filtro cuando se pasa `as_of`:

```sql
AND version_id IN (
  SELECT id FROM law_chunk_versions v
  WHERE v.valid_from <= :as_of
    AND (v.valid_until IS NULL OR v.valid_until > :as_of)
)
```

Esto permite responder *"¿qué establecía este artículo en 2023?"* correctamente cuando hay una versión histórica y otra vigente.

---

## 3. Operación

### 3.1 Ingerir Tier 1 (ahora)

```bash
cd apps/backend

# 1. Descargar manualmente las normas Tier 1 que faltan desde el BCN o DO.
#    Los archivos .txt van a apps/backend/data/legal_dumps/<bcn_id>.txt

# 2. Cargar el catálogo + ingestar:
.venv_test/bin/python -m scripts.ingest_bcn_corpus list
.venv_test/bin/python -m scripts.ingest_bcn_corpus ingest-tier1

# 3. Evaluar el golden dataset:
.venv_test/bin/python -m scripts.eval_law_retrieval
```

`ingest-tier1` itera sobre `TIER1_BCN_IDS` en `scripts/ingest_bcn_corpus.py` e ingiere los que tengan dump local.

### 3.2 Re-ingestar una norma específica

```bash
.venv_test/bin/python -m scripts.ingest_bcn_corpus ingest --bcn-id=1984
```

Esto:
1. Lee `data/legal_dumps/1984.txt`.
2. Parsea con jerarquía.
3. Crea/actualiza la fila en `norm_catalog`.
4. Crea una nueva `law_chunk_versions` (con la fecha actual como `valid_from`).
5. Marca las versiones previas como `is_current=false` con `valid_until = fecha_actual`.
6. Inserta los chunks con `version_id = nuevo`.

### 3.3 Golden dataset

`docs/corpus/golden-dataset-v2.json` tiene 20 preguntas con respuestas esperadas (artículos + códigos de ley). El evaluador `scripts/eval_law_retrieval.py` corre cada pregunta contra el corpus y mide `recall@5`. Umbral CI: ≥ 0.85.

Incluye 3 preguntas con `as_of` específico para validar el versionado temporal (Q18, Q19, Q20).

### 3.4 Búsqueda desde la UI

`/precedents` tiene un panel de búsqueda con los filtros:
- Texto libre (mín. 3 caracteres)
- Área legal (dropdown)
- Norma (dropdown poblado desde `/corpus/norms`)
- Libro (solo Códigos)
- Capítulo
- Fecha `as_of` (filtro temporal)

Cada resultado muestra `jerarquia_path` y `article_number` para citación precisa.

---

## 4. Decisiones de diseño

### 4.1 ¿Por qué local dumps + script de ingest en lugar de scraping directo del BCN?

La BCN usa una SPA Angular con reCAPTCHA de Google. Ningún endpoint público devuelve el texto plano de las normas (probamos 4 URLs distintas, todas sirven el mismo shell de 9.6 KB). Scraping requeriría Playwright (~100 MB de browsers) o破解 del captcha (ilegal).

**Decisión**: el operador descarga manualmente las normas Tier 1 desde el navegador (Ctrl+S como HTML, o copia del Diario Oficial) y las deja en `apps/backend/data/legal_dumps/<bcn_id>.txt`. El script ingiere desde ahí. Es trabajo humano pero escala: Tier 1 son ~30 normas; Tier 3 serían ~6.000 y se automatiza con Playwright en Fase 3.

### 4.2 ¿Por qué JSON y no JSONB en Postgres?

SQLAlchemy mapea `JSON` a JSON nativo en Postgres (funcional para `extra`, `modifies_norm_ids`) y a TEXT en SQLite (tests). Sacrificamos el rendimiento de operadores GIN en `modifies_norm_ids`, pero ese campo se lee entero en UI y nunca se hace query dentro. Si en el futuro queremos GIN index sobre JSON, migramos esa columna específica a JSONB con `.with_variant(JSONB(), "postgresql")`.

### 4.3 ¿Por qué embeddings OpenAI y no locales?

OpenAI `text-embedding-3-small` cuesta **~$0.50** para ingestar las 6.000 normas Tier 1. La alternativa local (`sentence-transformers` con `BAAI/bge-m3`) cuesta 0 en dinero pero suma 1 dependencia operacional y posibles problemas de memoria en Railway free tier.

**Decisión**: mantener OpenAI mientras el costo mensual sea < $200. Migrar a `sentence-transformers` local en Fase 3 (cuando el corpus completo tenga ~24.000 chunks y reindex mensual cueste ~$15).

### 4.4 ¿Por qué un cliente SPARQL propio en lugar de `rdflib`?

`rdflib` interprete SPARQL es overkill: solo necesitamos 3 queries (catálogo, versiones, relaciones), todas parametrizadas. `httpx.post` directo es ~10× más rápido de cargar en memoria y suficiente para nuestro uso. Si en Fase 3 necesitamos CONSTRUCT con N-Triples para poblar el grafo completo, ahí sí evaluamos `rdflib`.

---

## 5. Riesgos conocidos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | El BCN SPARQL cambia la ontología | Pin a la versión actual; tests de parser contra respuestas fijas; al primer fallo, actualizar cliente. |
| R2 | El corpus crece más allá de 50k chunks | pgvector HNSW actual aguanta ~50k con m=16, ef_search=40. Más allá, migrar a Qdrant o particionar por área legal. |
| R3 | OpenAI cambia el modelo de embeddings | Reindex script listo; encriptar cache del corpus para no tener que re-embedar. |
| R4 | Operador abandona la curación manual de Tier 3 | Fase 3 introduce Playwright + navegador headless para automatización parcial. |
| R5 | Tier 1 incompleto (faltan Códigos) | `ingest-tier1` loggea los faltantes con la ruta exacta del dump. Documentamos `TIER1_BCN_IDS` con placeholders que el operador confirma con `bcn_client.query_norms(limit=5)`. |

---

## 6. Roadmap

| Fase | Alcance | Esfuerzo |
|---|---|---|
| 1 (esta sesión) | Modelos + crawler BCN + parser jerárquico + DBWriter + CLI + RAG temporal + endpoints + frontend + golden dataset | ✅ Completa |
| 2 (siguiente sprint) | Tier 2 (~100 leyes más citadas) + jurisprudencia Poder Judicial + grafo completo | 1 semana |
| 3 (mes) | Tier 3 (~6.000 normas restantes) + automatización con Playwright + embeddings locales + actualizaciones diarias | 1 mes |

---

## 7. Comandos útiles

```bash
# Listar estado del Tier 1
.venv_test/bin/python -m scripts.ingest_bcn_corpus list

# Ingestar una norma específica
.venv_test/bin/python -m scripts.ingest_bcn_corpus ingest --bcn-id=1984

# Re-ingestar Tier 1
.venv_test/bin/python -m scripts.ingest_bcn_corpus ingest-tier1

# Evaluar RAG con golden dataset
.venv_test/bin/python -m scripts.eval_law_retrieval

# Búsqueda manual desde Python
.venv_test/bin/python -c "
from app.services.rag import hybrid_search
results = hybrid_search(
    query='plazo prescripción acción laboral',
    organization_id=1, matter_id=0, top_k=5,
)
for r in results:
    print(r['chunk_id'], r['law_name'], 'art.', r['article_number'])
"

# Búsqueda con filtro temporal
.venv_test/bin/python -c "
from datetime import date
from app.services.rag import hybrid_search
results = hybrid_search(
    query='consentimiento para tratamiento de datos',
    organization_id=1, matter_id=0, top_k=5,
    as_of=date(2024, 6, 1),  # antes de la Ley 21.719
)
for r in results:
    print(r['law_name'], 'art.', r['article_number'])
"
```

---

## 8. Referencias cruzadas

- `apps/backend/scripts/bcn_client.py` — cliente SPARQL
- `apps/backend/scripts/html_parser.py` — parser jerárquico
- `apps/backend/scripts/db_writer.py` — escritor a Postgres
- `apps/backend/scripts/ingest_bcn_corpus.py` — CLI crawler
- `apps/backend/scripts/eval_law_retrieval.py` — evaluación RAG
- `apps/backend/app/services/rag.py` — RAG con filtros temporales
- `apps/backend/app/api/endpoints/corpus.py` — endpoints /api/v1/corpus/*
- `apps/backend/app/models/norm_catalog.py` — modelo del catálogo
- `apps/backend/app/models/law_chunk_version.py` — modelo de versionado
- `apps/backend/app/models/norm_relation.py` — modelo del grafo
- [`docs/lilian-3.0.md` §4.2](../lilian-3.0.md) — arquitectura general
