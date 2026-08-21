# S5.3 — Pendiente: corpus real de precedentes SCJ

## Por qué este stub existe

S5.3 sólo carga **ejemplos sintéticos** (``scripts/seed_synth_precedents.py``).
Los roll numbers empiezan en ``SYNTH-`` y cada fila está marcada con
``type="sintetico"`` y el disclaimer ``SYNTHETIC`` en ``disposition``.
Esto se hizo así para evitar fabricar citas que parecieran reales del
Poder Judicial de Chile.

## Lo que falta para S5.3 "real"

1. **Convenio de datos** con la Biblioteca del Congreso Nacional (BCN)
   o con el portal del Poder Judicial (``pjud.cl``). Hasta ahora no
   tenemos contrato ni scraping autorizado.
2. **Pipeline de ingestión**: una vez conseguido el corpus, un script
   nuevo en ``scripts/ingest_real_precedents.py`` que:
   - lea cada sentencia del formato oficial (PDF, XML o JSON),
   - extraiga roles, magistrado, año, materia, considerandos y
     dispositivo,
   - inserte en ``precedents`` con ``type="sentencia"`` y el
     ``full_citation`` extraído del header oficial,
   - indexe embeddings con la cita literal para evitar duplicados.
3. **Backfill masivo**: re-seed de las 100-500 sentencias más citadas
   por materia para que el RAG del agente de ``/precedents`` tenga
   contexto útil.
4. **Validación humana**: panel de revisión donde un abogado senior
   aprueba cada lote antes de hacerlo público.

## Cómo afecta al producto

- El RAG de precedentes funciona hoy: las sentencias sintéticas dan
  contexto plausible para demos y pruebas internas.
- Toda cita que un caso de ``/precedents`` entregue en producción
  mostrará el disclaimer ``SYNTHETIC`` en la disposition, por lo que
  el abogado que la vea sabrá que no es una sentencia real.
- Apenas se carguen las primeras 100 sentencias reales, el catálogo
  sintético puede purgarse con un DELETE WHERE type='sintetico'.

## Estimación

- 1 semana: convenio + ETL completo.
- 1 día: backfill cuando el corpus esté disponible.
- 1 día: QA + rollout.

## Tasks

- [ ] Contactar a BCN para licencias de datos.
- [ ] Evaluar portal ``pjud.cl`` (¿ofrece API?).
- [ ] Diseñar pipeline de ingestión.
- [ ] Reemplazar ``seed_synth_precedents.py`` por
      ``seed_real_precedents.py``.

