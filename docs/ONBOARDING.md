# Onboarding para nuevos desarrolladores

Guía de incorporación en tres días. El objetivo del día 3 es tener un PR abierto
y mergeado, por pequeño que sea.

Si algo de esta guía no funciona, no lo arregles en silencio: es un bug de
onboarding y corregirlo es una excelente primera contribución.

---

## Día 1: Setup y primera ejecución

Objetivo: la aplicación corriendo en local y un documento procesado de extremo a
extremo.

### 1.1 Requisitos previos

| Herramienta | Versión | Verificar |
|-------------|---------|-----------|
| Python | 3.12 (mínimo 3.11) | `python --version` |
| Node.js | 20.x | `node --version` |
| Docker + Compose | reciente | `docker compose version` |
| Git | cualquiera | `git --version` |

El backend usa `enum.StrEnum`, que requiere Python 3.11 o superior. Con 3.10 no
arranca.

### 1.2 Clonar y configurar

```bash
git clone https://github.com/Jorge-Guerrero-Hidalgo/lilian.git
cd lilian
cp .env.example .env
```

Edita `.env` con valores reales. Los mínimos para arrancar:

```bash
DATABASE_URL=postgresql://postgres:postgres@db:5432/postgres
REDIS_URL=redis://redis:6379/0
JWT_SECRET=<al menos 32 caracteres aleatorios>
LLM_PROVIDER=anthropic
LLM_API_KEY=<tu key>
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=<tu key>
STORAGE_PROVIDER=local
ALLOWED_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Genera el secreto JWT:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Nunca commitees `.env`. Está en `.gitignore` por una razón. Si crees haber
subido una key por accidente, dilo de inmediato: rotarla cuesta minutos,
ignorarlo puede costar mucho más.

### 1.3 Levantar el entorno

```bash
docker compose up -d
docker compose ps        # todos los servicios deben estar healthy
```

Comprueba que responde:

```bash
curl http://localhost:8000/health      # {"status": "healthy"}
open http://localhost:3000
```

Documentación interactiva de la API: `http://localhost:8000/docs`.

### 1.4 Alternativa sin Docker

Útil si vas a iterar mucho sobre el backend.

```bash
# Backend
cd apps/backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend, en otra terminal
cd apps/frontend
npm ci
npm run dev
```

Postgres y Redis siguen siendo necesarios: puedes levantarlos solos con
`docker compose up -d db redis`.

### 1.5 Primer flujo completo

Esta es la parte que de verdad valida el setup:

1. Regístrate en `http://localhost:3000` y crea una organización.
2. Crea un cliente.
3. Crea un caso asociado a ese cliente, tipo "revisión de contratos".
4. Sube un PDF o DOCX cualquiera al caso.
5. Observa cómo el estado del documento pasa a `processed`.
6. Lanza un análisis y revisa el resultado con sus citas.

Si el documento se queda en `processing`, el worker no está consumiendo la cola.
Mira `docker compose logs -f worker` y consulta
[TROUBLESHOOTING.md](TROUBLESHOOTING.md), sección Redis.

### 1.6 Correr los tests

```bash
cd apps/backend
pytest
```

Los tests usan SQLite en memoria, así que no necesitan Postgres. Si pasan en
verde, tu entorno de desarrollo está listo.

### Checklist día 1

- [ ] Backend responde en `/health`
- [ ] Frontend carga en `localhost:3000`
- [ ] Documento subido y procesado correctamente
- [ ] Análisis generado con citas
- [ ] `pytest` en verde

---

## Día 2: Arquitectura y código base

Objetivo: saber dónde vive cada cosa y por qué está donde está.

### 2.1 Lectura obligatoria

En este orden:

1. [architecture.md](architecture.md) - capas, flujos y decisiones de diseño
2. [schema.md](schema.md) - las 24 tablas y sus relaciones
3. [rbac-matrix.md](rbac-matrix.md) - los siete roles y sus permisos
4. [GLOSSARY.md](GLOSSARY.md) - vocabulario legal y técnico

No intentes memorizarlo. Basta con saber que existen y volver cuando haga falta.

### 2.2 Mapa mental del repositorio

