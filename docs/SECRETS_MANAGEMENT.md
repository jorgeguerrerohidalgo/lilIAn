# 🔐 Secrets Management — lilIAn

> **Procedimiento obligatorio de manejo de secretos**
>
> Cualquier clave real (OpenAI, Anthropic, JWT, Supabase, etc.) NUNCA debe aparecer en el código fuente, en commits, ni en archivos `.env` commiteados.

---

## ⚠️ Estado actual (2026-08-06)

| Acción | Estado |
|--------|--------|
| `.env` listado en `.gitignore` | ✅ |
| `.env` no commiteado a git | ✅ Verificado con `git log --all -- .env` |
| `.env.example` solo placeholders | ✅ |
| Claves reales rotadas en proveedores | ⏳ **PENDIENTE — ACCIÓN MANUAL REQUERIDA** |

> 🚨 **ACCIÓN INMEDIATA:** Si tu copia local de `.env` contiene claves reales (como `sk-proj-…` de OpenAI o `sk-ant-…` de Anthropic), esas claves deben **rotarse** en sus respectivos paneles ANTES de continuar. Aunque `.env` no está en git, una `git add -f` accidental las filtraría.

---

## 📋 Procedimiento de rotación

### 1. Identificar claves expuestas

```bash
# Buscar claves reales en cualquier archivo
grep -rE "(sk-proj-|sk-ant-|eyJ[A-Za-z0-9_-]{20,}|postgres://[^:]+:[^@]+@|redis://[^:]+:[^@]+@)" \
  --include="*.env*" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" \
  apps/ docs/ 2>/dev/null
```

### 2. Rotar en cada proveedor

| Servicio | Acción | URL |
|----------|--------|-----|
| OpenAI | Crear nueva API key, eliminar la vieja | https://platform.openai.com/api-keys |
| Anthropic | Crear nuevo key, revocar el anterior | https://console.anthropic.com/settings/keys |
| Supabase | Regenerar service_role key | Project Settings → API |
| Railway | Variables de entorno del servicio | Service → Variables |
| Vercel | Project Settings → Environment Variables | https://vercel.com/dashboard |
| JWT_SECRET | Generar nuevo: `python -c "import secrets; print(secrets.token_urlsafe(32))"` | Local |

### 3. Actualizar variables de entorno

**Local** (`apps/backend/.env`, `apps/frontend/.env.local`):
```bash
# Generar JWT_SECRET fuerte
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Editar .env y reemplazar las claves
$EDITOR apps/backend/.env
```

**Producción** (Railway, Vercel):
- Actualizar cada variable en el dashboard
- Redeploy

### 4. Validar

```bash
# El startup debe pasar la validación de JWT_SECRET
cd apps/backend
python -c "from app.core.config import settings; print('OK:', len(settings.JWT_SECRET))"
# Debe imprimir >= 32

# Auditar git en busca de claves
git log --all -p | grep -E "sk-proj-|sk-ant-|JWT_SECRET=" | head
# Debe estar VACÍO
```

### 5. Prevenir re-exposición

```bash
# Instalar gitleaks localmente
brew install gitleaks  # o equivalente

# Escanear antes de cada commit
gitleaks detect --source . --verbose
```

---

## 🛡️ Política de secretos

### ✅ Permitido

- Variables de entorno vía `.env` (local) o panel del proveedor (producción).
- Referencia a env vars en código: `os.environ["OPENAI_API_KEY"]`.
- `JWT_SECRET` de al menos 32 caracteres aleatorios.
- Logging con `logger.debug()`, NUNCA `print()` que incluya el valor de la clave.

### ❌ Prohibido

- Hardcodear claves en código fuente.
- Commitear `.env` (ya está bloqueado por `.gitignore`).
- Loguear claves o sus prefijos en `print()` o `logger.info()`.
- Compartir `.env` por Slack, email, o similar.
- Usar la misma clave para dev y producción.
- Pasar `JWT_SECRET` como parámetro a funciones (debe leerse siempre de `settings`).

---

## 🔍 Auditoría automatizada

### Pre-commit hook (recomendado)

Agregar a `.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
# Detecta claves reales antes de cada commit
if grep -rE "(sk-proj-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{40,})" \
   --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" \
   --include="*.env*" . 2>/dev/null | grep -v node_modules | grep -v .venv; then
  echo "❌ COMMIT BLOCKED: secrets detected in source files"
  exit 1
fi
```

### CI gate (recomendado para Sprint 6)

```yaml
- name: gitleaks scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 📚 Referencias

- OWASP Top 10 — A02:2021 Cryptographic Failures
- OWASP Top 10 — A05:2021 Security Misconfiguration
- [Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- `docs/REMEDIATION_PLAN.md` — Issue S0-01

---

**Última actualización:** 2026-08-06 (Sprint 0)