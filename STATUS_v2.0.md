# lilIAn - Estado del Proyecto v2.0

**Última actualización:** 2026-08-02

## Estado de Implementación

### ✅ Completado v2.0

| Feature | Status | Notas |
|---------|--------|-------|
| RBAC (7 roles) | ✅ | Matriz en `docs/rbac-matrix.md` |
| Aislamiento multi-tenant | ✅ | Filtros por `organization_id` |
| Sistema RAG híbrido | ✅ | Embedding + keyword + RRF |
| EvidenceBundle | ✅ | `apps/backend/app/services/evidence.py` |
| Workflow review | ✅ | Tabla `reviews` + endpoints |
| Gate de revisión | ✅ | `can_use_analysis_for_automated_decisions()` |
| Pipeline idempotente | ✅ | Hash + force flag |
| Storage abstracto | ✅ | Local o Supabase |
| Tests aislamiento | ✅ | 24 tests en `test_isolation.py` |
| Dataset golden | ✅ | 4 casos curados |
| Citaciones navegables | ✅ | `components/citation-link.tsx` |
| Documentación schema | ✅ | `docs/schema.md` |

### ⚠️ Pendiente de verificar en producción

| Componente | Status | Acción |
|------------|--------|--------|
| Migraciones Supabase | ✅ | Ejecutadas |
| Storage bucket | ❓ | ¿Configurado? |
| Deploy Vercel | ❓ | ¿Código actualizado? |
| Deploy Railway | ❓ | ¿Código actualizado? |

---

## Mejoras Pendientes

### Prioridad Media

1. **Tests E2E**
   - No hay tests end-to-end
   - Sugerencia: Playwright para flujos críticos (login, crear matter, subir documento)

2. **CI/CD Pipeline**
   - No hay pipeline de CI configurado
   - Sugerencia: GitHub Actions para lint, test, build

3. **Monitoring/Observabilidad**
   - Sin logs centralizados
   - Sin métricas de uso
   - Sin alerting

### Prioridad Baja

4. **Documentación API versionada**
   - OpenAPI generada pero no versionada
   - Sugerencia: OpenAPI 3.1 con versioning

5. **Rate limiting por tier**
   - Implementado pero no configurado
   - Depende de plan SaaS

6. **国际化 (i18n)**
   - UI solo en español
   -迟早 (futuro)

---

## Deployments

| Plataforma | URL | Estado |
|------------|-----|--------|
| Railway (Backend) | `liliap-production.up.railway.app` | ⚠️ Verificar v2.0 |
| Vercel (Frontend) | `lilian-n62leqj9z-jorgeguerrerohidalgo710.vercel.app` | ⚠️ Verificar v2.0 |
| Supabase | `yjiglcxuzizjgzlldqji.supabase.co` | ✅ |

---

## Commits v2.0

| Commit | Descripción |
|--------|-------------|
| `ebf0ef4` | feat(db): migraciones workflow |
| `e1d8399` | feat(v2.0): seguridad, RAG, workflow |
| `c930548` | fix(C-04): disable broken RLS |
| `4c414b5` | fix(C-01): secrets a env vars |
| `d38eaec` | fix(P0): aislamiento multi-tenant |

---

## Variables de Entorno v2.0

### Backend (Railway)
```bash
# Storage (nuevas)
STORAGE_BACKEND=local  # o supabase
STORAGE_PATH=/app/storage/documents
SUPABASE_STORAGE_BUCKET=documents

# Existentes
DATABASE_URL=...
JWT_SECRET=...
REDIS_URL=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_API_URL=https://liliap-production.up.railway.app
```

---

## Próximos Pasos

1. ✅ ~~Ejecutar migraciones Supabase~~
2. ⬜ Verificar deploys (Vercel/Railway)
3. ⬜ Configurar Supabase Storage (si se usa)
4. ⬜ Configurar CI/CD (opcional)
5. ⬜ Agregar tests E2E (opcional)
