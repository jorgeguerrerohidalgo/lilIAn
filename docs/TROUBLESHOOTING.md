# Troubleshooting

Guía de resolución de problemas para lilIAn. Cada sección lista el síntoma,
la causa más probable y la solución.

Antes de empezar: la mayoría de los problemas de arranque vienen de variables
de entorno faltantes o mal formadas. Revisa `.env.example` en la raíz y en
`apps/backend/` antes de investigar más a fondo.

---

## 1. Errores de instalación

### 1.1 Python

**Síntoma:** `SyntaxError` en `app/models/legal_area.py` o similar al importar.

El backend usa `enum.StrEnum`, disponible desde Python 3.11. El proyecto está
fijado en Python 3.12 (CI usa 3.11 como mínimo).

```bash
python --version   # debe ser >= 3.11
```

Solución: instalar Python 3.12 y recrear el virtualenv.

```bash
cd apps/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

**Síntoma:** `AttributeError: module 'bcrypt' has no attribute '__about__'`

Causa: `passlib<1.8` es incompatible con `bcrypt>=4.2`. El proyecto eliminó
`passlib` y llama a `bcrypt` directamente desde `app/core/security.py`.

Solución: desinstalar `passlib` del entorno y reinstalar dependencias.

```bash
pip uninstall -y passlib
pip install -r requirements.txt
```

---

**Síntoma:** `error: Microsoft Visual C++ 14.0 is required` (Windows) o fallo
compilando `psycopg2-binary` / `pymupdf`.

Causa: falta toolchain de compilación para wheels nativos.

Solución:

- Linux: `sudo apt-get install build-essential python3-dev libpq-dev`
- macOS: `xcode-select --install`
- Windows: usar WSL2 (recomendado) o instalar Build Tools for Visual Studio.

---

**Síntoma:** `ModuleNotFoundError: No module named 'app'` al correr pytest.

Causa: pytest ejecutado desde la raíz del repo en lugar de `apps/backend/`.

```bash
cd apps/backend && pytest
```

---

### 1.2 Node / Frontend

**Síntoma:** `npm ci` falla con `EUSAGE: package-lock.json out of sync`.

Causa: `package.json` cambió sin regenerar el lockfile.

```bash
cd apps/frontend
rm -rf node_modules
npm install          # regenera el lock
# o, si el lock es correcto:
npm ci
```

---

**Síntoma:** errores de tipos de React o `Cannot find module 'next'`.

Causa habitual: versión de Node incompatible. CI usa Node 20.

```bash
node --version   # debe ser 20.x
nvm use 20
```

---

**Síntoma:** `EACCES: permission denied` instalando paquetes globales.

Nunca uses `sudo npm install -g`. Usa `nvm` para gestionar Node en el
directorio del usuario.

---

### 1.3 Docker Compose

**Síntoma:** `docker compose up` levanta el backend pero muere de inmediato.

Revisa los logs del servicio concreto, no el output agregado:

```bash
docker compose logs -f backend
docker compose logs -f worker
```

Causas frecuentes:

- `JWT_SECRET` con menos de 32 caracteres: pydantic-settings rechaza el arranque.
- `DATABASE_URL` apuntando a `localhost` en lugar del nombre del servicio
  (`db` o el host de Supabase). Dentro de la red de Compose, `localhost` es el
  propio contenedor.
- `REDIS_URL` apuntando a `localhost` en lugar de `redis`.

---

## 2. Errores de base de datos

### 2.1 Conexión

**Síntoma:** `sqlalchemy.exc.OperationalError: could not connect to server`.

Checklist en orden:

1. ¿La URL tiene el formato correcto?
   `postgresql://usuario:password@host:5432/postgres`
2. ¿La contraseña contiene caracteres especiales (`@`, `#`, `/`)? Deben ir
   URL-encoded. `p@ss` se escribe `p%40ss`.
3. ¿El host de Supabase es alcanzable desde donde corres?
   `psql "$DATABASE_URL" -c 'select 1'`
