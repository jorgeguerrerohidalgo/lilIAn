#!/bin/bash
# Script de recuperacion completa del corpus legal chileno v2
# Ejecutar desde la raiz del proyecto:
#   cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
#   bash scripts/sh/fix_corpus_full.sh
#
# Pasos:
#   [1/6] DELETE chunks Tier 1 existentes
#   [2/6] Re-ingestar Tier 1 (parser mantiene derogados)
#   [3/6] Re-ingestar Ley 18.046 (Sociedad Anónima)
#   [4/6] Re-ingestar Ley 19.496 (Consumidor)
#   [5/6] Reindexar embeddings (~30 min en background)
#   [6/6] Correr eval final

set -e

echo "=================================================="
echo "Recuperacion completa del corpus legal chileno v2"
echo "=================================================="

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/apps/backend"
VENV_PY="$BACKEND_DIR/.venv_test/bin/python"
echo "Repo root:   $REPO_ROOT"
echo "Backend dir: $BACKEND_DIR"

# 1) DELETE chunks Tier 1 existentes para re-ingestar limpio
echo ""
echo "[1/6] Limpiando chunks existentes para re-ingest..."
( cd "$BACKEND_DIR" && "$VENV_PY" -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
tier1 = ['172986','1984','207436','22740','176595','242302','21719','19628','18046','19496']
for lc in tier1:
    n = session.execute(text('DELETE FROM law_chunks WHERE law_code = :lc'), {'lc': lc}).rowcount
    print(f'  {lc}: borrados {n} chunks')
    session.execute(text('DELETE FROM norm_catalog WHERE bcn_id = :lc'), {'lc': lc})
session.execute(text('DELETE FROM law_chunk_versions WHERE norm_id NOT IN (SELECT id FROM norm_catalog)'))
session.commit()
session.close()
print('OK')
" )

# 2) Re-ingestar Tier 1
echo ""
echo "[2/6] Re-ingestando Tier 1 (~10-15 min)..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest-tier1 --no-embeddings )

# 3) Re-ingestar Ley 18.046 (Sociedad Anónima) - idNorma segun BCN
echo ""
echo "[3/6] Re-ingestando Ley 18.046 (Sociedad Anónima)..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest --bcn-id=18046 --legal-area=comercial --no-embeddings )

# 4) Re-ingestar Ley 19.496 (Consumidor)
echo ""
echo "[4/6] Re-ingestando Ley 19.496 (Consumidor)..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest --bcn-id=19496 --legal-area=consumidor --no-embeddings )

# 5) Reindexar embeddings
echo ""
echo "[5/6] Reindexando embeddings (~30-40 min en background)..."
( cd "$BACKEND_DIR" && nohup "$VENV_PY" -m scripts.reindex_chunks > /tmp/reindex.log 2>&1 & )
echo "PID: $!"

# 6) Run eval final
echo ""
echo "[6/6] Corriendo eval final..."
sleep 5
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.eval_law_retrieval )

echo ""
echo "Resumen del corpus:"
( cd "$BACKEND_DIR" && "$VENV_PY" -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
print(f'  Total chunks: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks\")).scalar()}')
print(f'  With embeddings: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks WHERE embedding_vec IS NOT NULL\")).scalar()}')
print(f'  Distinct law_codes: {session.execute(text(\"SELECT COUNT(DISTINCT law_code) FROM law_chunks\")).scalar()}')
session.close()
" )
