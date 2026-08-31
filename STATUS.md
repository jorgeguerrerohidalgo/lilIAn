# STATUS - Corpus Legal Chileno

> Documento de estado para reanudar trabajo en nueva sesion.
> Generado: 2026-08-31

## Contexto

Lilian es una plataforma SaaS legal chilena. El objetivo es tener un corpus legal completo (~6.000 normas chilenas) que permita responder todas las dudas legales en Chile via RAG. El corpus esta en Supabase (Postgres + pgvector).

Pipeline: BCN legacy obtxml?opt=7&idNorma=X -> BCNHttpClient -> BCNXmlParser -> DBWriter -> law_chunks (con embeddings OpenAI text-embedding-3-small 1536-dim) -> search_laws_by_embedding (vector) + search_chunks_by_keyword (BM25) -> hybrid_search (RRF fusion).

## Commits relevantes

```
4fd2e37  feat(sh): v4 re-ingest script + endpoint uses correct BCN idNormas  <- HEAD, pushado
bd86372  docs: STATUS - handoff document for new chat context
ebf01cf  fix(ingest): use correct BCN idNormas (1209272 for 21.719) + add 18046, 19496
f87f875  feat(sh): add v3 script - re-ingest post-VARCHAR migration + reindex + eval
225df76  fix(corpus): route /corpus/search through search_laws_by_embedding
9feff4f   fix(rag): lower similarity_threshold defaults; fix eval + golden paths
```

## Estado del corpus

Tablas en Supabase:
- norm_catalog: ~11 normas (5 Codigos + 4 leyes + Constitucion + 19.628 + 18.046 + 19.496)
- law_chunk_versions: ~10 versiones vigentes
- law_chunks: ~12.000 chunks totales, todos con embeddings de OpenAI
- norm_relations: vacia (grafo de relaciones no implementado)

Por ley (idNorma BCN):

| idNorma | Ley | Chunks | Refundido |
|---|---|---|---|
| 172986 | Codigo Civil | ~2.600 | OK |
| 1984 | Codigo Penal | ~680 | OK |
| 207436 | Codigo del Trabajo | ~739 | OK |
| 22740 | Codigo de Comercio | 0 (parser falla) | ERROR |
| 176595 | Codigo Procesal Penal | ~564 | OK |
| 242302 | Constitucion | ~225 | OK |
| 1209272 | Ley 21.719 (refundida) | 12 | OK |
| 19628 | (idNorma incorrecto: devuelve Decreto MINEDUC) | 2 | ERROR |
| 18046 | Ley 18.046 (Sociedad Anonima) | 2 | OK |
| 19496 | Ley 19.496 (Consumidor) | 2 | OK |

Recall@10 actual: 30% (6/20 PASS). Limitado por:
- P1: 19628 no es la Ley 19.628 (el corpus tiene un documento incorrecto)
- P3: 22740 (Codigo de Comercio) parser falla por ser archivo de 57 MB

## Bugs conocidos (de la auditoria del agente)

| # | Severidad | Bug | Ubicacion |
|---|---|---|---|
| P1 | HIGH | 19628 no resuelve a la Ley 19.628 (devuelve Decreto MINEDUC) | ingest_bcn_corpus.py:71 |
| P2 | HIGH | law_code almacena idNorma BCN (1209272) pero golden espera alias cortos (21719). Mismatch causa recall@10 ~30% | db_writer.py:293 + eval_law_retrieval.py:149 + golden-dataset-v2.json |
| P3 | HIGH | Codigo de Comercio (22740) XML de 57 MB hace que el parser se cuelgue (OOM o minutos por parseo) | bcn_xml_parser.py:103,143 |
| P4 | MED | law_chunks sin UNIQUE constraint -> re-ingest duplica chunks | db_writer.py:324 |
| P5 | MED | Credenciales hardcoded en eval_law_retrieval.py:62-63 | eval_law_retrieval.py:62 |
| P6 | MED | cmd_sync ignora --since y re-corre todo Tier 1 | ingest_bcn_corpus.py:284 |
| P7 | MED | reindex_chunks.py rate-limit plano sin backoff en 429 | reindex_chunks.py:84-86 |
| P8 | MED | _ingest_one traga toda Exception per norm | ingest_bcn_corpus.py:264 |

## Plan de correcciones pendientes

Orden por DEPENDENCIA, no por comodidad. Dos reglas que mandan sobre todo lo demas:

1. **No re-ingestar antes de tener el UNIQUE constraint (P4).** Hoy law_chunks no lo tiene,
   asi que correr fix_corpus_v4.sh duplica chunks en vez de reemplazarlos y el recall EMPEORA.
