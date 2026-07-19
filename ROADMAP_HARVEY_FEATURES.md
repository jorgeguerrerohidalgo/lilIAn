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

### ⏳ 1. Generación de Contratos Inteligentes - Integración Frontend
**Prioridad:** Alta | **Estado backend:** ✅ Completado | **Estado frontend:** ⏳ Pendiente

**Backend implementado (Commit `a7d44d3`):**
- Función `extract_variables_from_matter()` usa LLM para analizar documentos
- Endpoint `POST /doc-templates/suggest-variables`
- Analiza documentos del caso y sugiere valores para templates

**Lo que falta (Frontend):**
- [ ] Botón "Sugerir desde caso" en DocumentGenerator component
- [ ] Integrar llamada a `/suggest-variables`
- [ ] Mostrar variables sugeridas para confirmación
- [ ] Poder editar antes de generar

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

### ⏳ 3. Detección de Conflictos Normativos
**Prioridad:** Media | **Tiempo estimado:** 6-8 horas | **Complejidad:** Media

**Descripción:** Analizar si un contrato contradice alguna ley o regulación chilena vigente.

**Lo que ya existe:**
- `get_laws_context_for_rag()` en analysis.py
- RAG de leyes chilenas indexadas
- Sistema de análisis de documentos

**Lo que falta:**
- [ ] Motor de comparación contrato vs ley
- [ ] Detección de cláusulas potencialmente abusivas
- [ ] Alertas específicas (no solo riesgos generales)
- [ ] Nueva función `detect_normative_conflicts()` en analysis.py

**Ventajas:**
- Muy útil para revisión de contratos
- Conecta análisis con RAG de leyes
- Detectable con lógica de comparación

**Desventajas:**
- Requiere que el contrato cite leyes explícitamente
- Complejidad en interpretar "conflicto"
- Puede generar falsos positivos

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
| Contratos Inteligentes (backend) | ✅ | 2h | Media | Alto | Hoch |
| Contratos Inteligentes (frontend) | ⏳ | 2h | Media | Alto | Hoch |
| Predicción Judicial | ⏳ | 8-12h | Alta | Muy Alto | Unique |
| Detección Conflictos | ⏳ | 6-8h | Media | Medio | Hoch |
| Tendencias Jurisprudenciales | ⏳ | 3-4h | Baja | Medio | Medien |

---

## Próximos Pasos Recomendados

1. **Inmediato:** Integrar frontend de Contratos Inteligentes - Botón "Sugerir desde caso"
2. **Corto plazo:** Detección Conflictos (#3) - Conecta con análisis existente
3. **Largo plazo:** Predicción (#3) - Más complejo, dejar para después
4. **Cuando haya datos:** Tendencias (#4) - Simple pero requiere precedentes

---

## Historial de Commits

| Fecha | Commit | Descripción |
|-------|--------|-------------|
| 2026-07-19 | a7d44d3 | feat: extracción inteligente de variables para generación de contratos |
| 2026-07-19 | cd517f2 | feat: integración de precedentes judiciales en chat conversacional |
| 2026-07-17 | e99b161 | feat: integración de búsqueda de precedentes judiciales en análisis de casos |
