# 🚀 Deployment Guide — lilIAn

> Guía paso a paso para desplegar lilIAn a producción.
> Última revisión: 2026-08-07

---

## 📋 Pre-requisitos

- Cuenta en [Railway](https://railway.app) (backend)
- Cuenta en [Vercel](https://vercel.com) (frontend)
- Cuenta en [Supabase](https://supabase.com) (PostgreSQL + Storage)
- Cuenta en [Upstash](https://upstash.com) o similar (Redis)
- API keys: OpenAI / Anthropic / MiniMax
- Dominio (opcional pero recomendado)

---

## 🔧 Paso 1: Preparar Supabase

1. Crear proyecto en [Supabase](https://supabase.com)
2. Copiar credenciales:
   - `SUPABASE_URL` (Project URL)
   - `SUPABASE_ANON_KEY` (anon public)
   - `SUPABASE_SERVICE_ROLE_KEY` (service_role)
3. Crear bucket de storage:
   - SQL Editor → ejecutar:
     ```sql
     INSERT INTO storage.buckets (id, name, public)
     VALUES ('documents', 'documents', false);
     ```
4. Ejecutar migrations (ver `migrations/`):
   ```bash
   # Con Supabase CLI
   supabase db push
   ```

---

## 🔴 Paso 2: Configurar Redis

1. Crear base de datos Redis en [Upstash](https://upstash.com) o [Railway](https://railway.app)
2. Copiar `REDIS_URL` (formato: `redis://default:PASSWORD@HOST:PORT`)

---

## 🐍 Paso 3: Desplegar Backend en Railway

### Opción A: Deploy automático desde GitHub

1. Crear proyecto en Railway → "Deploy from GitHub"
2. Seleccionar el repo `Jorge-Guerrero-Hidalgo/lilian`
3. Configurar:
   - **Root Directory**: dejar vacío (Railway detecta el Dockerfile raíz)
   - **Variables de entorno**: ver siguiente sección

### Opción B: Deploy con Railway CLI

```bash
railway login
railway init
railway up
```

### Variables de entorno en Railway

```bash
# App
APP_ENV=production
DEBUG=false
PORT=8000

# Database (Supabase)
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:5432/postgres

# Supabase
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Redis
REDIS_URL=redis://default:PASSWORD@HOST:PORT

# JWT (¡GENERAR NUEVO!)
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_ISSUER=lilian
JWT_AUDIENCE=lilian-api

# LLM
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
LLM_API_KEY=sk-ant-...
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=sk-proj-...

# CORS (CRÍTICO en producción)
ALLOWED_ORIGINS=https://lilian.vercel.app,https://lilian.cl

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_AUTH_PER_MINUTE=10

# Storage
STORAGE_BACKEND=local
STORAGE_PATH=/app/storage/documents
```

### Verificación post-deploy

```bash
# Healthcheck
curl https://lilian-api.railway.app/health
# Debe retornar {"status": "healthy"}

# Docs interactivos
# https://lilian-api.railway.app/docs
```

---

## 🎨 Paso 4: Desplegar Frontend en Vercel

### Deploy automático desde GitHub

1. Crear proyecto en Vercel → "Import Git Repository"
2. Seleccionar el repo
3. Configurar:
   - **Root Directory**: `apps/frontend`
   - **Framework Preset**: Next.js (auto-detectado)
   - **Build Command**: `next build`
   - **Output Directory**: `.next`

### Variables de entorno en Vercel

```bash
# API URL (URL pública del backend en Railway)
NEXT_PUBLIC_API_URL=https://lilian-api.railway.app

# (Opcional) Habilitar logs en dev
NEXT_PUBLIC_ENABLE_LOGS=true
```

### Verificación post-deploy

```bash
# Cargar la página
curl https://lilian.vercel.app

# Verificar que la cookie se setea en /login
curl -i -X POST https://lilian-api.railway.app/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=Test1234!Abcd" | grep -i set-cookie
```

---

## 🔐 Paso 5: Rotar Secretos Pre-Deploy

**CRÍTICO:** Antes de cada deploy, rotar las claves reales:

```bash
# 1. Generar JWT_SECRET fuerte
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Rotar API keys en cada proveedor:
# - OpenAI: https://platform.openai.com/api-keys
# - Anthropic: https://console.anthropic.com/settings/keys
# - Supabase: Project Settings → API

# 3. Actualizar variables en Railway y Vercel

# 4. Verificar que no hay secretos en el código
git log --all -p | grep -E "sk-proj-|sk-ant-|JWT_SECRET=" | head
# Debe estar VACÍO
```

Ver [`docs/SECRETS_MANAGEMENT.md`](docs/SECRETS_MANAGEMENT.md) para más detalles.

---

## 📊 Paso 6: Verificación Post-Deploy

### Checklist

- [ ] `GET /health` retorna 200 en Railway
- [ ] `GET /api/v1/auth/login` funciona
- [ ] `POST /api/v1/auth/register` crea usuario
- [ ] Frontend carga sin errores en Vercel
- [ ] Cookie `lilian_auth_token` se setea en login
- [ ] Middleware redirige a `/auth/login` si no hay cookie
- [ ] CORS permite solo orígenes configurados
- [ ] `/metrics` requiere auth
- [ ] `npm run build` en frontend pasa sin errores
- [ ] `pytest` en backend pasa sin errores

---

## 🐳 Docker Local (opcional)

```bash
# Build
docker build -t lilian-api .

# Run con .env
docker run -p 8000:8000 --env-file apps/backend/.env lilian-api

# Acceder a docs
open http://localhost:8000/docs
```

---

## 🔄 Rollback

Si un deploy falla:

1. **Railway**: Dashboard → Deployments → click en deployment anterior → "Redeploy"
2. **Vercel**: Dashboard → Deployments → click en deployment anterior → "Promote to Production"

---

## 📚 Referencias

- [`docs/architecture.md`](docs/architecture.md) — Arquitectura del sistema
- [`docs/SECRETS_MANAGEMENT.md`](docs/SECRETS_MANAGEMENT.md) — Manejo de secretos
- [`docs/REMEDIATION_PLAN.md`](docs/REMEDIATION_PLAN.md) — Plan de remediación
- [`STATUS_v2.1.md`](STATUS_v2.1.md) — Estado actual del proyecto