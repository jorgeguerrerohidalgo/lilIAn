#!/bin/bash

# ============================================
# GUÍA DE MIGRACIÓN PARA SUPABASE ONLINE - lilIAn
# ============================================
#
# Este script NO ejecuta nada automáticamente.
# Es una guía para aplicar las migraciones desde el
# dashboard web de Supabase o mediante la API.
#
# OPCIÓN 1: Desde el Dashboard de Supabase (RECOMENDADA)
# ---------------------------------------------------------------
# 1. Ve a https://supabase.com/dashboard
# 2. Selecciona tu proyecto
# 3. Menú lateral: SQL Editor
# 4. Click en "New Query"
# 5. Copia y pega el contenido de cada archivo SQL
#    en orden, de 001 a 015
# 6. Click "Run" para cada uno
#
# Archivos SQL en orden:
#   001_enable_extensions.sql
#   002_create_organizations.sql
#   003_create_users.sql
#   004_create_organization_members.sql
#   005_create_matters.sql
#   006_create_documents.sql
#   007_create_audit_logs.sql
#   008_create_pgvector.sql
#   009_create_document_chunks.sql
#   010_create_legal_sources.sql
#   011_create_analysis_reports.sql
#   012_create_risk_items.sql
#   013_create_chat_sessions.sql
#   014_create_templates.sql
#   015_create_subscriptions_and_usage.sql
#
# ============================================

echo ""
echo "============================================"
echo "GUÍA DE MIGRACIÓN - lilIAn para Supabase Online"
echo "============================================"
echo ""
echo "Ubicación de migraciones:"
echo "  lilian/infra/supabase/migrations/"
echo ""
echo "Orden de ejecución (001 a 015):"
echo ""
ls -1 infra/supabase/migrations/*.sql | xargs -I {} basename {}
echo ""
echo "============================================"
echo "PASOS EN SUPABASE DASHBOARD:"
echo "============================================"
echo ""
echo "1. Ve a https://supabase.com/dashboard"
echo "2. Selecciona tu proyecto"
echo "3. Menu lateral: SQL Editor"
echo "4. Click en 'New Query'"
echo "5. Copia el contenido del archivo 001_enable_extensions.sql"
echo "6. Click 'Run' (o Ctrl+Enter)"
echo "7. Repite para cada archivo en orden hasta 015"
echo ""
echo "NOTA: Si un archivo da error de tabla ya existente,"
echo "continua con el siguiente (es normal si se ejecuta dos veces)"
echo ""