2. **Medir antes de cambiar el corpus.** P2 es un mismatch de etiquetas, no de contenido.
   Si re-ingestas primero, no vas a poder separar cuanto del recall era etiqueta y cuanto
   era corpus faltante.

### Fase 1 - Medicion limpia (no toca la DB, no bloquea con nadie)
- P2: Actualizar golden-dataset-v2.json con idNorma BCN (1209272 para 21.719, no 21719)
- Re-correr eval_law_retrieval -> este es el baseline REAL, no el 30% actual
- Salida esperada: separa "recall perdido por etiqueta" de "recall perdido por corpus"

### Fase 2 - Prerequisitos de re-ingest (bloquea la Fase 4)
- P4: Migracion Alembic con UNIQUE en law_chunks (law_code, version_id, chunk_index)
- P5: Quitar credenciales hardcoded de eval_law_retrieval.py:62
- P8: Reemplazar el except Exception de _ingest_one por log estructurado
  (mientras siga ahi, una ingesta fallida se ve igual que una exitosa)

### Fase 3 - Contenido faltante (es lo unico que sube el recall de verdad)
- P1: [BLOQUEANTE MANUAL - lo resuelve Jorge en el navegador]
      Buscar el idNorma refundido de 19.628 en https://www.bcn.cl/leychile/Navegar?idNorma=19628
      Ya se descarto por SPARQL, opt=7 (9 IDs) y opt=3 paginado. Requiere inspeccion visual.
- P3: lxml.etree.iterparse + element.clear() en bcn_xml_parser.py para el Codigo de Comercio
      (22740, 57 MB). Sin esto queda en 0 chunks para siempre.

### Fase 4 - Re-ingest y validacion (solo despues de 2 y 3)
- bash scripts/sh/fix_corpus_v4.sh
- reindex de embeddings
- eval final contra el criterio de exito

### Fase 5 - Fuera del camino critico
- P6: Hacer que cmd_sync respete --since (hoy re-corre todo Tier 1)
- P7: Backoff en 429 para reindex_chunks.py

### Fase 6 - Tier 2/3 completo
- discover_bcn_catalog.py con opt=3 paginado
- cmd_ingest_tier2 para las 100 leyes mas citadas
- cmd_ingest_all para las ~6.000 normas restantes

## Plan de pruebas

### Tests unitarios a agregar
1. tests/test_bcn_xml_parser.py (ya existen 10, agregar 5 mas):
   - test_parses_libro_titulo_capitulo_headings
   - test_keeps_derogados_with_flag
   - test_handles_unicode_in_titles
   - test_iterparse_handles_large_xml (Codigo de Comercio 57 MB con streaming)
   - test_unique_constraint_dedupes_reingest

2. tests/test_bcn_http_client.py (ya existen 6, agregar 3 mas):
   - test_rotates_user_agent_on_403
   - test_retries_on_5xx_with_backoff
   - test_cache_respects_ttl

3. tests/test_corpus_e2e.py (nuevo):
   - test_e2e_pipeline_q1_to_q20
   - test_e2e_temporal_versioning
   - test_e2e_graph_relations

### Criterio de exito
- recall@10 >= 0.85 en el golden dataset v2
- Tests pytest pasando con coverage >= 80%
- Cobertura de Tier 1 completa

## Comandos para continuar

### Diagnosticar el estado actual
```bash
cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
git log --oneline -10
git status
```

### Re-ingestar con idNorma correctos
```bash
cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
bash scripts/sh/fix_corpus_v4.sh
```

### Re-correr el eval
```bash
cd apps/backend
.venv_test/bin/python -m scripts.eval_law_retrieval
```

### Verificar el corpus
```sql
SELECT law_code, COUNT(*) as total, COUNT(embedding_vec) as emb
FROM law_chunks
GROUP BY law_code
ORDER BY law_code;
```

### Buscar idNorma refundido de 19.628
1. Navegador: https://www.bcn.cl/leychile/Navegar?idNorma=19628
2. Buscar la version refundida con las modificaciones de la 21.719
3. Reportar el idNorma que aparece en la URL

### Suite de tests
```bash
cd apps/backend
.venv_test/bin/python -m pytest tests/test_bcn_xml_parser.py tests/test_bcn_http_client.py -v
```

## Archivos clave

