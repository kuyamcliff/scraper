#!/usr/bin/env bash
# start.sh — fires up qbittorrent-nox + telegram bot together
set -e

SAVE_PATH="${SAVE_PATH:-/home/user/downloads}"
QBIT_PORT="${QBIT_PORT:-8080}"
QBIT_PASS="${QBIT_PASS:-adminadmin}"

mkdir -p "$SAVE_PATH"

# ── start qbittorrent-nox ─────────────────────────────────────────────────────
echo "[*] starting qbittorrent-nox on port $QBIT_PORT..."
qbittorrent-nox \
  --webui-port="$QBIT_PORT" \
  --save-path="$SAVE_PATH" &
QBIT_PID=$!
echo "[*] qbit PID: $QBIT_PID"

# wait for webui to be ready
for i in $(seq 1 20); do
  if curl -sf http://localhost:$QBIT_PORT > /dev/null 2>&1; then
    echo "[*] qbit webui ready"
    break
  fi
  sleep 1
done

# set password via API
curl -s -c /tmp/qbit_cookies.txt -X POST http://localhost:$QBIT_PORT/api/v2/auth/login \
  -d "username=admin&password=$(cat /tmp/qbit_tmppass.txt 2>/dev/null || echo adminadmin)" > /dev/null

# ── start telegram bot ────────────────────────────────────────────────────────
echo "[*] starting telegram bot..."
export QBIT_URL="http://localhost:$QBIT_PORT"
export QBIT_USER="admin"
export QBIT_PASS="$QBIT_PASS"
export SAVE_PATH="$SAVE_PATH"
export RD_API_KEY="${RD_API_KEY:-}"

python tgbot.py &
BOT_PID=$!
echo "[*] bot PID: $BOT_PID"

echo ""
echo "✅ all running"
echo "   qbit webui : http://localhost:$QBIT_PORT"
echo "   downloads  : $SAVE_PATH"
echo ""
echo "press Ctrl+C to stop both"

# kill both on exit
trap "kill $QBIT_PID $BOT_PID 2>/dev/null; exit" INT TERM
wait
