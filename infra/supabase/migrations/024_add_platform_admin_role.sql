-- Migration: 024_add_platform_admin_role
-- Description: Agrega rol PLATFORM_ADMIN para separar admin de plataforma de OWNER de organizacion
-- Date: 2026-07-31
-- Issue: C-02 (Separar admin de plataforma)

-- El enum MemberRole en Python ahora incluye PLATFORM_ADMIN
-- Este cambio es backward-compatible ya que solo agrega un nuevo valor

-- NOTA: Para aplicar este cambio en PostgreSQL, ejecutar:
-- ALTER TYPE memberrole ADD VALUE IF NOT EXISTS 'platform_admin';

-- Verificar que no hay ningun usuario con rol platform_admin aun
-- (Esto es esperado - el primer PLATFORM_ADMIN debe crearse manualmente)

-- SELECT * FROM organization_members WHERE role = 'platform_admin';

-- Para crear el primer PLATFORM_ADMIN (ejemplo):
-- INSERT INTO organization_members (organization_id, user_id, role, created_at)
-- VALUES (1, 1, 'platform_admin', NOW());
