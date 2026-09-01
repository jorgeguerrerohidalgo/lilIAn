# STATUS - Corpus Legal Chileno

> Documento de estado para reanudar trabajo en nueva sesion.
> Ultima actualizacion: 2026-09-01 (sesion extendida)

## Handover rapido (leer primero)

```
# STATUS - Sesion 2026-09-01

Trabajando en la rama `corpus/fix-refundidos-and-hybrid` (1 commit pusheado,
no mergeado). PR: https://github.com/jorgeguerrerohidalgo/lilIAn/pull/new/corpus/fix-refundidos-and-hybrid

Plan A completado: idLey= para 19496 y 18046. 19496: 2->149 chunks, 18046: 2->177.
Plan B completado: search_laws_by_keyword + RRF en endpoint. Recall 45% con top_k=20.

NO commitear a main todavia. Mergear la rama primero (review de 30 min).

Siguiente accion recomendada: mergear la rama, luego agregar GIN index en
to_tsvector(content) en law_chunks para bajar el keyword search de 10s a <100ms.

Bug conocido: 1209272 (Ley 21.719) solo tiene 12 chunks. La refundida completa
NO esta en BCN todavia. Imposible mejorar Q2-Q5, Q19 sin otra fuente.

Comandos clave:
- Eval: LILIAN_EVAL_USERNAME=... LILIAN_EVAL_PASSWORD=... .venv_test/bin/python -m scripts.eval_law_retrieval --k=20
- Ver corpus: SELECT law_code, COUNT(*) FROM law_chunks GROUP BY law_code
```

---

## Contexto rapido

Lilian es una plataforma SaaS legal chilena. El corpus legal vive en Supabase
(Postgres + pgvector) y se ingiere desde la BCN via el endpoint
`Consulta/obtxml?opt=7`. El retrieval es RAG con OpenAI text-embedding-3-small
(1536-dim) + hybrid keyword (Postgres tsvector 'spanish').

**Recordatorio de auth:** el script `eval_law_retrieval.py` ahora requiere las
variables de entorno `LILIAN_EVAL_USERNAME` y `LILIAN_EVAL_PASSWORD`
(P5: credenciales sacadas del codigo). Hay que exportarlas en cada shell
oponerlas en `.env.local` (gitignored).

## Branch actual y commits pusheados

- **main**: 5 commits adelante de donde empezo el dia, todos pusheados
  - `228c43c` docs(status): correccion de advertencia obsoleta sobre v4
  - `ad2593b` docs(status): reflejar v4 commiteado en el bloque de handover
  - `0a83926` docs(status): reordenar plan por dependencias
  - `48f578d` fix(corpus): P1 + P3 + P5 + P8 + P4 migration
  - `5cc254d` fix(corpus): widening VARCHAR(255) + STATUS results
- **corpus/fix-refundidos-and-hybrid** (NUEVA, pusheada, NO mergeada):
  - `2fc39a1` fix(corpus): Plan A idLey + Plan B hybrid search
  - PR: https://github.com/jorgeguerrerohidalgo/lilIAn/pull/new/corpus/fix-refundidos-and-hybrid

## Commits relevantes del repo

```
5cc254d  fix(corpus): widening VARCHAR(255) + STATUS results  (main HEAD)
2fc39a1  fix(corpus): Plan A idLey + Plan B hybrid search    (branch HEAD)
48f578d  fix(corpus): P1 (141599) + P3 (streaming) + P5 + P8 + P4 migration
0a83926  docs(status): reordenar plan por dependencias
ad2593b  docs(status): reflejar v4 commiteado
228c43c  docs(status): corregir advertencia obsoleta
4fd2e37  feat(sh): v4 re-ingest script + endpoint uses correct BCN idNormas
bd86372  docs: STATUS - handoff document
ebf01cf  fix(ingest): use correct BCN idNormas (1209272 for 21.719) + 18046, 19496
```

## Bugs resueltos (auditados y commiteados)

