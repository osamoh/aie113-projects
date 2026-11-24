#!/usr/bin/env bash
# Run one command with the secrets from configs/secrets.enc.env in ITS environment only.
# The values are decrypted in memory for that command and are never written to a file.
#
#   scripts/with_secrets.sh docker compose up --build -d
#   scripts/with_secrets.sh uvicorn stocks_service.api.app:create_app --factory
#   scripts/with_secrets.sh sh -c 'curl -s localhost:8000/v1/forecast -H "X-API-Key: $STOCKS_API_KEY" \
#       -H "content-type: application/json" -d "{\"ticker\": \"2222.SR\"}"'
set -euo pipefail
cd "$(dirname "$0")/.."
[ "$#" -gt 0 ] || { echo "Usage: scripts/with_secrets.sh <command> [arguments...]"; exit 2; }
export SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"
exec sops exec-env configs/secrets.enc.env "$(printf '%q ' "$@")"