4. ¿El proyecto Supabase está pausado? Los proyectos free se pausan tras
   inactividad; hay que reactivarlos desde el dashboard.

---

**Síntoma:** `FATAL: too many connections for role`.

Causa: el pool de SQLAlchemy más el pooler de Supabase superan el límite del
plan. Cada worker abre su propio pool.

Solución: usar el connection pooler de Supabase (puerto `6543`, modo
transaction) en lugar de la conexión directa (`5432`) para el backend, y
reducir `pool_size`.

---

**Síntoma:** `asyncpg.exceptions.InvalidPasswordError` pero la contraseña es
correcta.

Causa habitual: el `.env` tiene la contraseña entre comillas y se están
incluyendo literalmente. En archivos `.env` no se usan comillas salvo que
formen parte del valor.

---

### 2.2 Migraciones

**Síntoma:** `relation "matters" does not exist`.

Las migraciones no se aplicaron. Están en `infra/supabase/migrations/` y en
`apps/backend/migrations/`.

```bash
# Con Supabase CLI
supabase db push

# Con Alembic (backend)
cd apps/backend && alembic upgrade head
```

---

**Síntoma:** `type "vector" does not exist`.

Falta la extensión pgvector, que el sistema RAG necesita para
`document_chunks.embedding`.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

**Síntoma:** `alembic.util.exc.CommandError: Can't locate revision`.

Causa: la tabla `alembic_version` apunta a una revisión que ya no existe en el
repo (por ejemplo, tras un rebase que eliminó una migración).

Solución: identificar la revisión válida más cercana y sellar el estado.

```bash
alembic history
alembic stamp <revision_valida>
alembic upgrade head
```

No borres `alembic_version` en producción sin backup.

---

**Síntoma:** dos migraciones con el mismo `down_revision` (heads múltiples).

```bash
alembic heads          # muestra los heads en conflicto
alembic merge -m "merge heads" <head1> <head2>
```

---

## 3. Errores de Redis

Redis se usa para dos cosas: la cola de trabajos RQ del worker de documentos y
la blacklist de tokens JWT (`app/core/token_blacklist.py`).

**Síntoma:** los documentos se suben pero quedan en estado `processing` para
siempre.

Causa: el worker no está corriendo o no ve la misma cola.

```bash
# ¿está vivo el worker?
docker compose ps worker
docker compose logs -f worker

# ¿hay trabajos encolados?
redis-cli -u "$REDIS_URL" LLEN rq:queue:default
```

Si la cola crece y no baja, el worker no está consumiendo. Verifica que backend
y worker comparten exactamente el mismo `REDIS_URL`, incluyendo el número de
base (`/0`).

---

**Síntoma:** `redis.exceptions.ConnectionError: Error 111 connecting to redis:6379`.

- En local con Compose, el host es `redis`, no `localhost`.
- En Upstash u otros proveedores gestionados se requiere TLS: la URL empieza por
  `rediss://` (doble `s`), no `redis://`.

---

**Síntoma:** warnings de `RedisError` en los logs pero la app sigue funcionando.

Esto es esperado. La blacklist de tokens está diseñada como defensa en
profundidad: si Redis cae, el sistema hace fail-open para no bloquear a todos
los usuarios, y registra el error. Un logout no se propagará hasta que el token
expire por sí mismo. Restaura Redis cuanto antes.

---

**Síntoma:** `NOAUTH Authentication required`.

Falta la contraseña en la URL. Formato completo:
`redis://default:PASSWORD@HOST:PORT`.

---

## 4. Errores de storage (Supabase)

**Síntoma:** `400 Bucket not found` al subir un documento.

