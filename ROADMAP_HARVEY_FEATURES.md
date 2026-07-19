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

### ⏳ 4. Análisis de Tendencias Jurisprudenciales
**Prioridad:** Baja | **Tiempo estimado:** 3-4 horas | **Complejidad:** Baja

**Descripción:** Estadísticas sobre evolución de fallos: distribución por tribunal, tendencia temporal, factores comunes.

**Lo que ya existe:**
- `Precedent` model con todos los campos necesarios
- Endpoint de búsqueda `GET /precedents/search`
- Datos en Supabase

**Lo que falta:**
- [ ] Endpoint: `GET /precedents/analytics`
- [ ] Aggregation queries (win-rate por tribunal, por año, por materia)
- [ ] Dashboard de tendencias en frontend

**Ventajas:**
- Relativamente simple de implementar
- Queries SQL directas
- Dashboard visual de alto valor

**Desventajas:**
- Valor limitado sin muchos precedentes
- Solo tan bueno como los datos indexados
- No usa RAG/AI, solo analytics

---

## Tabla Comparativa

| Funcionalidad | Estado | Tiempo | Complejidad | Impacto | Ventaja |
|---------------|--------|--------|-------------|---------|---------|
| Chat Mejorado | ✅ | 2-3h | Baja | Alto | Medien |
| Contratos Inteligentes | ✅ | 4h | Media | Alto | Hoch |
| Detección Conflictos | ✅ | 2h | Media | Medio | Hoch |
| Predicción Judicial | ⏳ | 8-12h | Alta | Muy Alto | Unique |
| Tendencias Jurisprudenciales | ⏳ | 3-4h | Baja | Medio | Medien |

---

## Próximos Pasos Recomendados

1. **Largo plazo:** Predicción Judicial (#4) - Más complejo, dejar para después
2. **Cuando haya datos:** Tendencias (#5) - Simple pero requiere precedentes

---

## Historial de Commits

| Fecha | Commit | Descripción |
|-------|--------|-------------|
| 2026-07-19 | 87b43d4 | feat: detección de conflictos normativos contractuales |
| 2026-07-19 | 570a27a | feat: integrar extracción inteligente de variables en frontend |
| 2026-07-19 | a7d44d3 | feat: extracción inteligente de variables para generación de contratos |
| 2026-07-19 | cd517f2 | feat: integración de precedentes judiciales en chat conversacional |
| 2026-07-17 | e99b161 | feat: integración de búsqueda de precedentes judiciales en análisis de casos |
