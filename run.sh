#!/usr/bin/env bash
# Chạy FastAPI (uvicorn) bằng môi trường conda local_env.
# Cách dùng:
#   ./run.sh              -> chạy dev server tại 127.0.0.1:8000 (auto-reload)
#   HOST=0.0.0.0 PORT=9000 ./run.sh   -> đổi host/port
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONDA_ENV_PYTHON="F:/miniconda3/envs/local_env/python.exe"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [ ! -f "$CONDA_ENV_PYTHON" ]; then
  echo "Không tìm thấy Python tại: $CONDA_ENV_PYTHON" >&2
  echo "Sửa biến CONDA_ENV_PYTHON trong run.sh cho đúng đường dẫn conda env của bạn." >&2
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "Không tìm thấy .env — copy .env.example thành .env và điền MONGO_URI trước khi chạy." >&2
  exit 1
fi

echo "==> Đồng bộ dependencies (requirements.txt)..."
"$CONDA_ENV_PYTHON" -m pip install -q -r requirements.txt

echo "==> Khởi động API tại http://$HOST:$PORT (docs: http://$HOST:$PORT/docs)"
exec "$CONDA_ENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