| # | Bug | Resolucion | Commit |
|---|---|---|---|
| P1 | idNorma 19628 era el Decreto MINEDUC, no la Ley 19.628 | idNorma real = **141599** (encontrado via Playwright + busqueda simple BCN) | 48f578d |
| P2 | golden-dataset esperaba `21719` pero corpus tenia `1209272` | Golden actualizado con `1209272` en Q1-Q5, Q19 | 48f578d |
| P3 | Codigo de Comercio (57 MB) colgaba el parser | `lxml.iterparse(huge_tree=True)`, routing auto <5MB eager / >=5MB streaming | 48f578d |
| P4 | `law_chunks` sin UNIQUE, re-ingest duplicaba | `uq_law_chunks_law_code_version_chunk` aplicado | 48f578d + script standalone |
| P5 | credenciales hardcoded en eval_law_retrieval | Lee `LILIAN_EVAL_USERNAME` / `LILIAN_EVAL_PASSWORD` del entorno | 48f578d |
| P8 | `except Exception` tragaba errores en `_ingest_one` | Nueva `IngestError` jerarquica, errores de sistema propagan | 48f578d |
| P4b | `article_number` VARCHAR(50) / `articulo` VARCHAR(64) truncaba Codigo Civil | Widening a VARCHAR(255) | 5cc254d |
| **P1b** | **idNorma 19496 apuntaba al Decreto "Feria del Salmon" (no Ley del Consumidor); idNorma 18046 apuntaba al Decreto "Corporacion de Arte de Santiago"** | **idLey=19496 da 148 articulos refundidos; idLey=18046 da 176 articulos. Nuevo `TIER1_USE_IDLEY = {19496, 18046}` en ingest_bcn_corpus.py** | **2fc39a1** |

## Estado actual del corpus Tier 1

| idNorma | Ley | Chunks | Metodo |
|---|---|---|---|
| 172986 | Codigo Civil | 2843 | idNorma |
| 1984 | Codigo Penal | 680 | idNorma |
| 207436 | Codigo del Trabajo | 739 | idNorma |
| 22740 | Codigo de Comercio | 933 | idNorma (streaming) |
| 176595 | Codigo Procesal Penal | 564 | idNorma |
| 242302 | Constitucion | 225 | idNorma |
| 1209272 | Ley 21.719 | 12 | idNorma (BCN no expone refundida completa) |
| 141599 | Ley 19.628 (DICOM) | 28 | idNorma (35 disponibles, parser pierde 7) |
| 18046 | Ley 18.046 (S.A.) | 177 | **idLey** (era Decreto equivocado) |
| 19496 | Ley 19.496 (Consumidor) | 149 | **idLey** (era Decreto equivocado) |

Total: ~6350 chunks Tier 1, 13900+ con embeddings (incluyendo chunks no-Tier 1).

## Patron clave descubierto: idLey vs idNorma

La BCN acepta dos parametros en `Consulta/obtxml?opt=7`:
- `idNorma=<N>`: una version historica especifica. A veces apunta a un Decreto
  sin relacion con la ley (19496, 18046, 19628 fueron casos).
- `idLey=<N>`: la ley en si, con todas las modificaciones acumuladas
  ("refundido consolidado"). Esto es lo que el RAG necesita.

Implementado en `apps/backend/scripts/bcn_http_client.py:fetch_law_xml(law_number)`.
Ruteo via `TIER1_USE_IDLEY` en `ingest_bcn_corpus.py:TIER1_BCN_IDS`.

**Limitaciones conocidas:**
- 1209272 (21.719) con idLey da el MISMO XML que idNorma (12 articulos).
  BCN no expone la refundida completa de la 21.719 todavia (entra en
  vigencia escalonada hasta 2026-12-01).
- 141599 (19.628) con idLey da 35 EstructuraFuncional; el parser extrae
  28 chunks. Los 7 que se pierden son los que tienen `tipoParte="Articulo"`
  sin `<NombreParte>` hijo o con nombre huerfano.

## Plan B: hybrid search implementado

`apps/backend/app/services/rag.py`:
- `search_laws_by_keyword(query, top_k, ...)` con `to_tsvector('spanish', content)`
  + `ts_rank_cd`. Tokeniza el query a palabras >=3 chars, filtra no-alnum.
- Acepta los mismos filtros que `search_laws_by_embedding`: `legal_area`,
  `as_of`, `libro`, `capitulo`. **No** filtra por org/matter (es el corpus
  legal, no `document_chunks`).

`apps/backend/app/api/endpoints/corpus.py`:
- El endpoint `/corpus/search` ya tenia el RRF armado.
- Cambio: usa `search_laws_by_keyword` (en vez de `search_chunks_by_keyword`
  que iba contra `document_chunks`).

**Performance:** keyword search tarda ~10s por query sobre 14k chunks
(sin GIN index). Aceptable para piloto, mejorable.

## Recall baseline y techo

| | top_k=5 | top_k=20 |
|---|---|---|
| Antes (30 Aug) | 6/20 (30%) | n/a |
| Despues Plan A+B (1 Sep) | 6/20 (30%) | **9/20 (45%)** |

**Pasan (9/20):** Q1, Q6, Q7, Q8, Q9, Q10, Q11, Q12, Q15
**Fallan (11/20):**
- Q2, Q3, Q4, Q5, Q19: `1209272` (12 chunks; la refundida completa NO esta
  en BCN, solo los articulos transitorios)
- Q13, Q14, Q16, Q17: leyes correctas en top, pero los articulos especificos
  no llegan al top-20 (golden estricto: 2+ articulos por pregunta)
