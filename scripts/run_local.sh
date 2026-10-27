#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Separate local practice DB, never a silent fallback from a failed Supabase DB.
export DATABASE_URL=""
export LOCAL_SQLITE_PATH="$PWD/data/practice.sqlite3"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-local-preview-only}"
export PORT="${PORT:-5001}"
if [ -x .venv/bin/python ]; then
  task_python=.venv/bin/python
elif [ -x ../../Assignment-1/emotion_labeler/.venv/bin/python ]; then
  task_python=../../Assignment-1/emotion_labeler/.venv/bin/python
else
  task_python=python3
fi
"$task_python" -m flask --app app:create_app init-db
exec "$task_python" app.py
