#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PORT="${SERVER_PORT:-8888}"
SERVER_IP="${SERVER_IP:-127.0.0.1}"
PYTHON_EXE="${PYTHON_EXE:-python3}"
ACTIVE_AI_MODULE="${ACTIVE_AI_MODULE:-PyAPI.AI}"
DUMMY_AI_MODULE="${DUMMY_AI_MODULE:-PyAPI.IdleAI}"
PY_FLAGS="${PY_FLAGS:--d -o}"
START_UI="${START_UI:-0}"

PY_ROOT="$ROOT/CAPI/python"
SERVER_PROJ="$ROOT/logic/Server/Server.csproj"
UI_PROJ="$ROOT/interface/AvaloniaUI/THUAI9_Avalonia.csproj"
LOG_DIR="$ROOT/logs/linux_python_1team"

mkdir -p "$LOG_DIR"

echo "[THUAI9] Linux Python 1-team launcher"
echo "[THUAI9] Active AI: $ACTIVE_AI_MODULE"
echo "[THUAI9] Dummy AI:  $DUMMY_AI_MODULE"
echo "[THUAI9] Logs:      $LOG_DIR"

command -v dotnet >/dev/null 2>&1 || {
    echo "[ERROR] dotnet not found." >&2
    exit 1
}

command -v "$PYTHON_EXE" >/dev/null 2>&1 || {
    echo "[ERROR] Python not found: $PYTHON_EXE" >&2
    exit 1
}

echo "[THUAI9] Building server..."
dotnet build "$SERVER_PROJ"

if [ "$START_UI" = "1" ]; then
    echo "[THUAI9] Building UI..."
    dotnet build "$UI_PROJ"
fi

echo "[THUAI9] Generating Python proto files..."
(
    cd "$PY_ROOT"
    "$PYTHON_EXE" -m pip install -r requirements.txt
    bash generate_proto.sh
)

if [ "$START_UI" = "1" ]; then
    echo "[THUAI9] Starting UI..."
    (
        cd "$ROOT/interface/AvaloniaUI"
        dotnet run --no-build
    ) >"$LOG_DIR/ui.log" 2>&1 &
    echo $! >"$LOG_DIR/ui.pid"
fi

echo "[THUAI9] Starting server on $SERVER_IP:$SERVER_PORT..."
(
    cd "$ROOT/logic/Server"
    dotnet run --no-build -- --port "$SERVER_PORT" --teamCount 2
) >"$LOG_DIR/server.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" >"$LOG_DIR/server.pid"

echo "[THUAI9] Waiting for server..."
"$PYTHON_EXE" - <<PY
import socket
import sys
import time

deadline = time.time() + 120
while time.time() < deadline:
    try:
        with socket.create_connection(("$SERVER_IP", int("$SERVER_PORT")), timeout=1):
            sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
PY

export PYTHONPATH="$PY_ROOT:$PY_ROOT/proto:${PYTHONPATH:-}"

echo "[THUAI9] Starting team clients..."
(
    cd "$PY_ROOT"
    "$PYTHON_EXE" -m PyAPI.main \
        -t 1 -p 0 -I "$SERVER_IP" -P "$SERVER_PORT" \
        --aiModule "$ACTIVE_AI_MODULE" $PY_FLAGS
) >"$LOG_DIR/team1-0.log" 2>&1 &
echo $! >"$LOG_DIR/team1-0.pid"

(
    cd "$PY_ROOT"
    "$PYTHON_EXE" -m PyAPI.main \
        -t 2 -p 0 -I "$SERVER_IP" -P "$SERVER_PORT" \
        --aiModule "$DUMMY_AI_MODULE" $PY_FLAGS
) >"$LOG_DIR/team2-0.log" 2>&1 &
echo $! >"$LOG_DIR/team2-0.pid"

echo "[THUAI9] Launched."
echo "[THUAI9] Character clients will start automatically after BuildCharacter succeeds."
echo "[THUAI9] Tail logs with: tail -f \"$LOG_DIR/server.log\" \"$LOG_DIR/team1-0.log\""
echo "[THUAI9] Stop later with: kill \$(cat \"$LOG_DIR\"/*.pid)"
