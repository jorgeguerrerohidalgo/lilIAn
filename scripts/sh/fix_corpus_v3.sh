#!/bin/bash
# Script v3: re-ingest + reindex + eval después de la migración VARCHAR(255)
# Ejecutar desde la raiz del proyecto:
#   cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
#   bash scripts/sh/fix_corpus_v3.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/apps/backend"
VENV_PY="$BACKEND_DIR/.venv_test/bin/python"
echo "Repo root:   $REPO_ROOT"
echo "Backend dir: $BACKEND_DIR"

# 1) DELETE chunks restantes de Tier 1 (que se ingesaron truncados antes de la migración)
echo ""
echo "[1/5] Limpiando chunks Tier 1 que se ingesaron con VARCHAR(64)..."
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

# 2) Re-ingestar Tier 1 SIN embeddings (ahorra tiempo en este paso)
echo ""
echo "[2/5] Re-ingestando Tier 1 (~10-15 min)..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest-tier1 --no-embeddings )

# 3) Re-ingestar Ley 18.046 y 19.496 explícitamente
echo ""
echo "[3/5] Re-ingestando Ley 18.046 y 19.496..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest --bcn-id=18046 --legal-area=comercial --no-embeddings )
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest --bcn-id=19496 --legal-area=consumidor --no-embeddings )

# 4) Reindexar embeddings (~25 min en background)
echo ""
echo "[4/5] Reindexando embeddings (~25 min en background)..."
( cd "$BACKEND_DIR" && nohup "$VENV_PY" -m scripts.reindex_chunks > /tmp/reindex.log 2>&1 & )
echo "PID: $!"

# 5) Eval final
echo ""
echo "[5/5] Corriendo eval final..."
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
