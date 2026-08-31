#!/bin/bash
# Script v4: re-ingest Tier 1 con idNormas correctos de BCN
# Ejecutar desde la raiz del proyecto:
#   cd /home/jorge-guerrero-hidalgo/Desarrollo/legal_lilIAn/lilian
#   bash scripts/sh/fix_corpus_v4.sh
#
# Cambios vs v3:
#   - Reemplaza el bcn_id 21719 por 1209272 (idNorma BCN real de la 21.719)
#   - Agrega 18046 (Ley 18.046) y 19496 (Ley 19.496) al Tier 1
#   - Re-borra todos los chunks Tier 1 para re-ingestar limpio
#   - Re-borra 21719 (legacy con idNorma incorrecto) explicitamente
#
# Pasos:
#   [1/5] DELETE chunks Tier 1 con idNormas antiguos
#   [2/5] Re-ingestar Tier 1 con idNormas correctos
#   [3/5] Reindexar embeddings (~30-40 min en background)
#   [4/5] Eval final
#   [5/5] Resumen del corpus
#
# Salida esperada: recall@10 >= 0.85 sobre golden-dataset-v2.json
# (que se debe actualizar con los idNorma BCN correctos).

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/apps/backend"
VENV_PY="$BACKEND_DIR/.venv_test/bin/python"
echo "Repo root:   $REPO_ROOT"
echo "Backend dir: $BACKEND_DIR"

# 1) DELETE chunks Tier 1
echo ""
echo "[1/5] Limpiando chunks Tier 1 con idNormas antiguos..."
( cd "$BACKEND_DIR" && "$VENV_PY" -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
old_codes = ['21719']
tier1 = ['172986','1984','207436','22740','176595','242302','1209272','19628','18046','19496']
for lc in old_codes:
    n = session.execute(text('DELETE FROM law_chunks WHERE law_code = :lc'), {'lc': lc}).rowcount
    print(f'  old {lc}: borrados {n} chunks')
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
echo "[2/5] Re-ingestando Tier 1 (~15-25 min)..."
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.ingest_bcn_corpus ingest-tier1 --no-embeddings )

# 3) Reindexar embeddings
echo ""
echo "[3/5] Reindexando embeddings (~30-40 min en background)..."
( cd "$BACKEND_DIR" && nohup "$VENV_PY" -m scripts.reindex_chunks > /tmp/reindex.log 2>&1 & )
echo "PID: $!"

# 4) Eval final
echo ""
echo "[4/5] Corriendo eval final..."
sleep 5
( cd "$BACKEND_DIR" && "$VENV_PY" -m scripts.eval_law_retrieval )

# 5) Resumen del corpus
echo ""
echo "[5/5] Resumen del corpus:"
( cd "$BACKEND_DIR" && "$VENV_PY" -c "
from app.core.database import SessionLocal
from sqlalchemy import text
session = SessionLocal()
print(f'  Total chunks: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks\")).scalar()}')
print(f'  With embeddings: {session.execute(text(\"SELECT COUNT(*) FROM law_chunks WHERE embedding_vec IS NOT NULL\")).scalar()}')
print(f'  Distinct law_codes: {session.execute(text(\"SELECT COUNT(DISTINCT law_code) FROM law_chunks\")).scalar()}')
session.close()
" )
