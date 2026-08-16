# Operaciones manuales para cerrar Fases 2 y 3

> **Para quién es este doc:** ti, después de que yo termine de escribir código.
> **Estado de los commits al momento de escribir este doc:**
> los 6 commits de Fase 0 + 1 + 2 + 3 están en `main` **localmente**.
> NO se han pusheado todavía. Railway y Vercel siguen corriendo código viejo.

---

## Resumen de qué cambió (qué vas a deployar)

| Commit | Qué hace | Quién lo despliega |
|---|---|---|
| `2ac6295` | Fix loop landing→login | Vercel (auto en push) |
| `9b72e89` | Chat conectado al backend | Vercel (auto en push) |
| `af1db82` | Memoria persistente (schema + service) | Vercel + Railway + Supabase |
| `87da8de` | Streaming LLM (Anthropic + endpoint + frontend) | Vercel + Railway |
| `0b38665` | Agentes backend (case_researcher, drafting_assistant, compliance_checker) + schema | Vercel + Railway + Supabase |
| `79da34c` | UI: dropdown de modo en el chat | Vercel |

---

## Paso 1 — Pushear los commits

```bash
cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
git push origin main
```

**Qué pasa automáticamente:**
- **Vercel** detecta el push, redeploy del frontend (1-2 min). Los commits `2ac6295`, `9b72e89` y la parte frontend de `87da8de` (ChatPanel.tsx) entran en producción.
- **Railway** NO redeploya solo en push a `main` (configurado para redeploy solo en push a su propio repo). Hay que trigger manual (ver paso 4).

---

## Paso 2 — Verificar que Vercel SSO está desactivado

Sin esto, el frontend en producción está bloqueado detrás de autenticación Vercel y no puedes probar nada.

1. Abre https://vercel.com/jorgeguerrerohidalgo710/lil-i-an/settings/deployment-protection
2. **Vercel Authentication** → Standard Protection → **off**
3. Espera 30s a que el cambio propague

Si necesitas Vercel SSO activo, déjalo encendido pero agrega tu email a la allowlist.

---

## Paso 3 — Aplicar las migraciones SQL en Supabase

Las migraciones **NO se aplican solas**. Hay que correrlas contra la base de datos.

### 3a. Desde el dashboard de Supabase (recomendado para 1 sola vez)

1. Abre https://supabase.com/dashboard/project/yjiglcxuzizjgzlldqji/sql/new
2. Crea 5 queries nuevas (una por archivo, en orden):

**Query 1** — pegar el contenido de:
```
infra/supabase/migrations/028_user_facts.sql
```
Click **Run**.

**Query 2** — pegar:
```
infra/supabase/migrations/029_case_context_snapshots.sql
```
Click **Run**.

**Query 3** — pegar:
```
infra/supabase/migrations/030_feedback_signals.sql
```
Click **Run**.

**Query 4** — pegar:
```
infra/supabase/migrations/031_agent_runs.sql
```
Click **Run**.

**Query 5** — pegar:
```
infra/supabase/migrations/032_agent_steps.sql
```
Click **Run**.

### 3b. Verificar que las tablas existen

En el SQL editor corre:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'user_facts', 'case_context_snapshots', 'feedback_signals',
    'agent_runs', 'agent_steps'
  );
```

Debes ver las 5 tablas listadas.

---

## Paso 4 — Redeployar Railway con los cambios de backend

Los commits `af1db82` y `87da8de` cambiaron código del backend (modelos, servicios, endpoints). Railway los necesita.

### 4a. Si tu repo Railway está linkeado a GitHub

Solo necesitas hacer el push (Paso 1) Y redeployar manualmente:

```bash
# Opción CLI
railway up

# O desde el dashboard:
# https://railway.app/project/liliap → Deployments → "Deploy" en el branch actual
```

### 4b. Si Railway redeploya automático en push a su repo

Solo push (Paso 1) basta. Verifica en https://railway.app/project/liliap/deployments que hay un deploy nuevo después de tu push.

### 4c. Verificar que arrancó bien

Después del redeploy:
```bash
curl https://liliap-production.up.railway.app/health
```

Debe devolver `{"status":"healthy"}`. Si devuelve 500 o se queda cargando, abre los logs en Railway y mira el traceback.

---

## Paso 5 — Validar login + chat en producción

Abre https://lil-i-rj551xub2-jorgeguerrerohidalgo710.vercel.app en el browser (o la URL que Vercel te dio).

### 5a. Login

1. Si ya tienes usuario: entra con email + contraseña.
2. Si no tienes: regístrate en `/auth/register`.
3. **Verifica que entras a `/dashboard` sin loop.** Antes rebotaba entre login y dashboard; ahora debe quedarse en dashboard.

### 5b. Probar el chat (con streaming)

1. Abre el chat del dashboard (botón flotante abajo a la derecha).
2. Escribe: "¿Qué dice el artículo 4 del Código del Trabajo sobre la jornada laboral?"
3. **Debes ver:**
   - La respuesta empieza a llegar palabra por palabra (no espera 15s a que llegue todo).
   - El mensaje queda guardado en la BD (cierra el chat y vuélvelo a abrir → el historial persiste).

### 5c. Probar la memoria persistente

1. En el chat, pregunta algo que NO debería estar en los documentos del caso, p.ej. "Resume el caso en 3 frases".
2. Verifica que la respuesta menciona detalles del caso real (si tienes documentos cargados) o que indique que no hay documentos.
3. **Para verificar la persistencia de `user_facts`:**
   ```sql
   -- En Supabase SQL editor
   SELECT id, organization_id, user_id, kind, content, confidence
   FROM user_facts
   ORDER BY created_at DESC
   LIMIT 10;
   ```
   Al principio estará vacío. Los facts se crean cuando:
   - El usuario califica con thumbs up/down un mensaje (botón aún no en UI → se llenará con código futuro)
   - Se llama `memory.record_user_fact()` directamente desde admin/seed

4. **Para verificar la persistencia de `case_context_snapshots`:**
   ```sql
   SELECT id, matter_id, summary, version, updated_at
   FROM case_context_snapshots
   ORDER BY updated_at DESC
   LIMIT 5;
   ```
   También empezará vacío. Se llena cuando un endpoint llame a `memory.update_case_snapshot()` (lo añadiremos en Fase 3 cuando los agentes ejecuten resúmenes).

---

## Paso 6 (Opcional pero recomendado) — Activar embeddings reales

`EMBEDDING_PROVIDER=dummy` en producción significa que las búsquedas semánticas son hash determinístico, no embeddings de verdad. Esto baja mucho la calidad del RAG aunque el código sea correcto.

### 6a. Cambiar la env var en Railway

Desde el dashboard Railway (https://railway.app/project/liliap → Variables):

```
EMBEDDING_PROVIDER=openai
```

O por CLI:
```bash
railway variables --set "EMBEDDING_PROVIDER=openai"
```

Esto causa un redeploy automático. Railway ya tiene `OPENAI_API_KEY` configurado (ver HANDOFF.md), así que no necesitas agregar nada más.

### 6b. Reindexar el corpus de leyes

Las leyes chilenas (14 PDFs en `apps/backend/laws/`) están indexadas con embeddings dummy. Tienes que reindexar.

**Local (recomendado — más rápido, sin gastar compute de Railway):**

```bash
cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
export EMBEDDING_PROVIDER=openai
export DATABASE_URL="postgresql://postgres:TU_PASSWORD@db.yjiglcxuzizjgzlldqji.supabase.co:5432/postgres"

