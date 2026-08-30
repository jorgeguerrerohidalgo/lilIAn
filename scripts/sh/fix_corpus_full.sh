#!/bin/bash
# Script unico de recuperacion completa del corpus legal chileno
# Ejecutar desde la raiz del proyecto:
#   cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
#   bash scripts/sh/fix_corpus_full.sh
#
# Pasos:
#   [1/5] DELETE chunks Tier 1 existentes
#   [2/5] Re-ingestar Tier 1 (parser que mantiene derogados)
#   [3/5] Reindexar embeddings (~30 min en background)
#   [4/5] Correr eval final (recall@10)
#   [5/5] Resumen del corpus

set -e

echo "=================================================="
echo "Recuperacion completa del corpus legal chileno"
echo "=================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$SCRIPT_DIR/apps/backend"
echo "Working dir: $SCRIPT_DIR"
echo "Backend dir:  $BACKEND_DIR"

# 1) DELETE chunks existentes para re-ingestar limpio
echo ""
echo "[1/5] Limpiando chunks existentes para re-ingest..."
.venv_test/bin/python -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
tier1 = ['172986','1984','207436','22740','176595','242302','21719','19628']
for lc in tier1:
    n = session.execute(text('DELETE FROM law_chunks WHERE law_code = :lc'), {'lc': lc}).rowcount
    print(f'  {lc}: borrados {n} chunks')
    session.execute(text('DELETE FROM norm_catalog WHERE bcn_id = :lc'), {'lc': lc})
session.execute(text('DELETE FROM law_chunk_versions WHERE norm_id NOT IN (SELECT id FROM norm_catalog)'))
session.commit()
session.close()
print('OK')
"

# 2) Re-ingestar Tier 1 completo con el parser arreglado
echo ""
echo "[2/5] Re-ingestando Tier 1 (~5-10 min)..."
.venv_test/bin/python -m scripts.ingest_bcn_corpus ingest-tier1 --no-embeddings

# 3) Reindexar embeddings
echo ""
echo "[3/5] Reindexando embeddings (~30 min en background)..."
nohup .venv_test/bin/python -m scripts.reindex_chunks > /tmp/reindex.log 2>&1 &
echo "PID: $!"

# 4) Run eval final
echo ""
echo "[4/5] Corriendo eval final..."
sleep 5
.venv_test/bin/python -m scripts.eval_law_retrieval

# 5) Resumen del corpus
echo ""
echo "[5/5] Resumen del corpus:"
.venv_test/bin/python -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
print(f'  Total chunks: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks\")).scalar()}')
print(f'  With embeddings: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks WHERE embedding_vec IS NOT NULL\")).scalar()}')
print(f'  Distinct law_codes: {session.execute(text(\"SELECT COUNT(DISTINCT law_code) FROM law_chunks\")).scalar()}')
session.close()
"