```
lilian/
├── apps/
│   ├── backend/              FastAPI, Python 3.12
│   │   ├── app/
│   │   │   ├── api/endpoints/   Routers HTTP, uno por recurso
│   │   │   ├── api/deps/        Dependencias: auth, RBAC, tenant
│   │   │   ├── services/        Lógica de negocio
│   │   │   ├── models/          ORM SQLAlchemy
│   │   │   ├── schemas/         Contratos Pydantic de entrada y salida
│   │   │   └── core/            Config, seguridad, rate limit, métricas
│   │   ├── migrations/
│   │   └── tests/
│   └── frontend/             Next.js 14, App Router
│       ├── app/                 Rutas y páginas
│       ├── components/          Componentes React
│       └── lib/                 api.ts, hooks, utilidades
├── workers/document_processor/  Worker RQ
├── infra/supabase/migrations/   SQL de migraciones
├── docs/                        Esta documentación
└── tests/e2e/
```

### 2.3 Las cuatro capas del backend

El flujo de una petición atraviesa siempre las mismas capas, en orden:

**endpoint** define la ruta, valida entrada con Pydantic y no contiene lógica de
negocio. Si un endpoint supera unas 40 líneas, probablemente hay lógica que
debería estar en un servicio.

**deps** resuelve autenticación, organización y permisos. Es la capa que
garantiza el aislamiento multi-tenant. Toda ruta que toque datos de negocio
depende de ella.

**service** contiene la lógica real: análisis, RAG, chunking, generación de
documentos. Es la capa donde vive la complejidad y donde se concentra el valor
de los tests unitarios.

**model** es el ORM. Todas las tablas de negocio llevan `organization_id`.

Regla de oro: **nunca escribas una query sin filtrar por `organization_id`**.
Es la causa número uno de fugas de datos entre tenants. Cuando dudes, mira cómo
lo hace un endpoint existente que ya funcione.

### 2.4 Servicios clave

Merece la pena leer estos cuatro archivos con calma:

| Archivo | Qué hace |
|---------|----------|
| `services/analysis.py` | Análisis de documentos, validación de salida del LLM, detección de inyección |
| `services/rag.py` | Recuperación de contexto para el LLM |
| `services/chunker.py` | Fragmentación de texto con solapamiento y respeto de frases |
| `services/document_processor.py` | Pipeline de procesamiento del worker |

`analysis.py` es el corazón del producto. Presta atención a
`_validate_llm_output()`: ahí está la lógica que decide si un análisis puede
usarse automáticamente o exige revisión humana.

### 2.5 Frontend

- App Router de Next.js 14 con React Server Components.
- Toda llamada al backend pasa por `lib/api.ts`. No uses `fetch` suelto en
  componentes: rompe el manejo centralizado de errores y de credenciales.
- Autenticación por cookies httpOnly gestionadas por middleware.
- Para polling usa el hook `lib/hooks/use-poll.ts`, que limpia el intervalo al
  desmontar. No crees `setInterval` a mano.
- Accesibilidad: el proyecto invirtió un sprint completo en ella. Mantén
  `aria-label` en botones de solo icono, `role="alert"` en mensajes de error y
  `aria-hidden` en SVG decorativos.

### 2.6 Convenciones que se dan por supuestas

- **Python**: ruff con línea de 100 caracteres, target py312. Ejecuta
  `ruff check apps/backend` antes de commitear.