python3 apps/backend/workers/law_indexer.py \
    --laws-dir apps/backend/laws \
    --batch-size 50
```

Vas a gastar ~$0.10-0.30 USD en tokens de OpenAI (text-embedding-3-small es barato: $0.02 / 1M tokens).

**Desde Railway (si prefieres):**

```bash
railway run python apps/backend/workers/law_indexer.py \
    --laws-dir apps/backend/laws \
    --batch-size 50
```

### 6c. Verificar que la búsqueda semántica mejoró

```bash
# Antes con dummy: cosine ~ 0.0-0.3 incluso para queries muy relevantes
# Después con openai: cosine > 0.5 para queries relevantes
```

Mide la calidad con una búsqueda manual en el chat: si preguntas "despido injustificado" y la respuesta cita el Código del Trabajo con artículos correctos, los embeddings están funcionando.

---

## Paso 7 — Verificación final (smoke test completo)

Checklist para considerar Fases 2 y 3 cerradas:

- [ ] `git push origin main` hecho
- [ ] Vercel SSO desactivado
- [ ] 5 migraciones SQL aplicadas en Supabase
- [ ] `user_facts`, `case_context_snapshots`, `feedback_signals`, `agent_runs`, `agent_steps` existen en la BD
- [ ] Railway redeployado y `/health` responde 200
- [ ] Login funciona (entra a `/dashboard`, no loop)
- [ ] Chat responde con streaming (tokens incrementales)
- [ ] Historial del chat persiste tras refresh del browser
- [ ] Dropdown "Modo" visible arriba del input del chat
- [ ] Modo "Investigar caso" devuelve un brief estructurado (summary + leyes + riesgos)
- [ ] Modo "Redactar documento" devuelve un draft con variables
- [ ] (curl) Modo "Revisar cumplimiento" devuelve violaciones con ley citada
- [ ] (Opcional) Embeddings reales activados + corpus reindexado
- [ ] (Opcional) Calidad de búsqueda semántica mejorada

---

## Troubleshooting

### "Login sigue en loop después del push"

Vercel puede tardar hasta 5 minutos en propagar. Si después de 5 min sigue, abre DevTools → Network → recarga `/dashboard` → mira si la cookie `lilian_auth_token` está presente. Si no, el BFF no la está emitiendo: chequea los logs de Vercel para el endpoint `/api/auth/login`.

### "Chat dice 'No se pudo crear la sesión de chat (HTTP 500)'"

El backend no migró las tablas o los modelos. Verifica:
1. Las 3 migraciones aplicadas (Paso 3b).
2. Railway redeployó con el código nuevo (Paso 4). Si no, los modelos `UserFact` etc. no existen en el proceso de Python.

### "Streaming no funciona, devuelve respuesta completa de golpe"

El navegador no soporta `ReadableStream` o el proxy está buffereando. Verifica:
1. Header `X-Accel-Buffering: no` en la respuesta (debería estar).
2. El endpoint `/api/v1/chat/message/stream` responde 200 con `Content-Type: text/event-stream`.

El frontend debería caer automáticamente al endpoint bloqueante `/api/v1/chat/message` si el stream falla (404/405), pero si responde 200 y se queda pegado, hay un proxy buffering issue.

### "Migración SQL falla con 'relation does not exist'"

Probablemente las migraciones anteriores no se aplicaron. Mira `infra/supabase/migrations/022_create_precedents.sql` etc. y verifica el orden histórico. Las nuevas (`028`, `029`, `030`) solo dependen de tablas existentes (`organizations`, `users`, `matters`, `chat_messages`) que ya estaban.

---

## Lo que NO está en este doc

- Tests automatizados: no agregué tests para memoria/streaming en este PR. Cobertura ~70% según `STATUS_v2.1.md`. Sprint 8 del roadmap los aborda.
- Migración a Alembic: sigue con SQL ad-hoc. Sin bloqueante.
- Agentes (Fase 3): no incluidos. La base de memoria está lista para soportarlos.