El bucket debe existir y ser privado.

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', false);
```

Verifica también que `SUPABASE_STORAGE_BUCKET` en el entorno coincide con el
nombre del bucket creado.

---

**Síntoma:** `403 new row violates row-level security policy`.

Causa: el backend está usando `SUPABASE_ANON_KEY` en lugar de
`SUPABASE_SERVICE_ROLE_KEY`.

La service role key es exclusiva del backend y nunca debe llegar al frontend ni
a variables `NEXT_PUBLIC_*`.

---

**Síntoma:** `413 Payload Too Large` al subir un PDF.

Supabase Storage tiene un límite por archivo según el plan, y el proxy delante
del backend puede tener otro. Si el documento es legítimamente grande, súbelo
por partes o eleva el límite en la configuración del proxy.

---

**Síntoma:** las URLs firmadas expiran demasiado rápido y el usuario ve un
documento roto al recargar.

Las URLs firmadas de Supabase son temporales por diseño. El frontend debe
pedirlas al backend en cada carga, no cachearlas en `localStorage`.

---

**Síntoma:** en desarrollo local no quieres depender de Supabase.

Usa el backend de filesystem:

```bash
STORAGE_PROVIDER=local
```

La capa `app/services/storage.py` abstrae ambos proveedores.

---

## 5. Errores de LLM

### 5.1 Rate limit

**Síntoma:** `429 Too Many Requests` del proveedor durante un análisis.

El servicio tiene reintentos con backoff en `app/services/retry_utils.py`, pero
si el rate limit persiste hay que reducir la concurrencia.

Acciones:

- Bajar el número de workers concurrentes que llaman al LLM.
- Revisar el tier de la cuenta del proveedor.
- Si es un pico puntual, reintentar el análisis desde la UI.

---

### 5.2 Timeout

**Síntoma:** el análisis falla tras varios minutos sin error claro.

Los documentos largos generan prompts grandes. Comprueba:

- Tamaño del documento: los contratos de más de 100 páginas deben analizarse por
  secciones.
- El timeout del cliente HTTP del backend (`httpx`).
- El timeout del proxy en Railway o Vercel, que puede cortar la petición antes
  que el propio backend.

El análisis correcto no debe hacerse síncrono en un request HTTP. Si el flujo
lo permite, encolar el trabajo y consultar el estado por polling.

---

### 5.3 Prompt injection detected

**Síntoma:** el análisis se completa pero aparece marcado con
`requires_human_review: true` y un warning de inyección.

Esto no es un bug. `_validate_llm_output()` en `app/services/analysis.py`
inspecciona la salida del LLM buscando patrones de inyección de prompt
(`ignore previous instructions`, `disregard the system prompt`, marcadores
`<|im_start|>`, etc.). Cuando detecta uno:

1. No descarta el resultado.
2. Marca `requires_human_review = true`.
3. Añade el motivo a `warnings`.

Consecuencia funcional: el análisis no puede usarse para decisiones automáticas
hasta que un humano lo apruebe en el workflow de revisión.

Qué hacer: revisar el documento origen. Un contrato real puede contener texto
que coincide con los patrones por casualidad, pero también puede ser un
documento manipulado deliberadamente. Aprobar solo tras leerlo.

---

### 5.4 Salida malformada

**Síntoma:** warnings sobre tamaño o profundidad de la respuesta.

La validación aplica límites de forma: máximo 8000 caracteres por campo de
texto, máximo 200 elementos por lista y profundidad máxima de 8 niveles. Una
respuesta que los excede se trunca o se marca. Suele indicar que el prompt
necesita más restricciones, no que el documento sea inválido.

---

### 5.5 API key

**Síntoma:** `401 Unauthorized` del proveedor de LLM.

- `LLM_API_KEY` y `EMBEDDING_API_KEY` son variables distintas. Es habitual
  configurar solo la primera y que fallen los embeddings.
- El prefijo debe coincidir con el proveedor: `sk-ant-` para Anthropic,
  `sk-proj-` o `sk-` para OpenAI.
- `LLM_PROVIDER` debe coincidir con la key. Una key de OpenAI con
  `LLM_PROVIDER=anthropic` da 401.

---

## 6. Errores de frontend

### 6.1 Build

**Síntoma:** `Type error: ...` durante `next build` pero `next dev` funciona.

`next dev` no hace type-check completo. El build sí. Reproduce el fallo antes de
pushear:

```bash
cd apps/frontend
npx tsc --noEmit
npm run build
```

---

**Síntoma:** `Module not found: Can't resolve '@/components/...'`.

