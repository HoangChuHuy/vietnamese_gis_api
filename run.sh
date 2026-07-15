#!/usr/bin/env bash
# Chạy backend (FastAPI/uvicorn) và frontend (Vite) cùng lúc.
# Cách dùng:
#   ./run.sh                                   -> backend :8000, frontend :5173
#   HOST=0.0.0.0 PORT=9000 WEB_PORT=5174 ./run.sh   -> đổi host/port
# Ctrl+C sẽ dừng cả 2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONDA_ENV_PYTHON="/home/chuhuyhoang/miniconda3/envs/hoangenv/bin/python"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

if [ ! -f "$CONDA_ENV_PYTHON" ]; then
  echo "Không tìm thấy Python tại: $CONDA_ENV_PYTHON" >&2
  echo "Sửa biến CONDA_ENV_PYTHON trong run.sh cho đúng đường dẫn conda env của bạn." >&2
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "Không tìm thấy .env — copy .env.example thành .env và điền MONGO_URI trước khi chạy." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Không tìm thấy npm trong PATH — cài Node.js/npm trước khi chạy." >&2
  exit 1
fi

echo "==> Đồng bộ dependencies backend (requirements.txt)..."
"$CONDA_ENV_PYTHON" -m pip install -q -r requirements.txt

if [ ! -d "$SCRIPT_DIR/web/node_modules" ]; then
  echo "==> Cài dependencies frontend (npm install)..."
  (cd web && npm install)
fi

echo "==> Khởi động backend tại http://$HOST:$PORT (docs: http://$HOST:$PORT/docs)"
"$CONDA_ENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload &
BACKEND_PID=$!

cleanup() {
  echo "==> Dừng backend (pid $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Khởi động frontend tại http://localhost:$WEB_PORT"
(cd web && exec npm run dev -- --port "$WEB_PORT")