| Archivo | Rol |
|---|---|
| apps/backend/scripts/ingest_bcn_corpus.py | CLI principal de ingest |
| apps/backend/scripts/bcn_http_client.py | Cliente HTTP con rate limit y cache |
| apps/backend/scripts/bcn_xml_parser.py | Parser XML con jerarquia (libro/titulo/capitulo/articulo) |
| apps/backend/scripts/db_writer.py | Escritor a Postgres (upsert idempotente) |
| apps/backend/scripts/reindex_chunks.py | Regenera embeddings con OpenAI |
| apps/backend/scripts/eval_law_retrieval.py | Evalua recall@10 contra golden dataset |
| docs/corpus/golden-dataset-v2.json | 20 preguntas de prueba |
| docs/corpus/STATUS_REPORT.md | Reporte anterior (no es este archivo) |
| apps/backend/app/models/norm_catalog.py | Catalogo de normas (idNorma, tipo, titulo, etc.) |
| apps/backend/app/models/law_chunk.py | Chunks del corpus (jerarquico + embeddings) |
| apps/backend/app/models/law_chunk_version.py | Versiones temporales por norma |
| apps/backend/app/models/norm_relation.py | Grafo de relaciones modifica/deroga (vacio) |
| apps/backend/app/api/endpoints/corpus.py | Endpoint RAG con filtros jerarquicos y temporales |
| apps/backend/migrations/add_norm_catalog_and_versions.py | Crea las 3 tablas nuevas del corpus |
| apps/backend/migrations/add_ley_21719_tables.py | Migracion Ley 21.719 |

## Contexto de la nueva sesion

Si abres un nuevo chat, pegale al inicio:

```
Estamos reconstruyendo el corpus legal chileno de Lilian. El pipeline BCN -> XML -> ingest
funciona. El recall@10 esta en 30% por mismatch entre los idNorma BCN (que el pipeline
ingiere) y los nombres cortos que el golden dataset espera. Acabo de actualizar el script
ingest_bcn_corpus.py con los idNorma BCN correctos: 172986, 1984, 207436, 22740, 176595,
242302, 1209272, 19628 (que es incorrecto, devuelve Decreto MINEDUC), 18046, 19496.

Estado actual:
- Script de re-ingest v4 YA COMMITEADO en scripts/sh/fix_corpus_v4.sh (4fd2e37, en origin/main).
  No hay que recrearlo. No usar el v3: tiene el idNorma 21719, el bug original.
- Arbol de git limpio, HEAD en origin/main
- 12.000 chunks en law_chunks, todos con embeddings
- 19628 devuelve Decreto, no Ley 19.628 refundida (P1)
- 22740 falla por ser archivo de 57 MB (P3)
- Golden dataset v2 no actualizado con idNorma BCN (P2)

Proximos pasos (ORDEN CORREGIDO - respeta dependencias):
1. Actualizar golden-dataset-v2.json con idNorma correctos (1209272) y re-correr el eval.
   Esto da el baseline REAL. Hacerlo ANTES de tocar el corpus, si no no se puede separar
   cuanto del recall se pierde por etiqueta y cuanto por corpus faltante.
2. Agregar UNIQUE constraint en law_chunks (Alembic). PREREQUISITO de cualquier re-ingest:
   sin esto, correr fix_corpus_v4.sh duplica chunks y el recall empeora.
3. Limpieza: quitar credenciales hardcoded (eval_law_retrieval.py:62) y el except Exception
   de _ingest_one.
4. Buscar el idNorma refundido de 19.628 en BCN a mano (bloqueante, lo hace Jorge).
5. Parser streaming (iterparse) para el Codigo de Comercio (22740, 57 MB).
6. RECIEN ACA: re-ingestar con el script v4 + reindex + eval final.
7. Suite de tests completa.

Nota: el orden viejo ponia el re-ingest en el paso 3 y el UNIQUE constraint en el 6.
Eso estaba mal y duplicaba chunks.
```

## Advertencias importantes

- **NO correr fix_corpus_v4.sh antes de agregar el UNIQUE constraint (P4).** law_chunks no lo
  tiene todavia, asi que el re-ingest DUPLICA chunks en lugar de reemplazarlos y el recall baja
- No re-correr el script v3 con delete seguido de re-ingest sin antes buscar el idNorma refundido de 19.628
- El corpus va a quedar con un documento incorrecto (Decreto MINEDUC) en lugar de la Ley 19.628
- El codigo de Comercio (22740) requiere parser streaming (iterparse) antes de poder re-ingestarse
- El script v4 esta en `scripts/sh/fix_corpus_v4.sh` y SI esta commiteado (4fd2e37, pushado a origin/main). No hace falta recrearlo
- No usar el script v3: sigue teniendo el idNorma 21719 (el bug original)