El alias `@/` se resuelve vía `tsconfig.json` (`paths`). Si el import falla solo
en CI y no en local, casi siempre es una diferencia de mayúsculas en el nombre
del archivo: macOS es case-insensitive, Linux no. Verifica que el nombre del
archivo coincide exactamente con el import.

---

### 6.2 Runtime

**Síntoma:** `TypeError: Cannot read properties of undefined`.

Causa habitual: la respuesta del backend no trae el campo esperado porque el
usuario no tiene permiso sobre ese recurso y el endpoint devuelve una versión
reducida. Verifica la respuesta real en la pestaña Network antes de asumir que
el backend está roto.

---

**Síntoma:** `CORS policy: No 'Access-Control-Allow-Origin' header`.

`ALLOWED_ORIGINS` en el backend debe incluir el origen exacto del frontend, con
protocolo y sin barra final:

```bash
ALLOWED_ORIGINS=https://lilian.vercel.app,http://localhost:3000
```

El wildcard `*` está bloqueado en producción de forma deliberada (S1-17): es
incompatible con credenciales en cookies.

---

**Síntoma:** intervalos que siguen corriendo tras salir de la página, o
peticiones que se acumulan.

Usa el hook `usePoll` de `apps/frontend/lib/hooks/use-poll.ts`, que limpia el
intervalo en el unmount. No crees `setInterval` dentro de handlers de eventos.

---

### 6.3 Hydration

**Síntoma:** `Error: Text content does not match server-rendered HTML`.

Causas habituales, en orden de frecuencia:

1. Renderizar fechas con `toLocaleString()` sin fijar zona horaria ni locale.
   El servidor y el navegador difieren.
2. Leer `window`, `localStorage` o `document` durante el render en lugar de
   dentro de `useEffect`.
3. Usar `Math.random()` o `Date.now()` en el render.
4. HTML inválido, por ejemplo un `<div>` dentro de un `<p>`. El navegador lo
   reestructura y el árbol deja de coincidir.

Patrón seguro para contenido que solo existe en el cliente:

```tsx
const [mounted, setMounted] = useState(false);
useEffect(() => setMounted(true), []);
if (!mounted) return null;
```

---

**Síntoma:** cookies de auth no llegan al backend.

Las cookies son httpOnly. Comprueba que las peticiones se hacen con
`withCredentials` y que el dominio del backend permite el origen del frontend.
En cross-site se requiere `SameSite=None; Secure`, lo que obliga a HTTPS en
ambos extremos.

---

## 7. Errores de deploy

### 7.1 Vercel (frontend)

**Síntoma:** el build falla en Vercel pero funciona en local.

- Root Directory debe ser `apps/frontend`, no la raíz del repo.
- Las variables `NEXT_PUBLIC_*` se inyectan en build time. Cambiar una exige
  redeploy, no basta con reiniciar.
- Vercel corre `npm ci`: si `package-lock.json` no está commiteado o está
  desincronizado, el build falla.

---

**Síntoma:** el frontend carga pero todas las llamadas a la API dan 404 o
`ERR_CONNECTION_REFUSED`.

`NEXT_PUBLIC_API_URL` apunta a `localhost`. En producción debe ser la URL
pública de Railway.

---

### 7.2 Railway (backend)

**Síntoma:** el deploy queda en crash loop.

```bash
railway logs
```

Causas frecuentes:

- El servicio no escucha en `$PORT`. Railway asigna el puerto por variable de
  entorno; hardcodear 8000 provoca health check fallido.
- Falta una variable requerida y pydantic-settings aborta el arranque. El error
  aparece en las primeras líneas del log.
- `JWT_SECRET` con menos de 32 caracteres.

---

**Síntoma:** health check falla aunque la app arranca.

El endpoint es `GET /health` y devuelve `{"status": "healthy"}`. Verifica que la
ruta configurada en Railway coincide y que no está detrás de auth.

---

**Síntoma:** el backend funciona pero los documentos nunca se procesan en
producción.

