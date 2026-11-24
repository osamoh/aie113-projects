#!/usr/bin/env bash
# One-time set-up, on YOUR computer, of the encrypted secrets file.
#
#   brew install sops age        (macOS; on Linux use your package manager)
#   scripts/secrets_init.sh
#
# What it does, in order:
#   1. Makes your age key pair, unless you already have one. The PRIVATE half stays in
#      ~/.config/sops/age/keys.txt on this computer only and is never committed.
#   2. Writes .sops.yaml: "files matching configs/secrets.enc.env are encrypted for these
#      PUBLIC keys". Public keys are safe to commit; they can only lock, not unlock.
#   3. Makes a new random practice API key and encrypts it into configs/secrets.enc.env.
#      The plain value only ever passes through a pipe; it is never written to disk.
set -euo pipefail
cd "$(dirname "$0")/.."

SECRETS_FILE="configs/secrets.enc.env"
KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

for tool in sops age-keygen python3; do
  command -v "$tool" >/dev/null || { echo "Missing '$tool'. On a Mac: brew install sops age"; exit 1; }
done

# 1. The age key pair
if [ -f "$KEY_FILE" ]; then
  echo "Using your existing age key: $KEY_FILE"
else
  mkdir -p "$(dirname "$KEY_FILE")"
  (umask 077 && age-keygen -o "$KEY_FILE" >/dev/null 2>&1)
  echo "Made a new age key pair: $KEY_FILE (private: back it up, never commit it)"
fi
PUBLIC_KEY="$(age-keygen -y "$KEY_FILE")"
echo "Your public key: $PUBLIC_KEY"

# 2. .sops.yaml: who can unlock the secrets file
if [ ! -f .sops.yaml ]; then
  cat > .sops.yaml <<YAML
# Which files SOPS encrypts, and for whom. Only PUBLIC age keys belong here.
# To give someone access: add their public key below, then run
#   sops updatekeys configs/secrets.enc.env
creation_rules:
  - path_regex: configs/secrets\.enc\.env\$
    age: >-
      $PUBLIC_KEY
YAML
  echo "Wrote .sops.yaml"
elif ! grep -q "$PUBLIC_KEY" .sops.yaml; then
  echo "Your public key is not in .sops.yaml yet. Ask someone who can already decrypt to add"
  echo "it there and run: sops updatekeys $SECRETS_FILE"
  exit 1
fi

# 3. The encrypted secrets file
if [ -f "$SECRETS_FILE" ]; then
  echo "$SECRETS_FILE already exists; nothing was changed."
  echo "To replace the key (rotate it): sops $SECRETS_FILE"
  exit 0
fi
mkdir -p configs
python3 -c 'import secrets; print("STOCKS_API_KEY=" + secrets.token_urlsafe(32))' \
  | SOPS_AGE_KEY_FILE="$KEY_FILE" sops encrypt --filename-override "$SECRETS_FILE" \
      --input-type dotenv --output-type dotenv /dev/stdin > "$SECRETS_FILE"

echo
echo "Wrote $SECRETS_FILE. This is what git will store (the value is unreadable):"
head -n 1 "$SECRETS_FILE" | cut -c1-70
echo
echo "Next:"
echo "  git add .sops.yaml $SECRETS_FILE && git commit -m 'chore: encrypted API key'"
echo "  scripts/with_secrets.sh docker compose up --build -d"
