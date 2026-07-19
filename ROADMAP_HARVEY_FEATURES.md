# ROADMAP: Funcionalidades Tipo Harvey.ai para LILIAN

## Estado: En Desarrollo

---

## Funcionalidades Implementadas

### ✅ 1. Búsqueda de Precedentes Legales (Completado: 2026-07-17)
**Commit:** `e99b161` - feat: integración de búsqueda de precedentes judiciales en análisis de casos

**Lo que hace:**
- Endpoint `GET /precedents/search` con búsqueda semántica y por keywords
- Índice automático de embeddings al crear precedente
- Búsqueda por tribunal, año, área legal, tipo de materia
- Modelo `Precedent` con todos los campos judiciales

**Archivos:**
- `apps/backend/app/api/endpoints/precedents.py`
- `apps/backend/app/models/precedent.py`
- `apps/backend/app/services/precedent_rag.py`
- `infra/supabase/migrations/022_create_precedents.sql`

---

### ✅ 2. Integración de Precedentes en Análisis de Casos (Completado: 2026-07-18)
**Commit:** `e99b161`

**Lo que hace:**
- `get_precedents_context_for_rag()` busca precedentes según tipo de materia
- El prompt del LLM incluye sección "PRECEDENTES JUDICIALES RELEVANTES"
- Queries específicas por área legal (laboral, civil, consumer, family, etc.)

**Archivos:**
- `apps/backend/app/services/analysis.py` - Modificado

---

### ✅ 3. Chat Legal Mejorado (Completado: 2026-07-19)
**Commit:** `cd517f2` - feat: integración de precedentes judiciales en chat conversacional

**Lo que hace:**
- Modifica `get_relevant_context()` para incluir búsqueda de precedentes
- Añade parámetro `include_precedents=True` por defecto
- El chat ahora responde con contexto de documentos + leyes + precedentes judiciales
- Soporta filtro por área legal en búsqueda de precedentes

**Archivos:**
- `apps/backend/app/services/chat.py` - Modificado

---

## Funcionalidades Pendientes

### ⏳ 1. Generación de Contratos Inteligentes (Completado: 2026-07-19)
**Commits:** `a7d44d3` (backend) + `570a27a` (frontend)

**Backend implementado:**
- Función `extract_variables_from_matter()` usa LLM para analizar documentos
- Endpoint `POST /doc-templates/suggest-variables`
- Analiza documentos del caso y sugiere valores para templates

**Frontend implementado:**
- Botón "Sugerir desde caso" en DocumentGenerator component
- Llama al endpoint `/doc-templates/suggest-variables`
- Muestra variables sugeridas y missing_fields
- Aplica sugerencias automáticamente al formulario

**Estado:** ✅ Completado en backend y frontend

---

### ⏳ 2. Predicción de Resultados Judiciales
**Prioridad:** Media | **Tiempo estimado:** 8-12 horas | **Complejidad:** Alta

**Descripción:** Basado en precedentes similares, predecir probabilidad de éxito de una estrategia legal.

**Lo que ya existe:**
- `precedent_rag.py` con búsqueda por embedding
- Scores de similaridad en búsquedas

**Lo que falta:**
- [ ] Modelo de features: tipo de recurso, tribunal,法官, materia, montos
- [ ] Algoritmo de predicción (weighted average de similarity + same-court-history)
- [ ] Endpoint: `GET /precedents/predict`
- [ ] Dashboard de predicción en frontend

**Ventajas:**
- Feature único y muy valioso
- Alto valor percibido por usuarios
- Base para analytics más complejos

**Desventajas:**
- Más complejo de implementar
- Requiere datos suficientes para precisión
- Difícil de validar sin historial real
- Puede dar falsa confianza

---

### ⏳ 3. Detección de Conflictos Normativos (Completado: 2026-07-19)
**Commit:** `87b43d4` - feat: detección de conflictos normativos contractuales

**Lo que hace:**
- Función `detect_normative_conflicts()` compara cláusulas con leyes chilenas
- Detecta conflictos directos (severidad: high/medium/low)
- Detecta cláusulas en observación
- Integrada en `analyze_contract()` automáticamente
- Añadida al schema `RISK_ANALYSIS_SCHEMA`

**Estado:** ✅ Completado

---

### ⏳ 4. Análisis de Tendencias Jurisprudenciales (Completado: 2026-07-19)
**Commits:** `ad872a6` (backend) + `bfdf6c8` (frontend)

**Backend implementado:**
- `precedent_analytics.py` con get_precedent_analytics()
- Endpoint GET /precedents/analytics
- Endpoint GET /precedents/analytics/filters
- Métricas: volume_by_year, volume_by_court, volume_by_legal_area
- Court × Matter heatmap, top_voces, top_ponentes
- Análisis temporal y opcional de texto

**Frontend implementado:**
- PrecedentAnalyticsDashboard component
- Gráficos de barras, líneas, heatmap
- Filtros por tribunal, área legal, año
- Análisis de texto opcional

**Estado:** ✅ Completado

---

## Tabla Comparativa

| Funcionalidad | Estado | Tiempo | Complejidad | Impacto | Ventaja |
|---------------|--------|--------|-------------|---------|---------|
| Chat Mejorado | ✅ | 2-3h | Baja | Alto | Medien |
| Contratos Inteligentes | ✅ | 4h | Media | Alto | Hoch |
| Detección Conflictos | ✅ | 2h | Media | Medio | Hoch |
| Tendencias Jurisprudenciales | ✅ | 4h | Baja | Medio | Medien |
| Predicción Judicial | ⏳ | 8-12h | Alta | Muy Alto | Unique |

---

## Próximos Pasos Recomendados

1. **Largo plazo:** Predicción Judicial - Más complejo, dejar para después (requiere curacion de datos)

---

## Historial de Commits

| Fecha | Commit | Descripción |
|-------|--------|-------------|
| 2026-07-19 | bfdf6c8 | feat: dashboard de tendencias jurisprudenciales - frontend |
| 2026-07-19 | ad872a6 | feat: dashboard de tendencias jurisprudenciales - backend |
| 2026-07-19 | 87b43d4 | feat: detección de conflictos normativos contractuales |
| 2026-07-19 | 570a27a | feat: integrar extracción inteligente de variables en frontend |
| 2026-07-19 | a7d44d3 | feat: extracción inteligente de variables para generación de contratos |
| 2026-07-19 | cd517f2 | feat: integración de precedentes judiciales en chat conversacional |
| 2026-07-17 | e99b161 | feat: integración de búsqueda de precedentes judiciales en análisis de casos |