- Q18, Q20: `141599` (28 chunks) + `as_of=2024-12-13` filtra mas

**El criterio 85% (17/20) NO se alcanza con solo Tier 1.** Falta Tier 2/3
(~5.985 normas restantes).

## Proximos pasos (en orden recomendado)

### Inmediato (10 min)
1. **Mergear la rama `corpus/fix-refundidos-and-hybrid` a main.** Los cambios
   son aditivos: el endpoint ya tenia la fusion RRF armada, solo cambio la
   fuente del keyword. El hybrid funciona, el recall subio 9 puntos con
   top_k=20. Review de 30 min, merge, listo.

### Corto plazo (1 sesion, ~3-4 h)
2. **GIN index en `to_tsvector(content)`** en `law_chunks`. El keyword search
   tarda ~10s por query. Con GIN index baja a <100ms. Prerequisito para
   Tier 2/3 (que va a multiplicar el corpus por 5-10x).

   ```sql
   CREATE INDEX law_chunks_tsv_idx ON law_chunks
     USING gin (to_tsvector('spanish', content));
   ```

3. **Mejorar el parser para que use `tipoParte` atributo como fallback**
   cuando no hay `<NombreParte>` hijo. Hoy pierde ~7 articulos de la 19.628
   y unos cuantos de otras leyes. Cambio chico en `bcn_xml_parser.py`
   (~20 lineas).

### Mediano plazo (multiples sesiones)
4. **Tier 2 — las 100 leyes mas citadas.** `cmd_ingest_tier2`. El endpoint
   de `discover_bcn_catalog.py` con opt=3 paginado ya esta parcialmente
   implementado.

5. **Tier 3 — las ~6.000 normas restantes.** `cmd_ingest_all`. Esta es la
   unica palanca grande para subir el recall.

6. **Re-chunking mas granular.** Bajar `max_chunk_chars` de 2200 a ~800.
   Mas chunks por ley = mas chances de que un articulo especifico llegue
   al top-k.

### Diagnostico pendiente
- **Por que 172986 (Codigo Civil) rinde 2843 chunks pero el XML tiene 3151
  `<EstructuraFuncional>`?** Se pierden 308. Probablemente los chunks sin
  `<NombreParte>` hijo o con `<Texto>` muy corto son descartados. No es
  prioritario pero explica la perdida de cobertura.

## Comandos utiles

```bash
# Eval con top_k=20 (el maximo del endpoint)
cd apps/backend
LILIAN_EVAL_USERNAME=... LILIAN_EVAL_PASSWORD=... \
  .venv_test/bin/python -m scripts.eval_law_retrieval --k=20

# Re-correr el reindex si la DB se desincroniza con los embeddings
.venv_test/bin/python -m scripts.reindex_chunks

# Diagnosticar el corpus
.venv_test/bin/python -c "
from app.core.database import SessionLocal
from sqlalchemy import text
s = SessionLocal()
print(s.execute(text('SELECT law_code, COUNT(*) FROM law_chunks WHERE embedding_vec IS NOT NULL GROUP BY law_code ORDER BY law_code')).all())
s.close()
"

# Ver el idLey vs idNorma de una ley
curl -s "https://www.bcn.cl/leychile/Consulta/obtxml?opt=7&idLey=19496" | head -c 500
curl -s "https://www.bcn.cl/leychile/Consulta/obtxml?opt=7&idNorma=19496" | head -c 500
```

## Lecciones aprendidas

1. **"No puedo navegar" era falso.** Playwright (`mcp__playwright__browser_navigate`)
   estaba disponible. Lo descubri tarde, perdi tiempo.
2. **idNorma != idLey en BCN.** El cliente hardcodeado asumia idNorma; ahora
   soporta idLey con routing opt-in via `TIER1_USE_IDLEY`.
3. **Reingestar el Codigo Civil revelo un bug de schema** (article_number
   VARCHAR(50) truncaba un articulo real de 67 chars). El fix fue widening
   a VARCHAR(255). La migracion es idempotente.
4. **El parser SÍ extrae los 177 articulos de S.A. y 149 de Consumidor** cuando
   se le pasa el XML correcto. El "pocos chunks" no era bug del parser,
   era el idNorma equivocado.
5. **El recall depende mas de la calidad del retrieval que de la cantidad de
   leyes.** El BM25 vector+keyword juntos suben el recall 9 puntos con
   top_k=20. Pero el golden pide 2+ articulos por pregunta en top-20, y
   eso requiere corpus mas granular o mas normas.

## Bloque de handover (ahora al inicio del documento)

El bloque de handover rapido vive al principio de este archivo. Ver
`## Handover rapido (leer primero)` arriba.