- **TypeScript**: `npm run lint` y `npx tsc --noEmit` deben pasar.
- **Commits**: formato convencional, `tipo(scope): descripción`. Los tipos en
  uso son `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.
  Ejemplo real del repositorio:
  `refactor(s4-07): process_document split into focused helpers (#24)`
- **Ramas**: `feature/<descripcion-corta>`.
- **Archivos**: preferimos muchos archivos pequeños. De 200 a 400 líneas es lo
  típico, 800 el máximo.

### Checklist día 2

- [ ] Los cuatro documentos de referencia leídos
- [ ] Sabes en qué capa vive cada tipo de lógica
- [ ] `analysis.py` leído entero al menos una vez
- [ ] Entiendes por qué toda query filtra por `organization_id`

---

## Día 3: Contribución y primer PR

Objetivo: un PR abierto, revisado y mergeado.

### 3.1 Elegir la primera tarea

Busca issues etiquetados `good first issue`. Si no hay ninguno, hay opciones
seguras y útiles:

- Corregir algo que te falló durante el setup del día 1
- Añadir un test unitario a un servicio con poca cobertura
- Mejorar un docstring que te costó entender

No empieces por refactorizar `analysis.py`.

### 3.2 Flujo de trabajo

```bash
git checkout main && git pull
git checkout -b feature/mi-primera-contribucion
```

Escribe el test primero cuando corrijas un bug: primero debe fallar,
reproduciendo el problema, y solo entonces implementas la corrección.

```bash
cd apps/backend
pytest tests/unit/test_mi_caso.py -v     # rojo
# implementar
pytest tests/unit/test_mi_caso.py -v     # verde
```

### 3.3 Antes de abrir el PR

```bash
# Backend
cd apps/backend
ruff check .
pytest

# Frontend
cd apps/frontend
npm run lint
npx tsc --noEmit
npm run build
```

CI ejecuta exactamente esto. Correrlo en local evita el ciclo de push y espera.

### 3.4 Abrir el PR

```bash
git add <archivos concretos>
git commit -m "fix(scope): descripción de qué y por qué"
git push -u origin feature/mi-primera-contribucion
gh pr create
```

Un PR revisable:

- Hace una sola cosa
- Explica el porqué, no solo el qué
- Incluye plan de pruebas
- Referencia el issue si existe

Añade siempre archivos por nombre. `git add .` acaba subiendo `.env` o
artefactos de build tarde o temprano.

### 3.5 Durante la revisión

Todo comentario debe terminar resuelto o respondido. Si no estás de acuerdo con
una sugerencia, explica por qué: la discusión técnica es parte del proceso, no
una fricción a evitar.

Cuando llegue tu turno de revisar a otros, aplica los criterios de la sección de
code review en las reglas del proyecto: bloquea por problemas críticos de
seguridad, avisa por bugs, comenta lo demás.

### Checklist día 3

- [ ] Rama creada desde `main` actualizado
- [ ] Test escrito antes de la corrección
- [ ] Linters y tests en verde en local
- [ ] PR abierto con descripción y plan de pruebas
- [ ] Comentarios de revisión atendidos

---

## Recursos

### Documentación interna

| Documento | Cuándo consultarlo |
|-----------|--------------------|
| [architecture.md](architecture.md) | Antes de tocar el flujo de análisis |
| [schema.md](schema.md) | Al añadir una tabla o columna |
| [rbac-matrix.md](rbac-matrix.md) | Al crear un endpoint nuevo |
| [openapi.md](openapi.md) | Al integrar desde el frontend |
| [TESTING.md](TESTING.md) | Al escribir tests |
| [PERFORMANCE.md](PERFORMANCE.md) | Al notar lentitud |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Cuando algo falla |
| [GLOSSARY.md](GLOSSARY.md) | Al leer un término desconocido |
| [FAQ.md](FAQ.md) | Preguntas de producto |
| [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) | Al manejar credenciales |
| [../DEPLOYMENT.md](../DEPLOYMENT.md) | Al desplegar |

### Documentación externa

- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- Next.js App Router: https://nextjs.org/docs/app
- pgvector: https://github.com/pgvector/pgvector
- RQ: https://python-rq.org
- Supabase: https://supabase.com/docs

### Canales

- **GitHub Issues**: bugs y propuestas de funcionalidad
- **GitHub Discussions**: preguntas abiertas y decisiones de diseño
- **Pull Requests**: revisión de código
- **Slack o el canal interno del equipo**: dudas rápidas del día a día

Para vulnerabilidades de seguridad, nunca uses un canal público: sigue el
proceso descrito en `SECURITY.md`.

### Preguntar bien

Antes de preguntar, dedica quince minutos a investigar. Al preguntar, incluye
qué intentabas hacer, qué esperabas, qué pasó y qué ya probaste. Una pregunta
bien planteada suele responderse sola a mitad de escribirla.

---

## Glosario rápido

Los términos que más aparecen en el código. El listado completo, con matices,
está en [GLOSSARY.md](GLOSSARY.md).

| Término | Significado en este código |
|---------|----------------------------|
| **Matter** | Caso legal. La unidad central de trabajo |
| **Client** | Cliente del estudio. Persona o empresa representada |
| **Organization** | Tenant. Todo dato de negocio pertenece a una |
| **Chunk** | Fragmento de documento indexado para búsqueda |
| **Embedding** | Vector que representa el significado de un chunk |
| **RAG** | Recuperar contexto relevante y pasárselo al LLM |
| **Citation** | Enlace de una afirmación de la IA a su fragmento origen |
| **Precedent** | Precedente judicial usado como contexto |
| **Legal area** | Área del derecho: labor, civil, consumer, family, commerce, penal, other |
| **Risk score** | Puntuación de riesgo de un hallazgo del análisis |
| **Deadline alert** | Alerta de un plazo procesal próximo |
| **requires_human_review** | Bandera que bloquea el uso automático de un análisis |
| **RBAC** | Control de acceso por rol |
| **Tenant isolation** | Garantía de que una organización no ve datos de otra |