El worker es un servicio separado. Desplegar solo el backend deja la cola sin
consumidor. Debe existir un servicio adicional ejecutando el worker de
`workers/document_processor/`.

---

### 7.3 Migraciones en deploy

No ejecutes migraciones automáticamente en el arranque de cada réplica: dos
réplicas arrancando a la vez pueden correr la misma migración en paralelo.
Ejecútalas como paso previo y explícito del deploy.

---

## 8. Cómo obtener logs útiles

### Local (Docker Compose)

```bash
docker compose logs -f backend       # un servicio
docker compose logs --tail=200 worker
docker compose logs -f               # todo
```

### Backend en Railway

```bash
railway logs --service backend
railway logs --service worker
```

### Frontend en Vercel

Dashboard del proyecto, pestaña Logs. Separa Build Logs (fallos de compilación)
de Runtime Logs (errores de servidor en runtime).

### Base de datos

Dashboard de Supabase, sección Logs, filtro por Postgres. Útil para detectar
queries lentas y errores de RLS que la app reporta solo como 403.

### Redis

```bash
redis-cli -u "$REDIS_URL" INFO clients
redis-cli -u "$REDIS_URL" LLEN rq:queue:default
redis-cli -u "$REDIS_URL" MONITOR   # solo en desarrollo, es costoso
```

### Nivel de log

En desarrollo puedes elevar el detalle:

```bash
APP_ENV=development
DEBUG=true
```

`DEBUG=true` nunca debe activarse en producción: expone trazas completas.

### Qué mirar antes de escalar el problema

1. La primera excepción del log, no la última. Los errores en cascada ocultan
   la causa.
2. El `request_id` o correlativo si aparece, para seguir una petición completa.
3. Los timestamps: un fallo que empieza exactamente a la hora de un deploy
   apunta al deploy.

Nunca pegues logs sin revisarlos: pueden contener tokens, emails de clientes o
fragmentos de documentos legales. Anonimiza antes de compartir.

---

## 9. Cómo reportar un bug efectivamente

Un buen reporte ahorra días. Incluye siempre:

**1. Título específico.** Malo: "no funciona el análisis". Bueno: "el análisis
de contratos laborales falla con 504 en documentos de más de 50 páginas".

**2. Entorno.**

- Rama y commit: `git rev-parse --short HEAD`
- Local con Compose, staging o producción
- Versiones: `python --version`, `node --version`

**3. Pasos de reproducción numerados.** Desde un estado conocido. Si no es
reproducible de forma fiable, indícalo y di cuántas veces de cuántas ocurre.

**4. Resultado esperado vs resultado real.** Separados y explícitos.

**5. Evidencia.**

- Traceback completo del backend, no solo la última línea
- Consola del navegador y pestaña Network para bugs de frontend
- IDs relevantes (`matter_id`, `document_id`), nunca contenido del documento

**6. Alcance.** ¿Afecta a un usuario o a todos? ¿A una organización o a varias?
¿Empezó tras un deploy concreto?

**7. Workaround.** Si encontraste una forma de evitarlo, documéntala: puede
desbloquear a otros mientras se corrige.

### Qué no incluir nunca

- Contenido de documentos legales de clientes
- Tokens, API keys, cookies de sesión, `DATABASE_URL` completa
- Datos personales identificables

Si el bug tiene implicaciones de seguridad, no abras un issue público. Sigue el
proceso de `SECURITY.md`.

### Plantilla mínima

~~~markdown
## Resumen
[una frase]

## Entorno
- Rama/commit:
- Entorno: local | staging | producción

## Pasos
1.
2.
3.

## Esperado

## Real

## Logs
```
[traceback anonimizado]
```

## Alcance
[un usuario | una organización | todos]
~~~

---

## Ver también

- [DEPLOYMENT.md](../DEPLOYMENT.md) - guía de despliegue completa
- [architecture.md](architecture.md) - arquitectura y flujos
- [FAQ.md](FAQ.md) - preguntas frecuentes de producto
- [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md) - gestión de secretos
