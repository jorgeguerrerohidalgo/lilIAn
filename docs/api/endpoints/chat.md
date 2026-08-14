# API — Chat

> Router: `apps/backend/app/api/endpoints/chat.py` · Prefijo: `/api/v1/chat` · Tag OpenAPI: `chat`

Chat asistido por IA sobre un caso. Cada sesión está anclada a un `matter_id`; las respuestas se generan con el LLM configurado usando como contexto los documentos del caso (RAG).

---

## Índice

- [Resumen de endpoints](#resumen-de-endpoints)
- [Modelo de datos](#modelo-de-datos)
- [POST /api/v1/chat/sessions](#post-apiv1chatsessions)
- [GET /api/v1/chat/sessions](#get-apiv1chatsessions)
- [GET /api/v1/chat/sessions/{session_id}/messages](#get-apiv1chatsessionssession_idmessages)
- [POST /api/v1/chat/message](#post-apiv1chatmessage)
- [Flujo completo](#flujo-completo)
- [Errores comunes](#errores-comunes)
- [Rate limits](#rate-limits)
- [Notas de seguridad](#notas-de-seguridad)

---

## Resumen de endpoints

| Método | Path | Auth | Éxito | Descripción |
|---|---|---|---|---|
| `POST` | `/api/v1/chat/sessions` | Bearer + org | `201` | Crea una sesión de chat sobre un caso |
| `GET` | `/api/v1/chat/sessions` | Bearer + org | `200` | Lista sesiones, opcionalmente por caso |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | Bearer + org | `200` | Historial de mensajes de la sesión |
| `POST` | `/api/v1/chat/message` | Bearer + org | `200` | Envía un mensaje y recibe la respuesta del asistente |

> El router define también `DELETE /api/v1/chat/sessions/{session_id}` para eliminar una sesión.

---

## Modelo de datos

### `ChatSessionResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `matter_id` | `int` | Caso al que pertenece la sesión |
| `title` | `str \| null` | Título de la conversación |
| `created_at` | `str` | ISO 8601 |
| `updated_at` | `str` | ISO 8601 |

### `ChatMessageResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `int` | |
| `role` | `str` | `user` o `assistant` |
| `content` | `str` | Texto del mensaje |
| `model_provider` | `str \| null` | Proveedor usado para generar la respuesta |
| `model_name` | `str \| null` | Modelo usado |
| `created_at` | `str` | ISO 8601 |

### `MessageResponse` (respuesta de `POST /message`)

| Campo | Tipo | Notas |
|---|---|---|
| `content` | `str` | Respuesta generada por el asistente |
| `session_id` | `int` | |
| `message_id` | `int` | Id del mensaje del asistente persistido |

---

## `POST /api/v1/chat/sessions`

Crea una sesión de chat anclada a un caso.

- **Auth**: Bearer + membresía de organización
- **Content-Type**: `application/json`
- **Status éxito**: `201 Created`

### Request body — `CreateSessionRequest`

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `matter_id` | `int` | Sí | Debe pertenecer a la organización del usuario |
| `title` | `str \| null` | No | Máximo 200 caracteres |

```bash
curl -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "matter_id": 1,
    "title": "Consultas sobre el contrato de trabajo"
  }'
```

```json
{
  "id": 5,
  "matter_id": 1,
  "title": "Consultas sobre el contrato de trabajo",
  "created_at": "2025-01-15T12:34:56Z",
  "updated_at": "2025-01-15T12:34:56Z"
}
```

---

## `GET /api/v1/chat/sessions`

### Query params

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `matter_id` | `int \| null` | `None` | Filtra las sesiones de un caso concreto |

```bash
# Todas las sesiones de la organización
curl http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer $TOKEN"

# Sesiones de un caso
curl "http://localhost:8000/api/v1/chat/sessions?matter_id=1" \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta: `list[ChatSessionResponse]`.

---

## `GET /api/v1/chat/sessions/{session_id}/messages`

Historial completo de la sesión, en orden cronológico.

```bash
curl http://localhost:8000/api/v1/chat/sessions/5/messages \
  -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "id": 101,
    "role": "user",
    "content": "¿El contrato incluye cláusula de confidencialidad?",
    "model_provider": null,
    "model_name": null,
    "created_at": "2025-01-15T12:35:10Z"
  },
  {
    "id": 102,
    "role": "assistant",
    "content": "Sí. La cláusula décima del contrato establece una obligación de confidencialidad...",
    "model_provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514",
    "created_at": "2025-01-15T12:35:14Z"
  }
]
```

---

## `POST /api/v1/chat/message`

Envía un mensaje del usuario y devuelve la respuesta del asistente. La llamada es **síncrona**: espera a que el LLM termine de generar.

- **Content-Type**: `application/json`
- **Status éxito**: `200 OK`

### Request body — `SendMessageRequest`

| Campo | Tipo | Requerido | Restricciones |
|---|---|---|---|
| `session_id` | `int` | Sí | Sesión existente de la organización |
| `message` | `str` | Sí | Longitud mínima 1, máximo `CHAT_MESSAGE_MAX_LEN` |
| `legal_area_override` | `str \| null` | No | Máximo 64 caracteres. Fuerza el área legal usada para seleccionar el contexto |

### Response 200 — `MessageResponse`

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 5,
    "message": "¿El contrato incluye cláusula de confidencialidad?"
  }'
```

```json
{
  "content": "Sí. La cláusula décima del contrato establece una obligación de confidencialidad...",
  "session_id": 5,
  "message_id": 102
}
```

Forzando el área legal:

```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 5,
    "message": "¿Qué plazo tengo para reclamar?",
    "legal_area_override": "laboral"
  }'
```

> La generación con LLM puede tardar varios segundos. Configura un timeout de cliente holgado (30-60 s) y muestra un estado de carga en la UI.

---

## Flujo completo

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=abogado@estudio.cl&password=..." \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Crear sesión sobre el caso 1
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"matter_id": 1, "title": "Análisis contrato"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 3. Preguntar
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"session_id\": $SESSION, \"message\": \"Resume los riesgos del contrato\"}"

# 4. Recuperar el historial
curl "http://localhost:8000/api/v1/chat/sessions/$SESSION/messages" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Errores comunes

| Código | Endpoint | Causa | `detail` de ejemplo |
|---|---|---|---|
| `401` | todos | Token ausente, inválido o expirado | `"No se pudo validar las credenciales"` |
| `403` | todos | Usuario sin membresía de organización | `"Usuario sin organización asignada"` |
| `404` | `sessions`, `message` | Caso o sesión inexistente / de otro tenant | `"Sesión no encontrada"` |
| `422` | `message` | Mensaje vacío o superior al máximo; `title` > 200 caracteres | Detalle estructurado de pydantic |
| `429` | todos | Límite del plan superado | `"Rate limit exceeded"` |
| `500` | `message` | Fallo del proveedor LLM, API key ausente o timeout | `"Error al generar la respuesta"` |

---

## Rate limits

Sin decorador `@limiter.limit` específico. Aplica el límite por organización según plan (`free` 100/min, `basic` 500/min, `pro` 2000/min, `enterprise` sin límite).

`POST /message` es el endpoint más caro de la API en tiempo y coste por token. Aunque el rate limit HTTP lo permita, cada mensaje consume cuota del proveedor LLM.

Ver [rate limits globales](../../openapi.md#rate-limits).

---

## Notas de seguridad

- **Inyección de prompt**: `message` es texto libre que llega al LLM. Un usuario puede intentar redirigir el comportamiento del asistente. Nunca uses la salida del modelo para decidir autorización ni para construir consultas a la base de datos.
- **`legal_area_override`**: está acotado a 64 caracteres, pero sigue siendo entrada controlada por el usuario que influye en la selección de contexto. Trátalo como no confiable.
- **Contexto RAG y multi-tenant**: el contexto se construye a partir de los documentos del caso; el aislamiento por `organization_id` es lo que impide filtrar documentos de otro tenant hacia el prompt. Cualquier regresión en ese filtro es una fuga de datos, no sólo un bug de permisos.
- **Transferencia a terceros**: cada mensaje y su contexto se envían al proveedor configurado (`LLM_PROVIDER`). Esto puede incluir información amparada por el secreto profesional. Verifica que exista base contractual con el proveedor.
- **Persistencia del historial**: los mensajes se almacenan en `chat_messages` de forma indefinida. Define una política de retención acorde a la normativa aplicable.
- **Sin streaming**: la respuesta es completa y síncrona. No expongas este endpoint directamente a clientes no confiables sin un timeout y un límite de concurrencia.
