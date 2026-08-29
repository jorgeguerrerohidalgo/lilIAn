# Lilian 3.0 — Plan de Producto y Tecnología

> **Estado del documento**: Borrador inicial v0.1 — 2026-08-29
> **Audiencia**: Equipo interno + técnico (asume que el lector conoce el stack).
> **Granularidad**: Fases macro (Q1 / Q2 / Q3-Q4 2026, Q1 2027), no sprint-by-sprint.
> **Scope**: Producto + tech. Sin pricing ni go-to-market (ver `docs/STATE_OF_PRODUCT_2026-08-21.md` y `ROADMAP_HARVEY_FEATURES.md` para contexto adyacente).
>
> Este documento **sustituye** el roadmap táctico de `ROADMAP_HARVEY_FEATURES.md`. Ese archivo se mantiene como bitácora histórica de qué se implementó y cuándo; este es el plan hacia adelante.

---

## 1. Resumen ejecutivo

Lilian 2.x es un **MVP funcional** con análisis de contratos, detección de riesgos con semáforo, búsqueda de precedentes con RAG, chat legal con streaming y multi-tenancy estricto con RBAC de 7 roles. Lo que está construido es **más de lo que tiene la mayoría del mercado chileno**, pero está pensado como demo tecnológica, no como plataforma lista para retención enterprise.

Lilian 3.0 es el salto de **"demo impressionnante"** a **"producto que un bufete paga mensualmente y renueva"**. Implica cerrar los gaps funcionales que un cliente real descubre al usarlo 30 días, fortalecer la infraestructura para crecer 10× sin reescritura, y darle al producto una identidad visual y narrativa que no se confunda con "otra herramienta de IA".

**El cambio de fase** se resume en cuatro frases:

1. **De PDFs limpios a PDFs del mundo real** — OCR de scans, comparación de versiones, batch processing.
2. **De RAG genérico a RAG curado para Chile** — corpus legal chileno cargado, mantenido y citado con trazabilidad.
3. **De chat a agentes** — workflows multi-step que ejecutan tareas legales concretas (revisión laboral, due diligence).
4. **De SaaS aislado a plataforma integrada** — conexiones con Poder Judicial, SII, firma electrónica.

**El diferenciador no es ser Harvey en español**. Es ser **mejor que Harvey en lo que un abogado chileno realmente necesita**, todos los días.

---

## 2. Estado actual (baseline)

Resumen del inventario de producto. Detalle completo en `docs/STATE_OF_PRODUCT_2026-08-21.md`.

### 2.1 Lo que funciona (no romper)

- **Análisis de contratos PDF/DOCX/TXT** con extracción de partes (RUT incluido), montos, fechas, cláusulas y scoring de riesgo por semáforo.
- **Búsqueda de precedentes** con pgvector + HNSW, búsqueda híbrida embeddings + keyword, fusión RRF.
- **Chat legal streaming** con RAG sobre documentos + leyes + precedentes, cap 4000 chars.
- **Generación de documentos** desde templates `language: es-CL`.
- **Multi-tenant estricto** con RBAC de 7 roles (`PLATFORM_ADMIN`, `OWNER`, `ADMIN`, `LAWYER`, `COMPANY_USER`, `CLIENT`, `VIEWER`).
- **Sharing externo** de informes con tokens firmados (`itsdangerous`) y TTL configurable.
- **Auth BFF** con cookie `lilian_auth_token` HttpOnly + SameSite=Lax, rate-limit en `/login` y `/register` (slowapi + Redis).
- **Multi-provider LLM** (anthropic / openai / minimax) con prompt caching.
- **Worker asíncrono** (RQ + Redis) para procesamiento de documentos.

### 2.2 Stack actual (con coste marcado)

> **Principio Lilian 3.0**: preferir herramientas open-source / self-hosted siempre que la calidad lo permita. Solo se justifica pagar por algo cuando no existe alternativa gratuita viable o cuando el coste operativo (tiempo humano, mantenimiento) supera el coste financiero. La columna **€** indica si la pieza tiene coste directo en uso: `0` = gratis / free tier suficiente, `€` = de pago, `€€` = caro a escala.

| Capa | Tecnología | € | Notas |
|---|---|---|---|
| Frontend | Next.js 14 App Router, React 18, TypeScript, Tailwind | 0 | Open source. Vercel free tier cubre MVP. |
| Backend | FastAPI 0.111, SQLAlchemy 2 async, Alembic | 0 | Open source. Railway free tier hasta validar. |
| DB | PostgreSQL 15 + pgvector | 0 | Open source. Supabase free tier hasta 500MB. |
| Cache / Queue | Redis (Upstash) | 0 | Upstash free tier: 10k comandos/día. |
| Storage | Supabase Storage / local FS | 0 | Free tier 1GB. MinIO self-hosted si se necesita más. |
| LLM | OpenAI gpt-4o-mini (default), Anthropic, Minimax | €€ | **Único coste variable significativo**. Mitigación: caching agresivo, modelo chico para tareas simples, prompt caching Anthropic. |
| Embeddings | OpenAI text-embedding-3-small 1536 dims | € | Coste bajo ($0.02/1M tokens). Alternativa gratuita documentada en §5.3.1. |
| OCR | PyMuPDF + python-docx (texto embebido) | 0 | Solo extrae texto embebido. **No cubre PDFs escaneados** — gap crítico a cerrar en Fase 1 con Tesseract. |
| Pagos | Stripe | € | Solo si se monetiza. Sin coste en MVP. |
| Email | SMTP self-hosted (MailHog en dev) | 0 | Para producción, usar SES o Postmark free tier. |
| Observabilidad | Sentry (free tier) + Prometheus + Grafana + Loki | 0 | Sentry free tier cubre 5k eventos/mes. Lo demás es self-hosted. |
| Auth | JWT (python-jose), bcrypt | 0 | Open source. |
| Vector store | pgvector (HNSW) | 0 | Ya integrado en Postgres. Suficiente hasta ~10M chunks. |
| Tests E2E | Playwright + axe-core | 0 | Open source. |
| Load testing | Locust o k6 (OSS) | 0 | Open source. |

**Regla de oro para nuevas dependencias**: si una pieza va a producción y tiene alternativa open-source con calidad comparable, va la open-source. Si solo hay opciones de pago (LLM, Stripe), se usa la más barata y se documenta el plan de salida (self-host del LLM cuando existan modelos OSS de calidad suficiente).

### 2.3 Salud del código

- Tests backend: **70%** (`fail_under = 70` en `pyproject.toml`). Necesario llegar a 80% como compromiso de calidad mínimo enterprise.
- 5 pages responsive implementadas en commits recientes (mobile-first para matters, documents, precedents, auth, dashboard). El dashboard shell tiene drawer móvil + sidebar fijo desktop.
- Deuda visible: `bg-primary-600` y variantes numéricas requerían clases que no existían en Tailwind config (resuelto en commit `9796ee2`).
- Falta: tests E2E serios (Playwright solo en `tests/e2e/` con cobertura mínima).

---

## 3. Visión del producto 3.0

### 3.1 La promesa

> **"Lilian 3.0 es la plataforma con la que un abogado chileno abre su computador a las 9 AM y cierra su día a las 6 PM sin haber tocado un PDF sin resumen, sin haber redactado un contrato sin asistencia, y sin haber tomado una decisión legal sin precedentes citados."**

No es un chatbot. Es el sistema operativo del trabajo legal en Chile.

### 3.2 Los tres pilares

1. **Cobertura real del trabajo legal chileno**
   Análisis documental, redacción, investigación, predicción y ejecución, todo apuntando a legislación y jurisprudencia chilena con citas verificables.

2. **Agentes, no chat**
   Un "agente de revisión laboral" no es un chat con un prompt. Es un workflow que: sube el contrato → identifica el tipo → extrae cláusulas críticas contra el Código del Trabajo → compara con la versión anterior → emite semáforo → propone redlines → espera aprobación humana → guarda el informe. Cada paso es verificable.

