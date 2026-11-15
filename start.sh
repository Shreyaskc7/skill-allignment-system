#!/usr/bin/env bash
# SkillAlign: one-step setup and start (Linux / macOS).
#   ./start.sh              set up whatever is missing, then start the API and the website
#   ./start.sh --check-only run every check but start nothing
# Safe to re-run; never deletes data; asks before migrating. Credentials come from .env (git-ignored).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"; FRONTEND="$ROOT/frontend"; ENV_FILE="$ROOT/.env"
CHECK_ONLY=0; [[ "${1:-}" == "--check-only" ]] && CHECK_ONLY=1

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
ok() { printf '    \033[32m%s\033[0m\n' "$1"; }
note() { printf '    \033[33m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m[STOPPED] %s\033[0m\n\n' "$1"; exit 1; }
hash_of() { [[ -f "$1" ]] && (sha256sum "$1" 2>/dev/null || shasum -a 256 "$1") | cut -d' ' -f1 || true; }

step "Checking tools"
PY=$(command -v python3 || command -v python || true); [[ -n "$PY" ]] || fail "Python 3.10+ not found."
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || fail "Python 3.10 or newer is required."
ok "Python $("$PY" -c 'import platform; print(platform.python_version())')"
command -v node >/dev/null || fail "Node.js 18+ not found."
[[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ]] || fail "Node.js 18 or newer is required."
ok "Node.js $(node --version)"

step "Checking .env (credentials)"
[[ -f "$ENV_FILE" ]] || { cp "$ROOT/.env.example" "$ENV_FILE"; note "Created .env from .env.example"; }
if grep -qE '^SECRET_KEY=\s*$' "$ENV_FILE"; then
  SECRET=$("$PY" -c 'import secrets; print(secrets.token_urlsafe(48))')
  "$PY" - "$ENV_FILE" "$SECRET" <<'PYEOF'
import re, sys
p, s = sys.argv[1], sys.argv[2]
t = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(re.sub(r"(?m)^SECRET_KEY=\s*$", "SECRET_KEY=" + s, t, count=1))
PYEOF
  ok "Generated a random SECRET_KEY in .env"
fi
grep -qE '^DATABASE_URL=.*YOUR_PASSWORD' "$ENV_FILE" && fail "Edit .env and replace YOUR_PASSWORD in DATABASE_URL, then run again."
ok ".env is filled in"
[[ -f "$FRONTEND/.env" ]] || cp "$FRONTEND/.env.example" "$FRONTEND/.env"

step "Preparing the backend"
VENV="$BACKEND/.venv"; VPY="$VENV/bin/python"
if ! { [[ -x "$VPY" ]] && "$VPY" -c 'import sys' 2>/dev/null; }; then
  [[ -d "$VENV" ]] && { mv "$VENV" "$VENV.broken-$(date +%Y%m%d%H%M%S)"; note "Existing .venv did not work here (moved aside)"; }
  "$PY" -m venv "$VENV"; ok "Created backend/.venv"
fi
REQ="$(hash_of "$BACKEND/requirements.txt")$(hash_of "$BACKEND/requirements-dev.txt")"
if [[ "$(cat "$VENV/.requirements.sha256" 2>/dev/null)" != "$REQ" ]]; then
  note "Installing backend packages..."
  "$VPY" -m pip install --disable-pip-version-check -q -r "$BACKEND/requirements.txt" -r "$BACKEND/requirements-dev.txt"
  echo "$REQ" > "$VENV/.requirements.sha256"; ok "Backend packages installed"
else ok "Backend packages up to date"; fi

step "Preparing the frontend"
LOCK="$(hash_of "$FRONTEND/package-lock.json")"
if [[ "$(cat "$FRONTEND/node_modules/.package-lock.sha256" 2>/dev/null)" != "$LOCK" ]]; then
  note "Installing frontend packages..."; (cd "$FRONTEND" && npm ci --no-audit --no-fund)
  echo "$LOCK" > "$FRONTEND/node_modules/.package-lock.sha256"; ok "Frontend packages installed"
else ok "Frontend packages up to date"; fi

step "Checking the database"
set +e; OUT=$(cd "$BACKEND" && "$VPY" "$ROOT/scripts/db_status.py" 2>&1); CODE=$?; set -e
if [[ $CODE -eq 2 ]]; then fail "Cannot connect to PostgreSQL: $(grep '^CONNECT fail' <<<"$OUT" | sed 's/^CONNECT fail //')"; fi
if [[ $CODE -eq 3 ]]; then
  note "Database needs migration ($(grep '^REV' <<<"$OUT"))."
  note "BACK UP FIRST:  pg_dump -U postgres -F c -f skillalign_backup.dump skill_alignment_db"
  [[ $CHECK_ONLY -eq 1 ]] && fail "Migration needed (run without --check-only to apply it)."
  read -r -p "    Have you backed up, and should the migration run now? [y/N] " A
  [[ "$A" =~ ^[Yy] ]] || fail "Migration skipped; the API will not start on an outdated schema."
  (cd "$BACKEND" && "$VENV/bin/alembic" upgrade head); ok "Database migrated"
  OUT=$(cd "$BACKEND" && "$VPY" "$ROOT/scripts/db_status.py" 2>&1)
fi
ok "Database schema is up to date"
if grep -q '^ADMINS 0' <<<"$OUT"; then
  note "No administrator account exists yet."
  if [[ $CHECK_ONLY -eq 0 ]]; then
    read -r -p "    Create one now? [y/N] " A
    if [[ "$A" =~ ^[Yy] ]]; then
      read -r -p "    Admin email: " EMAIL; read -r -p "    Admin full name: " NAME
      (cd "$BACKEND" && "$VPY" -m app.cli create-admin --email "$EMAIL" --name "$NAME")
    fi
  fi
fi
[[ $CHECK_ONLY -eq 1 ]] && { printf '\n\033[32mAll checks passed.\033[0m\n\n'; exit 0; }

step "Starting SkillAlign (Ctrl+C stops both)"
(cd "$BACKEND" && "$VPY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
API_PID=$!
(cd "$FRONTEND" && npm run dev) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null' INT TERM EXIT
ok "API: http://127.0.0.1:8000   Website: http://127.0.0.1:5173"
wait
