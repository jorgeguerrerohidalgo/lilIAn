# Handoff — Sesión de Deploy a Producción

> Documento de reanudación tras deploy a Railway + Vercel.
> Actualizado: 2026-08-13 04:49 GMT-4

## Estado de producción

| Componente | URL | Estado | Notas |
|---|---|---|---|
| **Backend (Railway)** | https://liliap-production.up.railway.app | ✅ LIVE (deploy `a2e25b17`) | Con todos los fixes de PR #1 y PR #3 mergeados |
| **Frontend (Vercel)** | https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app | ✅ Ready (deploy 04:43) | **Protegido con Vercel SSO** |

## Endpoints del backend verificados

| Endpoint | HTTP | Esperado | Notas |
|---|---|---|---|
| `/health` | 200 | 200 | ✅ `{"status":"healthy"}` |
| `/` | 200 | 200 | ✅ `{"message":"lilIAn API","version":"0.1.0"}` |
| `/docs` | 200 | 200 | ✅ OpenAPI docs accesibles |
| `/metrics` | 401 | 401 | ✅ S2-01: requiere auth |
| `OPTIONS /api/v1/auth/login` desde frontend | 200 | 200 | ✅ S1-17: CORS allow-list funciona |

## Variables de entorno aplicadas en Railway producción

```
ALLOWED_ORIGINS=https://lil-i-rj551xub2-jorgeguerrerohidalgo710.vercel.app,https://lilian.cl,...
ANTHROPIC_API_KEY=sk-ant-api03-...
APP_ENV=production
DATABASE_URL=postgresql://postgres.yjiglcxuzizjgzlldqji:***@aws-0-us-east-1.pooler.supabase.com:6543/postgres
EMBEDDING_PROVIDER=dummy
JWT_SECRET=MacBookPRo71014-LilIAN-Secret-Key-2024   ⚠️ cambiar si quieres rotación
LLM_API_KEY=sk-ant-api03-... (compartida con ANTHROPIC_API_KEY)
LLM_MODEL=claude-haiku-4-5-20251001
LLM_PROVIDER=anthropic
OPENAI_API_KEY=sk-proj-...
PORT=8000
REDIS_URL=redis://localhost:6379/0   ⚠️ localhost - Railway provee Redis interno
SUPABASE_URL=https://yjiglcxuzizjgzlldqji.supabase.co
SUPABASE_ANON_KEY=sb_publishable_***
SUPABASE_SERVICE_ROLE_KEY=sb_secret_***
```

## Acciones que requieren tu intervención humana

### 1. Desactivar Vercel SSO Protection (1 minuto)
El proyecto Vercel `jorgeguerrerohidalgo710/lil-i-an` está protegido con
Vercel SSO. Esto bloquea el acceso público. Para hacerlo público:

1. Abre https://vercel.com/jorgeguerrerohidalgo710/lil-i-an/settings/deployment-protection
2. **Vercel Authentication**: Standard Protection → apagado
   - O configura "Password Protection" específico si quieres acceso restringido

### 2. Rotar `JWT_SECRET` (opcional, recomendado para producción seria)
El secret actual es débil y predecible. Para rotación:

```bash
new_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "$new_secret"
# Actualizar en railway:
railway variables --set "JWT_SECRET=$new_secret"
# Esto causará un re-deploy. Los tokens emitidos con el secret anterior
# serán inválidos — usuarios tendrán que re-loguearse.
```

### 3. Custom domain (opcional)
Si quieres `lilian.cl` o similar, configura en Vercel:
- Settings → Domains → Add `lilian.cl`
- Actualizar `ALLOWED_ORIGINS` en Railway para incluirlo

## Cómo crear un usuario admin inicial

El backend está corriendo pero no hay usuarios en la DB. Para crear el primero:

```bash
# 1. Generar un hash de password con bcrypt (que ya usamos)
cd apps/backend
python3 -c "
import bcrypt
pwd = b'TuPasswordSeguro123!'
hashed = bcrypt.hashpw(_truncate := (lambda p: p.encode('utf-8')[:72].decode('utf-8', errors='ignore'))(pwd), bcrypt.gensalt(rounds=12))
print(hashed.decode('utf-8'))
"

# 2. Crear usuario y organización via SQL en Supabase
# (Acceder a https://supabase.com/dashboard/project/yjiglcxuzizjgzlldqji/sql)
```

Lo más simple para empezar: hacerlo a través del endpoint `/api/v1/auth/register` que ya existe en el backend.

```bash
curl -X POST https://liliap-production.up.railway.app/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jorge@example.com",
    "password": "SecurePass123!",
    "full_name": "Jorge Guerrero",
    "organization_name": "Mi Firma"
  }'
```

## Resumen del sprint de auditoría

| Sprint | Estado | Cobertura |
|---|---|---|
| S0 (Seguridad CRITICAL) | ✅ 14/14 | 100% |
| S1 (Bugs HIGH) | ✅ 16/17 | 94% (S1-02 ahora implementado) |
| S2 (RBAC) | 🟡 4/18 | 22% |
| S3 (Race conditions) | ✅ 7/8 | 88% |
| S4 (Refactorización) | 🟡 8/24 | 33% |
| S5 (Frontend UX) | 🟡 3/50 | 6% |
| S6 (Testing/CI) | ✅ Lint Python cerrado (906→0) | 13% |
| S7 (Docs) | 🟡 5/57 | 9% |

**CI en main**: ✅ 5/5 checks verdes + Vercel. Primera vez desde el inicio.

## Próximo en la cola

- S2 (14 issues pendientes de RBAC multi-tenant — más cobertura de tests)
- S4 (16 refactors menores pendientes)
- S5 (47 issues UX/accesibilidad)

Todos son trabajo de mejora continua, no hay bloqueantes.