3. **Trazabilidad de extremo a extremo**
   Cada afirmación de la IA está enlazada a una fuente: el chunk del documento original, el artículo del Código Civil, la sentencia de la Corte Suprema. Sin citaciones, no hay producto.

### 3.3 Principios de diseño

| # | Principio | Implicación práctica |
|---|---|---|
| 1 | **Mobile-first real** | Toda feature se diseña primero para 375px. El usuario chileno promedio revisa el celular antes de llegar al escritorio. |
| 2 | **Latencia perceptible < 500ms** | Primer byte del chat en menos de medio segundo. Si la IA piensa, se muestra skeleton + streaming. |
| 3 | **Reversibilidad** | Toda acción automatizada es revisable. "IA propuso borrar X" debe aparecer en una cola de aprobación, no ejecutarse silenciosamente. |
| 4 | **Cero magia sin fuente** | Cualquier salida numérica o jurídica muestra su origen. Tooltips sobre cifras, badges de citación sobre párrafos. |
| 5 | **Onboarding en 5 minutos** | Del signup al primer caso creado con análisis, en menos de 5 minutos. Si toma más, perdimos al usuario. |
| 6 | **Accesibilidad AA** | WCAG 2.1 AA mínimo. La mitad de los abogados senior usan lectores de pantalla para textos largos. |

### 3.4 Métricas de éxito (north star)

| Métrica | Baseline 2.x | Target 3.0 (12 meses) |
|---|---|---|
| MAU activos (firmas con ≥1 caso/semana) | desconocido | ≥ 40 |
| Casos analizados/mes/organización | ~5 | ≥ 30 |
| Tiempo promedio de análisis (PDF → semáforo) | ~90s | < 30s |
| Retención M3 (organizaciones que pagan 3 meses) | n/a (pre-pago) | ≥ 70% |
| NPS | n/a | ≥ 40 |
| Cobertura de tests | 70% | ≥ 80% |
| % usuarios con consentimiento Ley 21.719 registrado | 0% | 100% post-deploy |
| Compliance score promedio de tenants (PLATFORM_ADMIN) | n/a | ≥ 75 (grado C o superior) |
| Tiempo medio respuesta RightsRequest | n/a | < 30 días corridos (SLA legal) |

### 3.5 El cuarto pilar: cumplimiento como producto

Lilian 3.0 incorpora un **cuarto pilar** que no estaba en los tres originales: el cumplimiento normativo no es solo una obligación defensiva, es una **ventaja competitiva**. La Ley 21.719 entra en vigencia general el 1 de diciembre de 2026 y redefine las reglas del juego: cualquier SaaS que trate datos personales de ciudadanos chilenos sin consentimiento explícito verificable, sin derechos ARCO operativos, sin registro de actividades de tratamiento y sin notificación de brechas, está expuesta a multas de hasta 20.000 UTM y prohibición de operar.

Tres niveles:

1. **Lilian como responsable del tratamiento (defensiva)**: hacer que la propia plataforma cumpla antes del 1-dic-2026 — consentimiento al registrarse, derechos ARCO + portabilidad + bloqueo operativos, ROPA documentado por tenant, notificación de brechas. Es lo mínimo legal.

2. **Ley 21.719 como fuente legal en el corpus (inteligencia)**: cargar la ley al Tier 1 del RAG para que el chat, los agentes y los análisis la citen correctamente. Cubre el caso de uso "abogado pregunta sobre consentimiento para datos sensibles en un contrato laboral" — Lilian responde con el artículo correcto.

3. **Ley 21.719 como producto para bufetes (ofensiva)**: ayudar a los bufetes a cumplir — auditoría de cláusulas en contratos, generador de plantillas de privacidad, score de cumplimiento del bufete (no de Lilian), recordatorios de plazos legales. Convierte un requisito legal en una feature que justifica el plan.

**El diferenciador específico**: mientras Harvey es global y genérico, Lilian puede ser el primer producto que en serio audita, redacta y monitorea el cumplimiento de la Ley 21.719 para bufetes chilenos. Equivale a "Salesforce + GDPR-ready" en 2018: el cumplimiento se volvió un argumento de venta.

---

## 4. Características nuevas

### 4.1 Análisis de documentos

#### 4.1.1 OCR para PDFs escaneados (gap crítico)

**Por qué importa**: El abogado chileno promedio sube contratos firmados en scanner, no PDF nativos. Hoy PyMuPDF solo extrae texto embebido — un PDF escaneado entra al pipeline y `text` queda vacío.

**Diseño (todo open-source)**:
- Worker detecta PDFs sin texto extraíble (`len(extracted_text) < threshold`).
- Encola tarea OCR. **Pipeline multi-engine en cascada**, todos open-source:
  1. **Tesseract 5.x** (`pytesseract`): primera opción. Es el OCR más maduro, gratis, soporta español (`spa` traineddata). Bueno para scans limpios a 300 DPI.
  2. **PaddleOCR** (`paddleocr` Python): segunda opción si Tesseract falla por baja confianza. Modelo `es` para español. Mejor con handwriting que Tesseract. Pesado (~1GB modelos), correr en worker dedicado.
  3. **Surya OCR** (`surya-ocr`): tercera opción. Open-source, basado en transformers. Soporta 90+ idiomas incluyendo español con buena calidad. Más moderno, alternativa real a Textract en calidad para docs estructurados.
- Output OCR se persiste como `Document.text` con flag `text_source: "tesseract" | "paddleocr" | "surya" | "embedded"` y `confidence_score`.
- Pre-procesamiento con OpenCV (`opencv-python`): deskew, denoise, binarización adaptativa. Mejora la calidad de Tesseract significativamente en scans antiguos.
- **Coste objetivo: $0**. Tesseract y PaddleOCR corren en el worker. Surya corre en GPU si está disponible (en Railway es opcional); CPU es viable para documentos pequeños.

**Trade-off documentado**: Tesseract/PaddleOCR/Surya tienen menor accuracy que AWS Textract (~85-90% vs ~97% en handwriting complejo). Para el 95% de contratos escaneados a 300+ DPI en español con tipografía estándar, Tesseract es suficiente. Para el 5% restante (handwriting, scans muy degradados), se ofrece al usuario re-subir el documento o contactar a soporte.

**Acceptance criteria**:
- PDF escaneado de 10 páginas (300 DPI, español, scan limpio) produce análisis completo con cláusulas extraídas y scoring de riesgo.
- Latencia OCR: < 60s/página (Tesseract en CPU), < 30s/página (Surya en GPU si disponible).
- Tasa de confianza reportada por engine; si < 70%, retry con engine siguiente en cascada.
- UI muestra "Documento escaneado, procesando con OCR..." con stepper de progreso que indica engine activo.
- Logging por documento: qué engine se usó, tiempo, páginas fallidas si las hubo.

#### 4.1.2 Comparación de versiones / redlining (gap existente)

**Por qué importa**: `apps/backend/app/services/clause_comparator.py` existe pero el endpoint no está expuesto en `app/api/endpoints/`. Es una de las features más pedidas — abogados suben v1 y v3 y quieren ver qué cambió cláusula por cláusula.

**Diseño**:
- Endpoint `POST /api/v1/documents/compare` recibe `{document_a_id, document_b_id}`.
- Service alinea cláusulas por similitud semántica (no solo diff de texto).
- Devuelve `clause_pairs[]` con `status: "unchanged" | "modified" | "added" | "removed"` + `similarity_score` + diff visual.
- UI en `/dashboard/matters/[id]/compare?a=...&b=...` con side-by-side y highlights.
- "Aceptar cambio" / "Rechazar cambio" alimentan un historial de decisiones.

**Acceptance criteria**:
- Comparar dos versiones del mismo contrato (v1, v3) identifica ≥ 90% de las cláusulas modificadas.
- Diff visual muestra rojo/quitado, verde/agregado, amarillo/modificado.
- Cada par cita el número de cláusula original.

#### 4.1.3 Batch upload (carpeta completa)

**Por qué importa**: Los bufetes suben 50-200 documentos por due diligence. Subir uno por uno mata el funnel.

