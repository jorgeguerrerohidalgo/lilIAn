# Referencia de API por módulo

Documentación detallada de cada módulo de la API REST v1 de lilIAn: descripción funcional, esquemas de request/response, ejemplos `curl` completos, errores comunes, rate limits y notas de seguridad.

Para la visión general (autenticación, convenciones, catálogo completo de endpoints, códigos de error y versionado) ver [`docs/openapi.md`](../../openapi.md).

---

## Módulos

| Documento | Prefijo | Contenido |
|---|---|---|
| [auth.md](auth.md) | `/api/v1/auth` | Registro, login OAuth2, logout, perfil autenticado |
| [matters.md](matters.md) | `/api/v1/matters` | CRUD de casos legales y participantes |
| [clients.md](clients.md) | `/api/v1/clients` | CRUD de clientes de la organización |
| [documents.md](documents.md) | `/api/v1/documents` | Upload, procesamiento, análisis de riesgos y dashboard |
| [chat.md](chat.md) | `/api/v1/chat` | Sesiones y mensajes del asistente IA por caso |
| [analysis.md](analysis.md) | `/api/v1/analysis` | Informes de análisis legal y revisión de riesgos |
| [precedents.md](precedents.md) | `/api/v1/precedents` | Búsqueda, alta y analítica de precedentes judiciales |
| [search.md](search.md) | `/api/v1/search` | Búsqueda RAG sobre los documentos de un caso |
| [saas.md](saas.md) | `/api/v1/saas` | Planes, suscripción, métricas y eventos de uso |

Los módulos no cubiertos aquí (`/organizations`, `/lawyer`, `/templates`, `/doc-templates`, `/alerts`, `/admin`, `/legal-areas`, `/metrics`) están documentados en [`openapi.md`](../../openapi.md#módulos).

---

## Convenciones comunes

Aplican a todos los módulos salvo indicación explícita.

| Aspecto | Valor |
|---|---|
| Base URL (desarrollo) | `http://localhost:8000` |
| Prefijo | `/api/v1` |
| Autenticación | `Authorization: Bearer <access_token>` |
| Content-Type | `application/json` (excepto login: `x-www-form-urlencoded`; upload: `multipart/form-data`) |
| Fechas | ISO 8601 en UTC |
| Errores | `{ "detail": "Mensaje en español" }` (excepto `422`, con detalle de pydantic) |
| Aislamiento | Filtrado automático por `organization_id` del token |
| Acceso cross-tenant | `404`, no `403` |

### Obtener un token para los ejemplos

Todos los ejemplos `curl` asumen la variable `$TOKEN`:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=abogado@estudio.cl&password=TU_PASSWORD" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

## Documentación relacionada

| Documento | Contenido |
|---|---|
| [openapi.md](../../openapi.md) | Referencia completa de la API v1 |
| [env-vars.md](../../env-vars.md) | Variables de entorno de backend y frontend |
| [architecture.md](../../architecture.md) | Arquitectura del sistema |
| [schema.md](../../schema.md) | Esquema de base de datos |
| [rbac-matrix.md](../../rbac-matrix.md) | Matriz de roles y permisos |
| [SECRETS_MANAGEMENT.md](../../SECRETS_MANAGEMENT.md) | Gestión de secretos |

La especificación OpenAPI generada en vivo está disponible en `GET /docs` (Swagger UI), `GET /redoc` y `GET /openapi.json`.
