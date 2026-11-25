#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_ROOT="$DIR"

# Ensure directories exist
mkdir -p "$PROJECT_ROOT/data/blobs" "$PROJECT_ROOT/data/cache" "$PROJECT_ROOT/data/secrets"

# Ensure Ed25519 key exists
if [ ! -f "$PROJECT_ROOT/data/secrets/jwt_ed25519_private.pem" ]; then
  openssl genpkey -algorithm ED25519 -out "$PROJECT_ROOT/data/secrets/jwt_ed25519_private.pem"
fi

# Kill old tmux sessions or processes on 8080 / 5174
tmux kill-session -t sonavault-api 2>/dev/null || true
tmux kill-session -t sonavault-web 2>/dev/null || true
kill $(lsof -t -i:8080) 2>/dev/null || true
kill $(lsof -t -i:5174) 2>/dev/null || true
sleep 1

# Start API in persistent tmux session
tmux new-session -d -s sonavault-api \
  "cd '$PROJECT_ROOT/apps/api' && \
   SV_ENV=development \
   SV_PUBLIC_ORIGIN='http://localhost:5174' \
   SV_CORS_ORIGINS='http://localhost:5174,http://localhost:5173,http://127.0.0.1:5174,http://127.0.0.1:5173' \
   SV_DATABASE_URL='sqlite+aiosqlite:///${PROJECT_ROOT}/data/sonavault_dev.db' \
   SV_QDRANT_URL='http://localhost:6333' \
   SV_QUEUE_BACKEND='in-process' \
   SV_JWT_ED25519_PRIVATE_KEY_PATH='${PROJECT_ROOT}/data/secrets/jwt_ed25519_private.pem' \
   SV_JWT_ACCESS_TTL_MIN=60 \
   SV_JWT_REFRESH_TTL_DAYS=7 \
   SV_MASTER_KEK_B64='dGVzdF9tYXN0ZXJfa2VrX2Jhc2U2NF8zMmJ5dGVzISE=' \
   SV_BLIND_INDEX_KEY_B64='dGVzdF9ibGluZF9pbmRleF9iYXNlNjRfMzJieXRlcyE=' \
   SV_INTERNAL_SERVICE_TOKEN='dev-internal' \
   SV_WEBAUTHN_RP_ID='localhost' \
   SV_ENFORCE_MFA_TIER_MIN=99 \
   SV_ENFORCE_MFA_ALL=false \
   SV_SPEECH_SIDECAR_URL='http://localhost:18201' \
   SV_NLP_SIDECAR_URL='http://localhost:18202' \
   SV_VLLM_BASE_URL='http://localhost:18000' \
   SV_VLLM_MODEL_ID='/models/nvidia/Qwen3-30B-A3B-NVFP4' \
   SV_BLOB_ROOT='${PROJECT_ROOT}/data/blobs' \
   SV_MODEL_ROOT='${PROJECT_ROOT}/data/models' \
   SV_CACHE_ROOT='${PROJECT_ROOT}/data/cache' \
   PYTHONPATH='${PROJECT_ROOT}/apps/api/src' \
   '${PROJECT_ROOT}/apps/api/.venv/bin/uvicorn' sonavault.main:app --host 0.0.0.0 --port 8080"

# Start Frontend in persistent tmux session
tmux new-session -d -s sonavault-web \
  "cd '$PROJECT_ROOT/apps/web' && \
   VITE_API_PROXY_TARGET='http://localhost:8080' \
   /home/easemyai/.nvm/versions/node/v22.23.4/bin/npx vite --port 5174 --host 0.0.0.0"

echo "Waiting for services to become ready..."
for i in {1..20}; do
  if curl -s http://localhost:8080/openapi.json > /dev/null 2>&1 && curl -s http://localhost:5174/ > /dev/null 2>&1; then
    echo "=========================================================="
    echo " SonaVault Platform is LIVE in tmux sessions!"
    echo " Frontend Web UI : http://localhost:5174"
    echo " Backend REST API: http://localhost:8080"
    echo " Interactive Docs: http://localhost:8080/docs"
    echo " Default Admin   : operator@sonavault.dev"
    echo " Default Password: SonaVault2026!Admin"
    echo "=========================================================="
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for services. Check tmux with: tmux a -t sonavault-api or tmux a -t sonavault-web"
exit 1