**Diseño**:
- Drag & drop multi-archivo en `/dashboard/matters/[id]/documents`.
- Worker procesa en paralelo (pool configurable por plan).
- Stepper de progreso: `12/47 archivos procesados, 3 con error`.
- Errores no bloquean el resto — el usuario puede reintentar los fallidos.

### 4.2 Base legal chilena — corpus completo desde BCN Open Data

> **Documentación operativa**: `docs/corpus/legal-chile.md`. Resumen aquí, detalle ahí.

#### 4.2.1 Arquitectura del corpus (Fase 1 completada)

**Fuente primaria**: [BCN Open Data](https://datos.bcn.cl) — dataset completo de normas chilenas en formato abierto, con endpoint SPARQL (`bcnnorms:` ontology) y exportación Akoma Ntoso. Actualización diaria.

**Limitación práctica**: la BCN sirve una SPA Angular con reCAPTCHA en todos los endpoints HTML; solo el SPARQL funciona con `httpx` simple. Para Tier 1 (~30 normas) la estrategia es **descarga manual desde el navegador** + parser propio. Para Tier 3 (~6.000 normas) se automatiza con Playwright (Fase 3).

**Modelo de datos** (ver `docs/corpus/legal-chile.md` §2.1 para detalle):

- `norm_catalog` (1 fila por norma): `bcn_id`, `tipo` (codigo/ley/decreto/dfl/dl/constitucion/tratado), `numero`, `titulo`, `fecha_publicacion`, `organismo_emisor`, `estado`, `url_bcn`, `legal_area`, `current_version_id`, `repealed_by_norm_id`.
- `law_chunk_versions` (N filas por norma): `version_label`, `valid_from`, `valid_until`, `is_current`, `source_url`, `raw_source_hash`, `chunk_count`. Permite versionado temporal: queries con `as_of=X` devuelven chunks vigentes en X.
- `norm_relations` (grafo): `from_norm_id`, `to_norm_id`, `relation_type` (modifica/deroga/rectifica/refunde/prorroga/reglamenta), `article_ref`.
- `law_chunks` extendido con `jerarquia_path`, `parent_chunk_id`, `libro/titulo/capitulo/articulo/inciso/numeral/letra`, `norm_id`, `version_id`. Indexado por cada nivel jerárquico.

**Pipeline**:

```
BCN SPARQL → BCNClient → HTMLParser (jerárquico) → DBWriter (idempotente)
                                     ↓
                    norm_catalog + law_chunk_versions + law_chunks
                                     ↓
                    hybrid_search() con filtros (as_of, libro, capitulo)
                                     ↓
                    /api/v1/corpus/search → /precedents en el frontend
```

#### 4.2.2 Tier 1 — cobertura objetivo

5 Códigos base + Ley 21.719 + Ley 19.628 derogada + ~25 leyes frecuentes:

- Código Civil, Código de Comercio, Código del Trabajo, Código Penal, Ley 18.046 (Sociedades Anónimas)
- Ley 21.719 (vigente) + Ley 19.628 (derogada, conservada con `valid_until=2026-12-01`)
- ~10 leyes laborales (CT, SSL, etc.), ~5 tributarias, ~10 consumidor/propiedad
- **Total Tier 1**: ~6.000 chunks, ingestados en 30 min por operador

Tier 2 (Fase 2, 1 semana): ~100 leyes más citadas + jurisprudencia reciente del Poder Judicial + grafo completo de relaciones.

Tier 3 (Fase 3, 1 mes): ~6.000 normas restantes + automatización con Playwright + embeddings locales (sentence-transformers).

#### 4.2.3 Versionado temporal — la feature más valiosa

```sql
-- Query con as_of=X
SELECT chunk_id, content FROM law_chunks
WHERE version_id IN (
  SELECT id FROM law_chunk_versions v
  WHERE v.valid_from <= :as_of
    AND (v.valid_until IS NULL OR v.valid_until > :as_of)
)
```

Esto permite responder *"¿qué establecía este artículo en 2023?"* correctamente cuando hay una versión histórica y otra vigente. El query se activa pasando `as_of=YYYY-MM-DD` al endpoint `/api/v1/corpus/search`.

**Golden dataset** (`docs/corpus/golden-dataset-v2.json`): 20 preguntas, 3 de ellas con `as_of` específico para validar el versionado. CI gate: `recall@5 ≥ 0.85`.

#### 4.2.4 Embeddings y chunking optimizado para texto legal

Mantiene Plan A (OpenAI text-embedding-3-small) por costo (~€0.50 USD para Tier 3 completo). Plan B con `sentence-transformers` (BGE-m3) local está documentado para Fase 3 cuando el costo mensual supere $200.

**Chunking jerárquico** (ver `apps/backend/scripts/html_parser.py`):
- Detecta LIBRO / TÍTULO / CAPÍTULO / SECCIÓN / PÁRRAFO en Códigos.
- Genera chunks respetando la jerarquía con `jerarquia_path` (breadcrumb legible) y `parent_chunk_id` (FK al chunk padre).
- Para Leyes (sin estructura) usa article-only fallback.
- Artículos > 2.200 chars se dividen en incisos o windows de palabras.

**Curación > cantidad**: 1.000 sentencias bien curadas con metadatos útiles vale más que 100.000 sin estructura.

#### 4.2.2 Embeddings y chunking optimizados para texto legal

**Problema**: El chunking genérico de documentos (800 tokens, overlap 100) no respeta la estructura de artículos legales. Un chunk puede partir un artículo a la mitad y romper la citación.

**Diseño**:
- Chunking jerárquico legal-aware: respeta `Artículo N`, `Inciso N`, `Orden`, etc.
- Metadata enrichment automático: agrega `article_number`, `inciso`, `paragraph` a cada chunk.
- Embeddings: mantener OpenAI 1536 dims (balance coste/calidad) o migrar a `text-embedding-3-large` 3072 (mejor retrieval, +10× coste storage). **Decisión recomendada**: mantener 1536 hasta Fase 3.

### 4.3 Predicción de resultados judiciales

**Por qué importa**: Harvey lo tiene y es su "wow feature" para clientes corporativos. Para el mercado chileno, un modelo que predice "probabilidad de éxito en demanda laboral por despido injustificado" sería un diferenciador enorme.

**Diseño** (Fase 2, alto esfuerzo):
- **Modelo**: clasificación binaria (éxito/no-éxito) + regresión (probabilidad 0-1).
- **Input**: tipo de materia, hechos clave, tribunal, año.
- **Output**: probabilidad + top 5 sentencias similares con su resultado histórico.
- **Training data**: las 1.000+ sentencias del corpus + features extraídas (partes, monto, tipo de acción, resultado).
- **Honestidad**: el modelo se entrena con datos públicos; se muestra disclaimer "basado en N sentencias similares, no es asesoría legal".

**Acceptance criteria**:
- Precisión ≥ 65% en test set (mejor que baseline aleatorio 50%).
- Explicabilidad: para cada predicción, top 5 features que más influyeron.
- Actualización trimestral con nuevas sentencias.

### 4.4 Agentic workflows

**Por qué importa**: Chat es la fase 1. Agentes son la fase 2. Un agente ejecuta un workflow completo de varios pasos; un chat responde una pregunta.

#### 4.4.1 Arquitectura del sistema de agentes

```
[User] → [Agent Runner] → [Planner LLM] → [Plan: steps[]]
                                       ↓
                            [Tool Registry] ← tools/skills por tenant
                                       ↓
                          [Executor] → tool call → result
                                       ↓
                            [Reflect] → ¿continuar o responder?
                                       ↓
                          [Final Response to User]
```

- **Plan**: LLM genera plan de pasos a partir del goal del usuario.
- **Tools**: abstracción de tools/skills (similar a OpenAI function calling o Anthropic tools). Cada tool tiene schema, descripción, ejemplos.
- **Reflection**: después de cada step, el agente verifica si el resultado es razonable antes de continuar.
- **Human-in-the-loop**: steps marcados como `requires_approval: true` pausan y muestran UI de aprobación al usuario.

**Implementación recomendada (todo open-source o ya disponible)**:
- **Tool registry**: schema estándar JSON Schema. Tools como funciones Python decoradas (`@tool("nombre", description="...")`).
- **Planner**: prompt template con few-shot examples, no requiere framework externo.
- **State machine**: librería `transitions` o implementación custom. No usar frameworks pesados (LangGraph es open-source pero overkill para el caso de uso).
- **Tool runtime**: Python asyncio, mismo event loop que el resto del backend. Cada tool es async-safe.
- **UI**: el stepper del agente muestra cada tool call y resultado en tiempo real. Streaming con `Server-Sent Events` (SSE), ya implementado en el chat.

#### 4.4.2 Agentes prioritarios para el mercado chileno

**Agente 1: Revisión laboral express** (Fase 1)
- Input: contrato individual de trabajo (PDF o DOCX).
- Pasos: extraer cláusulas obligatorias (jornada, remuneración, férias) → comparar con Código del Trabajo Art. 10 → detectar incumplimientos → generar informe semáforo.
- Output: informe con 5-15 issues clasificados como críticos / moderados / menores.
- Latencia objetivo: < 60s end-to-end.

**Agente 2: Due diligence M&A** (Fase 2)
- Input: carpeta con N documentos de una empresa target.
- Pasos: clasificar docs → extraer liabilities (deudas, litigios, contratos críticos) → cruzar con registros públicos (mock primero, integración real Fase 3) → emitir risk register priorizado.
- Output: matriz de riesgos con probabilidad/impacto + citations.

**Agente 3: Cumplimiento regulatorio semanal** (Fase 3)
- Input: lista de clientes del bufete.
- Pasos: leer Diario Oficial de la semana → identificar cambios regulators que afecten a los clientes → cruzar con cartera activa → notificar.
- Output: digest semanal personalizado por cliente.

### 4.5 Multi-jurisdicción

**Por qué importa**: Hoy todo está hardcoded a Chile. Si la empresa crece, querer expandirse a Perú o Colombia requeriría un refactor invasivo.

**Diseño** (Fase 3, experimental):
- Campo `country: "CL" | "PE" | "CO"` en `Organization` (default "CL").
- Tenant prompts se ensamblan con un prompt base + country-specific clauses.
- Templates de documentos: estructura `templates/{country}/{type}.md`.
- Base legal: misma estructura `law_chunks` con campo `country`.
- **MVP**: solo CL. **Fase 3**: agregar Perú (jurisdicción más similar y mercado TAM grande).

### 4.6 Integraciones con ecosistema chileno

#### 4.6.1 Poder Judicial (consulta de causas)
- **Fuente**: el portal público de PJUD Chile (pjud.cl). No hay API oficial; usamos scraping ético con rate limiting, respeto a robots.txt y cached responses con TTL.
- **Librería sugerida**: `httpx` + `selectolax` o `beautifulsoup4` (ambos open-source). Captcha cuando aparece: delegar al usuario (el agente pausa y pregunta).
- **Casos de uso**: "agente busca todas las causas activas donde mi cliente es demandado".
- **Coste**: $0. Solo el coste de cómputo del worker.

#### 4.6.2 SII (validación RUT, facturas)
- **Validación RUT**: usar la misma técnica que la comunidad usa (consulta al SII mediante endpoints públicos conocidos). Cache local por 24h.
- **Validación DTE/factura electrónica**: consumir el XML del DTE directamente desde el sitio del SII o del receptor. Parsing con `lxml` (open-source).
- **Privacidad**: dejar claro en UI que solo validamos, no almacenamos datos del SII. Logs no deben contener RUTs completos (enmascarar).
- **Coste**: $0.

#### 4.6.3 Firma electrónica
- **Prioridad 1 — FirmaGob** (estándar chileno del Estado, gratis para docs públicos): integrar primero. Costo para docs privados también es bajo.
- **Prioridad 2 — DocuSign** (estándar internacional): integrar si el cliente lo pide explícitamente. DocuSign cobra por envelope (~$0.50-2 USD por firma), por lo que NO es default.
- **Prioridad 3 — Otras opciones open-source**: evaluar **Documenso** (open-source, self-hosted) o **OpenSigner** como tercera alternativa gratuita. Investigar madurez en Fase 3 antes de comprometer.
- **Flujo**: generar contrato en Lilian → enviar a firma → webhook de completion → guardar contrato firmado en Storage.
- **Decisión recomendada**: FirmaGob como única integración en Fase 3, Documenso como alternativa si FirmaGob no satisface necesidades de bufetes privados.

### 4.8 Cumplimiento normativo como producto (Ley 21.719)

La Ley 21.719 redefine el estándar para cualquier SaaS que trate datos personales. Para Lilian, el cumplimiento no es solo una obligación defensiva: es una **feature que justifica el plan Pro y el plan corporativo**. Mientras el mercado chileno se prepara, Lilian puede ofrecer un paquete integrado de cumplimiento que ningún competidor global (Harvey, Spellbook, Lexis+AI) tiene localizado.

#### 4.8.1 Defensa: Lilian cumple la ley

- **Consentimiento explícito al registrar**: checkbox obligatorio de Términos + Política de Privacidad, con versionado por usuario (`terms_version`, `privacy_version`). Endpoint `POST /api/v1/auth/register` rechaza con 422 si faltan.
- **Consentimientos granulares**: `POST /api/v1/privacy/consent` para gestionar scopes individuales (analytics, marketing, cookies). Revocación inmediata.
- **Derechos ARCO + portabilidad + bloqueo**:
  - `GET /api/v1/privacy/rights/me/export` — devuelve ZIP con todos los datos del usuario en formato JSON estructurado por entidad (perfil, membresías, consentimientos, requests, manifest de datos). Sin coste externo.
  - `POST /api/v1/privacy/rights/me/request` — crea una `RightsRequest` con SLA de 30 días corridos (art. 27). Worker de fondo escanea requests cerca del deadline.
  - `GET /api/v1/privacy/rights/me` — historial de solicitudes del usuario.
- **ROPA documentado por tenant**: tabla `data_processing_activities` con `legal_basis`, `data_categories`, `retention_days`, `recipients`, `involves_sensitive_data`, `involves_automated_decisions`. Endpoints CRUD para que cada tenant documente qué hace con los datos de sus clientes.
- **Notificación de brechas**: `POST /api/v1/privacy/breach-notify` (PLATFORM_ADMIN). Persiste `BreachIncident` con timestamps de notificación a la Agencia y a titulares. Integración con el API de la Agencia es trabajo de Fase 3.
- **Texto legal público** en `/legal/privacy`, `/legal/terminos`, `/legal/cookies`. Política describe transferencias internacionales reales (OpenAI, Anthropic, Supabase, Stripe, etc.).
- **Cookie banner** con opt-in para analytics. Las estrictamente necesarias están siempre activas (auth, CSRF).
- **Settings → Privacidad** con todos los derechos ARCO operativos en UI, incluido el botón "Exportar mis datos" (ZIP descargable).

#### 4.8.2 Inteligencia: la ley como corpus

- **Ley 21.719 cargada en Tier 1** del corpus legal chileno (ver §4.2). Cada chunk lleva metadata `legal_area="data_protection"` para filtrado eficiente.
- **Ley 19.628 derogada** conservada con `valid_until=2026-12-01` para que el RAG pueda mostrar la evolución normativa en respuestas ("antes regía X, ahora Y").
- **Golden dataset** con 5 preguntas verificadas. CI gate: `recall@5 ≥ 0.9` para privacidad.
- **Citación visible** en el chat: badge "📋 Ley 21.719" cuando se cita un chunk de protección de datos. Pattern matching por `legal_area`.

#### 4.8.3 Ofensiva: la ley como producto

- **Agente "Auditoría de privacidad"** (`POST /api/v1/analysis/privacy-audit`): clasifica cláusulas en 8 categorías (consentimiento, tratamiento_datos, transferencia, encargado, sensibles, menores, transferencia_internacional, decisiones_automatizadas) y emite semáforo + issues. Prompt incluye la Ley 21.719 chunked como contexto. Es el equivalente compliance del análisis de riesgos actual, pero específico para privacidad.
- **Generador de plantillas**: 4 plantillas base en `apps/backend/app/templates/chile/privacy/`:
  - `politica_privacidad_empresa_v1.md`
  - `politica_privacidad_bufete_v1.md`
  - `contrato_encargado_tratamiento_v1.md` (el DPA obligatorio con proveedores, art. 21)
  - `consentimiento_tratamiento_datos_v1.md`
  - Endpoint `POST /api/v1/privacy/generate-template` con `template_type`, `industry`, `tenant_size` ajusta cada plantilla al contexto del bufete. Disclaimer visible: "Borrador inicial; consulte con un abogado antes de usar."
- **Compliance score widget** en `/dashboard/admin/organizations/[id]`: lee el ROPA del tenant y devuelve 0-100 + grado (A/B/C/D/F) + issues accionables. NO es un sustituto de auditoría legal — disclaimer visible. Drives upgrades de plan ("para grado A necesitas X, Y, Z").
- **Catálogo de plantillas** en `/dashboard/admin/templates` (PLATFORM_ADMIN) y `/dashboard/team/templates` (OWNER/ADMIN): wizard de generación con preview.

#### 4.8.4 Por qué esto es una ventaja competitiva real

| | Harvey | Spellbook | Lilian 3.0 |
|---|---|---|---|
| Compliance GDPR (UE) | ✅ | ✅ | ❌ (mercado no es UE) |
| Compliance Ley 21.719 (Chile) | ❌ | ❌ | ✅ diseño específico |
| Auditor de cláusulas en contratos | parcial | ❌ | ✅ 8 categorías |
| Generador de plantillas localizado | ❌ | ❌ | ✅ 4 plantillas iniciales |
| Score de cumplimiento del bufete | ❌ | ❌ | ✅ widget + plan |
| Workflow ARCO end-to-end | parcial | ❌ | ✅ UI + endpoint |

**Mensaje de marketing**: "Lilian es el primer producto que te ayuda a cumplir la Ley 21.719 mientras trabajas en tus casos."

### 4.7 UX y diseño visual

**Por qué importa**: La percepción de "producto terminado" es 70% UX, 30% features. Lilian 2.x tiene una paleta sólida (Trust & Authority) pero la implementación es funcional, no memorable.

#### 4.7.1 Principios visuales (ver `rules/ecc/web/design-quality.md`)

- **Evitar template look**: nada de "card grid uniforme + sidebar gris + hero genérico".
- **Bento composition**: home del dashboard con secciones de diferentes tamaños, no todas iguales.
- **Motion con propósito**: streaming del chat debe sentirse como agua fluyendo; el semáforo de riesgo debe animar la transición de color.
- **Jerarquía tipográfica**: Barlow ya está elegida, pero hay que usar la escala con más intención (display vs body vs caption).

#### 4.7.2 Componentes nuevos prioritarios

| Componente | Propósito | Inspiración |
|---|---|---|
| `RiskBadge` animado | Semáforo que transiciona entre estados con motion | Linear, Stripe Elements |
| `CitationPill` | Cada citación legal aparece como pill clickeable que abre el chunk original | Notion AI, Harvey |
| `AgentProgressStepper` | Workflow de agente con steps verificables | Vercel deploy logs |
| `DiffViewer` | Redlining side-by-side con highlights | GitHub PR, Google Docs |
| `LegalTimeline` | Línea de tiempo de un caso con eventos, plazos y análisis | Linear roadmap |

#### 4.7.3 Onboarding rediseñado

- Tour de 3 pasos con `welcome-tour` (ya existe, mejorarlo).
- "Primer caso en 5 minutos" — wizard guiado con datos precargados de ejemplo.
- Plantillas starter por materia (laboral, civil, comercial) — el usuario elige una y todo se pre-rellena.

---

## 5. Plan técnico

### 5.1 Arquitectura target

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js 14    │    │   FastAPI 0.111 │    │     RQ          │
│   App Router    │    │   Python 3.12   │    │   Workers       │
│   Vercel        │ ←→ │   Railway       │ ←→ │   Railway       │
│                 │    │                 │    │   (Redis)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                      │
        │ HTTPS                 │ SQL                  │ Tesseract/Textract
        │ (cookies HttpOnly)    │ (asyncpg)            │
        ↓                       ↓                      ↓
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Browser       │    │   Supabase      │    │   Storage       │
│                 │    │   Postgres+pgvec│    │   Supabase/S3   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ↓
                        ┌─────────────────┐
                        │   LLM Gateway   │
                        │   (LiteLLM/     │
                        │   custom)       │
                        └─────────────────┘
                                │
                  ┌─────────────┼─────────────┐
                  ↓             ↓             ↓
             Anthropic       OpenAI       Minimax
```

**Decisiones arquitectónicas para 3.0**:

- **LLM Gateway**: introducir un gateway interno que abstrae providers y permite A/B testing, fallback automático y logging uniforme. **LiteLLM** (open-source, MIT) es la opción recomendada — proxy HTTP que normaliza la API entre Anthropic / OpenAI / modelos locales. Reduce dependencia de vendor y habilita fallback automático.
- **Workers**: separar workers por tipo (OCR, embeddings, agentes). Pool dedicado por tipo de tarea para no bloquear la cola.
- **Storage**: mantener Supabase Storage hasta 1GB (free tier). Más allá, evaluar **MinIO** (S3-compatible, open-source, self-hosted) corriendo en Railway o un VPS pequeño. Costo GB/mes ~10× menor que Supabase Storage. La abstracción `StorageService` ya está pensada para esto; falta el adapter `minio`.
- **Embeddings pipeline**: workers de embeddings separados para re-embebir el corpus legal sin tocar la cola principal.

### 5.2 Mejoras de infraestructura

#### 5.2.1 Cobertura de tests 70% → 80%+

| Suite | Hoy | Target 3.0 | Acción |
|---|---|---|---|
| Backend unit | ~60% | 80% | Cubrir services no testeados (clause_comparator, document_generator) |
| Backend integration | ~40% | 70% | E2E por endpoint crítico con `TestClient` + DB de test |
| Frontend unit | ~10% | 50% | Componentes UI (Button, Card, RiskBadge) |
| E2E (Playwright) | ~5% | 30% | Flujos críticos: login → crear caso → subir doc → ver análisis |

#### 5.2.2 CI/CD

- Backend: GitHub Actions ya corre ruff + pytest + compileall + build. **Agregar**: type check (mypy), seguridad (bandit), coverage report con threshold gate.
- Frontend: ESLint ya corre. **Agregar**: type check (tsc) con threshold incremental, Lighthouse CI para performance budget, axe-core para a11y.
- Preview deploys en Vercel siguen deshabilitados por decisión arquitectónica (CLAUDE.md). Mantener.

#### 5.2.3 Observabilidad (todo open-source self-hosted + Sentry free tier)

- **Sentry** (free tier, 5k eventos/mes): terminar de configurar (hoy está a medias). FastAPI + Next.js + RQ workers. Source maps solo a Sentry (no públicos).
- **Logs estructurados**: ya hay `app/core/logging.py`. Verificar que todos los endpoints loggean `request_id`, `user_id`, `tenant_id`, `latency_ms`. Destino: stdout (capturado por Docker → Railway logs) + archivo JSON rotado para querys históricos.
- **Métricas + visualización (auto-hospedado)**:
  - **Prometheus**: scraper de métricas. Endpoint `/metrics` en FastAPI vía `prometheus-fastapi-instrumentator`. Métricas custom para: latencia p50/p95/p99 por endpoint, tasa de errores por status code, uso de tokens LLM por tenant, queue depth de workers.
  - **Grafana**: dashboards. Visualización de latencias, errores, throughput, costos por tenant. Alertas configurables (Prometheus Alertmanager → Slack/email).
  - **Loki** (opcional): agregación de logs si el volumen lo justifica. Para empezar, stdout + grep es suficiente.
- **Todo self-hosted en Railway o un VPS pequeño** (Hetzner/OVH, ~$5/mes). Cero coste variable.

#### 5.2.4 Feature flags

- Librería: `flagsmith` o `posthog` (open-core).
- Casos de uso: rollout gradual de agentes (PLATFORM_ADMIN → beta tenants → todos), A/B test de prompts, kill switch si un modelo nuevo degrada.
- Implementación: middleware que evalúa flag por tenant antes de ejecutar.

### 5.3 Datos y RAG

#### 5.3.1 Estrategia de embeddings (plan A: API, plan B: open-source self-hosted)

**Plan A — OpenAI (default mientras coste sea bajo)**:
- `text-embedding-3-small` 1536 dims, $0.02/1M tokens.
- Para 100k chunks (~50M tokens de corpus legal): un único coste de ingestión ~$1. Queries son ~$0.0001 cada una.
- **Triggers para migrar a Plan B**: coste mensual > $200, dependencia de un solo provider, requisito de data residency en Chile.

**Plan B — sentence-transformers self-hosted (gratis, recomendado para producción)**:
- Librería: `sentence-transformers` (HuggingFace).
- Modelo recomendado: `BAAI/bge-m3` — multilingüe (español nativo), 568 dims (más compacto que 1536, mejor para HNSW), top-tier en MTEB benchmark.
- Alternativa: `intfloat/multilingual-e5-large` (560M params, ~1.1GB).
- **Infraestructura**: corre en el mismo worker Railway (CPU suficiente para docs legales cortos; GPU opcional si el volumen lo justifica). Sin coste adicional por query — solo RAM/CPU.
- **Trade-off**: +1 dependencia operacional (HuggingFace model cache, GPU opcional), -coste variable a escala (después de ~1M queries/mes, Plan B es más barato que Plan A).
- **Migración**: el `EmbeddingsService` ya debería tener interfaz abstracta. Cambiar de OpenAI client a `sentence-transformers` local es swap de implementación sin tocar call sites.

**Decisión recomendada**:
- **Fase 1**: mantener Plan A mientras el corpus legal se cura.
- **Fase 2**: introducir Plan B como opción, hacer A/B test contra golden dataset.
- **Fase 3**: Plan B como default si A/B test demuestra calidad equivalente (≤2% diferencia en recall@10).

#### 5.3.2 Vector store

- pgvector HNSW actual es suficiente hasta ~10M chunks. **No migrar** a Qdrant/Weaviate hasta que sea doloroso.
- Monitorear: p95 retrieval latency, recall@10 vs golden dataset.

#### 5.3.3 Eval pipeline

- Golden dataset de 50 preguntas jurídicas con respuesta esperada y citaciones requeridas.
- Script `pytest -m golden` corre cada pregunta contra el pipeline actual y mide: ¿se recupera el chunk correcto? ¿la respuesta lo cita?
- Gate: regresión > 5% en recall bloquea deploy.

### 5.4 Seguridad

#### 5.4.1 SOC 2 Type I readiness

- **Lo que falta**: documentar controles, implementar audit log completo (ya hay `AuditLog` model), penetration test externo.
- **Plazo objetivo**: 12-18 meses desde inicio (no es bloqueante para producto, pero sí para enterprise).
- **Acelerado por Fase 0 Ley 21.719**: las nuevas tablas `consent_records`, `data_processing_activities`, `rights_requests`, `breach_incidents` ya implementan varios controles que pide SOC 2 (consent trail, ROPA, breach notification). El trabajo de Fase 0 **es también** trabajo de SOC 2 readiness, no un duplicado.

#### 5.4.2 Hardening inmediato

- [ ] Rotación automática de `JWT_SECRET` (hoy es estático en `.env`).
- [ ] Rate limiting más granular (por endpoint, no solo `/login` y `/register`) usando `slowapi`.
- [ ] CSP estricto en producción (ya está configurado, asegurar que `script-src` no incluya `'unsafe-eval'` en prod).
- [ ] Sanitización de filenames de uploads (prevenir path traversal).
- [ ] Validación de magic bytes de PDFs (ya hay, expandir a DOCX).
- [ ] **Storage backend opcional**: introducir `MinIO` (S3-compatible, open-source) como alternativa self-hosted a Supabase Storage cuando el volumen supere 1GB o el coste sea relevante. La abstracción `StorageService` ya lo soporta conceptualmente — falta implementar el adapter.

### 5.5 Internacionalización (i18n)

- Hoy todo está hardcoded en español. **Fase 3**: introducir `next-intl` con namespace por página.
- Caso de uso: si vendemos a Perú, copy en `es-PE` (neutro regional funciona en muchos casos, pero términos legales varían).

---

## 6. Fases de implementación

**Convención de fases**: cada fase entrega valor de usuario + valor técnico. No se arranca la siguiente hasta cerrar los acceptance criteria de la anterior.

> ⚠️ **Importante**: la **Fase 0 (pre-vigencia Ley 21.719)** debe completarse **antes del 1 de diciembre de 2026**. Las demás fases se planifican en función de los recursos restantes una vez cerrado ese frente.

### Fase 0 — Pre-vigencia Ley 21.719 (cierre: antes del 2026-12-01)

**Objetivo**: que Lilian cumpla la Ley 21.719 desde el día 1 de su vigencia. Multas por no cumplir llegan hasta 20.000 UTM (~US$1.3M) y prohibición de operar con datos personales. Esta fase es **bloqueante** — no se arranca Fase 1 hasta cerrar Fase 0.

| # | Feature | Owner | Acceptance |
|---|---|---|---|
| 0.1 | Consentimiento explícito al registrar | Backend + Frontend | `POST /auth/register` rechaza con 422 si `terms_accepted=false` o `privacy_accepted=false`. Cada registro crea 2 `ConsentRecord` (terms@v1, privacy@v1) con IP y UA. |
| 0.2 | Textos legales públicos | Frontend | `/legal/privacy`, `/legal/terminos`, `/legal/cookies` accesibles sin auth, en español, versión visible. |
| 0.3 | Cookie banner con opt-in | Frontend | Aparece en primera visita, persiste decisión en localStorage, panel "Configurar" con toggles por scope. |
| 0.4 | Settings → Privacidad con derechos ARCO | Backend + Frontend | Lista consentimientos otorgados, log de accesos, botones de export/borrado/oposición. ZIP del export ≤ 5 MB. |
| 0.5 | Endpoint privacy en backend | Backend | 9 endpoints registrados (`/privacy/consent`, `/privacy/rights/me/*`, `/privacy/activities`, `/privacy/compliance-score`, `/privacy/breach-notify`). Tests al 80%. |
| 0.6 | Ley 21.719 en corpus Tier 1 | Backend | `law_chunks WHERE law_code='21719'` ≥ 50 filas. Golden dataset de 5 preguntas con `recall@5 ≥ 0.9`. |
| 0.7 | Ley 19.628 derogada con `valid_until` | Backend | Carga con metadata `repealed_by_21719: true`, `valid_until: 2026-12-01`. |
| 0.8 | Cita "Ley 21.719" en chat y `/precedents` | Frontend | Badge aparece en chat cuando se cita chunk con `legal_area="data_protection"`. Filtro dedicado en `/precedents`. |
| 0.9 | Worker SLA 30 días RightsRequest | Backend | Cron diario que escanea `RightsRequest` con `status=PENDING` y `requested_at + 30 días < now()`. Emite alerta Sentry. |
| 0.10 | Auditoría OpenAI/Anthropic DPA | Legal + Tech | DPA de ambos providers auditados contra art. 21 Ley 21.719. Documentado en `/legal/privacy`. |

**Riesgos específicos de Fase 0**:
- OpenAI/Anthropic podrían no tener DPA compatible con art. 21 a tiempo — mitigación: evaluar `mistral` (con data residency EU) o self-host con Llama 3 si no hay opción válida.
- Si el Sentry worker no se implementa a tiempo, una solicitud cerca del deadline podría pasar — mitigación: alerta de "30 días faltando" a partir del día 1 del request.

### Fase 1 — Fundamentos (Q1 2026: meses 1-3)

**Objetivo**: cerrar los gaps baratos que separan el MVP de un producto que retiene clientes.

> **Restricción de tooling**: las nuevas dependencias de Fase 1 (OCR, embeddings, observabilidad) son open-source / self-hosted según §2.2. Ningún coste variable adicional más allá del LLM. Decisión que se valida con A/B tests cuando haya alternativa.

| # | Feature | Owner sugerido | Acceptance |
|---|---|---|---|
| 1.1 | OCR para PDFs escaneados (Tesseract + PaddleOCR/Surya fallback) | Backend | PDF de 10p escaneado produce análisis completo < 60s con Tesseract en CPU |
| 1.2 | clause_comparator expuesto + endpoint + UI redlining | Full-stack | Comparar 2 versiones del mismo contrato muestra diff visual con ≥ 90% de cláusulas modificadas detectadas |
| 1.3 | Corpus legal chileno Tier 1 cargado | Backend | 5 códigos + 1000 sentencias en `law_chunks` con metadatos completos |
| 1.4 | Tests backend 70% → 80% | Backend | Gate en CI bloquea PRs con coverage < 80% |
| 1.5 | DiffViewer + CitationPill componentes | Frontend | Componentes usados en al menos 2 páginas reales |
| 1.6 | Batch upload | Full-stack | Subir 50 archivos en una acción, stepper muestra progreso, errores no bloquean |
| 1.7 | Agente "Revisión laboral express" (MVP) | Backend + IA | Workflow ejecuta 4 pasos, output con semáforo, latencia < 60s |
| 1.8 | Prometheus + Grafana operativos | Infra | Dashboard con latencia/errores/queue depth, alertas en Slack/email |

**Riesgos**:
- OCR open-source puede tener accuracy inferior en handwriting complejo; mitigación con cascada de engines + UI para re-subir.
- Corpus legal curado toma tiempo humano (1-2 semanas full-time para Tier 1).
- Worker con PaddleOCR (~1GB modelos) puede aumentar RAM del contenedor Railway; dimensionar antes.

### Fase 2 — Diferenciación (Q2 2026: meses 4-6)

**Objetivo**: hacer cosas que Harvey no hace para Chile.

| # | Feature | Owner | Acceptance |
|---|---|---|---|
| 2.1 | Predicción de resultados judiciales (MVP) | Backend + IA | Modelo con ≥ 65% precisión en test set, explicación top-5 features |
| 2.2 | Sistema de agentes framework | Backend | Plan/execute/reflect/human-in-the-loop funcionando, base para nuevos agentes |
| 2.3 | Agente "Due diligence M&A" | Backend + IA | Procesa carpeta de 50 docs, emite risk register priorizado |
| 2.4 | RAG eval pipeline | Backend + IA | Golden dataset de 50 preguntas, gate en CI, recall@10 medido |
| 2.5 | Mobile-first refactor dashboard completo | Frontend | Todas las páginas autenticadas con drawer móvil, sin overflow horizontal |
| 2.6 | Sentry 100% operativo | Infra | Errors tracked en producción, alerts configurados |

**Riesgos**:
- Predicción de resultados requiere volumen de datos que puede no existir.
- Framework de agentes es esfuerzo alto; recorte defensivo si se atrasa: dejar solo Agente 1 (revisión laboral) en Fase 1.

### Fase 3 — Ecosistema (Q3-Q4 2026: meses 7-9)

**Objetivo**: conectar Lilian con el ecosistema chileno real.

| # | Feature | Owner | Acceptance |
|---|---|---|---|
| 3.1 | Integración Poder Judicial (PJUD) | Backend | Búsqueda de causas por RUT de parte, últimas 10 |
| 3.2 | Integración SII (validación RUT) | Backend | Validar RUT contra SII en tiempo real, cache 24h |
| 3.3 | Firma electrónica (DocuSign + FirmaGob) | Full-stack | Generar contrato → enviar a firma → webhook → guardar firmado |
| 3.4 | Agente "Cumplimiento regulatorio semanal" | Backend + IA | Digest semanal automático por cliente |
| 3.5 | Multi-jurisdicción MVP (Perú) | Backend + IA | Tenant con `country="PE"` puede operar con templates y leyes peruanas |
| 3.6 | Marketplace de integraciones (light) | Full-stack | Directorio de integrations, OAuth flow básico |
| 3.7 | LLM Gateway interno | Backend | Abstracción de providers, A/B testing, fallback automático |

**Riesgos**:
- APIs de PJUD/SII no oficiales: riesgo legal y de estabilidad. Mitigación: rate limiting, alertas de cambios de schema.
- Firma electrónica: costos de DocuSign pueden hacer inviable el pricing. Evaluar FirmaGob primero.

### Fase 4 — Plataforma madura (Q1 2027: meses 10-12)

**Objetivo**: Lilian como sistema operativo del trabajo legal chileno.

| # | Feature | Owner | Acceptance |
|---|---|---|---|
| 4.1 | Dashboard predictivo de cartera | Frontend + IA | "Tus próximos 30 días: 5 plazos críticos, 2 clientes con riesgo de churn" |
| 4.2 | AI Agent por cliente (chat proactivo) | Backend + IA | El agente inicia conversaciones relevantes sin que el abogado pregunte |
| 4.3 | Workflows custom por tenant | Full-stack | El usuario define su propio agente con herramientas pre-built |
| 4.4 | SOC 2 Type I (audit externo) | Todos | Reporte aprobado, controles documentados |
| 4.5 | i18n (es-PE como segundo idioma) | Frontend | Tenant con `country="PE"` ve UI en español neutro o peruano |

---

## 7. Cómo hacer la herramienta atractiva (UX/UI)

> Esta sección merece atención explícita porque el equipo está más cómodo con backend que con diseño, y el "look and feel" es lo que convierte una demo en producto.

### 7.1 Anti-template policy (lo que NO hacer)

Ver `rules/ecc/web/design-quality.md`. Los anti-patrones que vemos hoy y hay que evitar:

- ❌ Card grids uniformes en el dashboard.
- ❌ Hero sections genéricos con gradiente y CTA.
- ❌ Sidebar gris + tabla + sin personalidad.
- ❌ Botones con sombras pesadas y rounded extremos.
- ❌ "Otro SaaS más" — si alguien confunde Lilian con Notion/Linear/Stripe a primera vista, fallamos.

### 7.2 La dirección visual correcta

**Editorial / magazine** combinado con **disciplina técnica**:
- Tipografía con peso contrastante (display grande + body pequeño).
- Uso deliberado de color (no decoración: rojo = riesgo, verde = éxito, ámbar = advertencia, azul = información).
- Capas con overlap intencional, no sombras genéricas.
- Motion que explica flujo (streaming del chat, transición de semáforo).
- Bents donde tiene sentido (la home del dashboard podría ser un bento: casos urgentes / análisis reciente / plazos / agentes activos).

**Referencias que vale la pena estudiar**:
- [Harvey](https://www.harvey.ai/) — el referente, por supuesto.
- [Linear](https://linear.app/) — UX impecable para flujos complejos.
- [Vercel](https://vercel.com/) — diseño técnico que se siente premium.
- [Stripe](https://stripe.com/) — documentación como producto.

### 7.3 El primer segundo importa

Cuando un usuario abre Lilian 3.0, debería ver:
1. **Casos urgentes** (bento card grande, con deadline pulsando).
2. **Análisis recientes** (lista compacta, click para detalle).
3. **Acciones rápidas** ("Nuevo caso", "Subir documento", "Preguntar al agente").
4. **Empty state emocional**: si es un usuario nuevo, no un "no tienes casos" frío, sino un "Empecemos con tu primer caso laboral" con CTA y plantilla.

### 7.4 El chat no es el centro

Hoy el chat es protagonista. En 3.0, el chat es una **herramienta más**. El centro es el caso. El abogado entra a Lilian a trabajar en un caso; el chat es donde pregunta si necesita ayuda; los agentes son donde delega trabajo.

### 7.5 Performance como estética

- Skeletons durante carga, no spinners genéricos.
- Streaming visible en el chat (letras apareciendo).
- Transiciones suaves entre estados.
- **El producto debe sentirse rápido aunque esté pensando**.

---

## 8. Riesgos y mitigaciones

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Costos de LLM explotan con adoption | Alta | Alto | LLM Gateway (LiteLLM) con rate limiting por tenant, alertas de spend, modelos pequeños para tareas simples, prompt caching Anthropic, A/B test contra `gpt-4o-mini` para confirmar que el modelo caro es necesario |
| R2 | Calidad de OCR open-source insuficiente para handwriting | Media | Alto | Cascada Tesseract → PaddleOCR → Surya con threshold de confianza; re-subir manual como fallback; entrenar detector de "OCR falló, contactar a soporte". Aceptar 85-90% accuracy vs 97% de Textract como trade-off justificado |
| R3 | PJUD/SII cambian su web y rompen scraping | Alta | Medio | Rate limiting, circuit breakers, UI que degrade graciosamente ("no se pudo consultar PJUD ahora"), suite de tests que detectan cambios de HTML antes de que lleguen a producción |
| R4 | Latencia de LLM en latam > mercados anglo | Media | Alto | Edge functions en Vercel, caching agresivo de embeddings (BGE-m3 self-hosted, sin rate limit externo), pre-compute de análisis comunes |
| R5 | Clientes corporativos piden compliance que no tenemos | Alta | Medio | SOC 2 readiness como inversión, no como nice-to-have |
| R6 | Multi-jurisdicción rompe el código hardcoded a Chile | Baja (Fase 3) | Alto | Iniciar refactor de prompts con `country` field desde Fase 1 aunque no se use |
| R7 | Un agente hace daño (borrado, firma errónea) | Media | Crítico | Human-in-the-loop obligatorio en acciones destructivas; cola de aprobación visible |
| R8 | Modelo de predicción legal con baja precisión daña reputación | Media | Alto | Disclaimer visible, modelo se ofrece como "exploratorio" hasta validar; golden dataset mantenido |
| R9 | Costo de MinIO o sentence-transformers en Railway excede free tier | Baja | Medio | Railway free tier es limitado; si se llega al límite, migrar a VPS Hetzner/OVH ($5/mes) o self-host en contenedor dedicado. El costo sigue siendo 1-2 órdenes de magnitud menor que las alternativas SaaS |
| R10 | No cumplir Ley 21.719 al 1-dic-2026 | Alta | Crítico | Fase 0 es bloqueante. Multas hasta 20.000 UTM (~US$1.3M) + prohibición de operar. Mitigación: Fase 0 completa antes de 2026-12-01 con consentimiento, ARCO, ROPA, brechas, texto legal y corpus. Si no se llega a tiempo: scope mínimo = solo lo defensivo (consentimiento + texto legal + ARCO), dejar Fase 2-3 para después de la fecha. |

---

## 9. KPIs por fase

### Fase 0 (cierre) — antes del 2026-12-01

- [ ] 100% de nuevos usuarios con `ConsentRecord` registrado
- [ ] `/legal/privacy`, `/legal/terminos`, `/legal/cookies` públicos y accesibles
- [ ] Cookie banner operativo, decisiones persistidas en localStorage
- [ ] `POST /auth/register` rechaza con 422 sin consentimiento explícito
- [ ] `GET /privacy/rights/me/export` devuelve ZIP < 5 MB con datos estructurados
- [ ] `law_chunks WHERE law_code='21719'` ≥ 50 filas, `recall@5 ≥ 0.9` para preguntas de privacidad
- [ ] Worker SLA 30 días RightsRequest escaneando diariamente
- [ ] DPA de OpenAI y Anthropic auditados, documentados en `/legal/privacy`

### Fase 1 (cierre)

- [ ] Coverage backend ≥ 80%
- [ ] OCR procesa 100 PDFs escaneados sin error
- [ ] clause_comparator detecta ≥ 90% de cambios en test set
- [ ] Al menos 1 bufete paga plan Pro durante 3 meses
- [ ] Compliance score promedio de tenants ≥ 75 (grado C)
- [ ] Agente "Auditoría de privacidad" detecta ≥ 3 cláusulas por contrato en golden dataset

### Fase 2 (cierre)

- [ ] Modelo de predicción con ≥ 65% precisión
- [ ] 2 agentes funcionando end-to-end
- [ ] NPS ≥ 30 en beta con 10 bufetes
- [ ] Recall@10 ≥ 80% en golden dataset de 50 preguntas

### Fase 3 (cierre)

- [ ] 3 integraciones activas (PJUD, SII, firma electrónica)
- [ ] Multi-jurisdicción MVP con 1 cliente peruano en producción
- [ ] MAU activos ≥ 20 firmas
- [ ] Casos analizados/mes ≥ 100 a través de la plataforma

### Fase 4 (cierre)

- [ ] SOC 2 Type I aprobado
- [ ] MAU activos ≥ 40 firmas
- [ ] Retención M3 ≥ 70%
- [ ] NPS ≥ 40

---

## 10. Conclusiones

Lilian 2.x está mejor plantada de lo que parece. La fundación (multi-tenant, RBAC, RAG, streaming chat) es sólida. Lo que falta es:

1. **Cerrar gaps baratos** (OCR, clause_comparator, corpus legal) — Fase 1.
2. **Construir diferenciadores** (predicción, agentes) — Fase 2.
3. **Integrar el ecosistema** (PJUD, SII, firma) — Fase 3.
4. **Madurar como plataforma** (SOC 2, marketplace, multi-jurisdicción) — Fase 4.

El éxito no es ser Harvey. Es ser **la mejor herramienta legal para Chile**, con agentes que ejecutan trabajo real, no chatbots que responden preguntas. Si en 12 meses un abogado chileno abre Lilian y dice "no podría trabajar sin esto", ganamos.

---

## Apéndice A — Referencias cruzadas

- `docs/STATE_OF_PRODUCT_2026-08-21.md` — Estado actual detallado por componente.
- `docs/architecture.md` — Arquitectura técnica actual.
- `docs/rbac-matrix.md` — Matriz de permisos por rol.
- `ROADMAP_HARVEY_FEATURES.md` — Bitácora histórica de qué se implementó.
- `docs/PERFORMANCE.md` — Budgets y métricas de performance.
- `docs/SECURITY.md` — Estado de seguridad y pendientes.
- `rules/ecc/web/design-quality.md` — Estándares de calidad de diseño.

## Apéndice B — Glosario de términos 3.0

| Término | Definición |
|---|---|
| **Agente** | Workflow multi-step que ejecuta una tarea legal concreta, no solo responde preguntas. |
| **CitationPill** | Componente UI que muestra una citación legal como clickeable; al hacer click abre el chunk original. |
| **Clause comparator** | Servicio que alinea y compara cláusulas entre dos versiones del mismo contrato. |
| **Diff viewer** | UI side-by-side para visualizar redlining. |
| **Human-in-the-loop** | Patrón donde el agente pausa en acciones destructivas o de alto impacto para aprobación humana. |
| **OCR** | Optical Character Recognition. Extracción de texto de PDFs escaneados (Tesseract, AWS Textract). |
| **pgvector** | Extensión de PostgreSQL para búsqueda por similitud con embeddings. |
| **PLATFORM_ADMIN** | Rol cross-tenant que ve todas las organizaciones. |
| **RAG** | Retrieval-Augmented Generation. Patrón donde el LLM responde con contexto recuperado de una base vectorial. |
| **RRF** | Reciprocal Rank Fusion. Algoritmo para combinar resultados de múltiples búsquedas (embeddings + keyword). |
| **Share link** | URL firmada con TTL para compartir informes externamente sin requerir cuenta. |
| **Stepper** | UI de progreso por pasos durante procesamiento asíncrono. |
