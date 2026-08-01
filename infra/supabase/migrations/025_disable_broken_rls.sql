-- Migration: 025_disable_broken_rls
-- Description: Deshabilitar RLS en tablas que tienen políticas rotas
-- Reason: RLS usa auth.uid() de Supabase Auth pero Lilian usa JWT propio
-- El aislamiento real está en la capa API con filtros organization_id
-- Date: 2026-07-31

-- Tablas con RLS rota (usan auth.uid() de Supabase Auth):
-- 1. deadline_alerts - policy referencia tabla inexistente "user_organizations"
-- 2. precedents - policy usa auth.uid() pero Lilian usa JWT propio

-- Deshabilitar RLS en estas tablas
-- El aislamiento real se hace en la capa API con organization_id filters

ALTER TABLE deadline_alerts DISABLE ROW LEVEL SECURITY;
ALTER TABLE precedents DISABLE ROW LEVEL SECURITY;

-- Verificar que RLS está deshabilitado
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
