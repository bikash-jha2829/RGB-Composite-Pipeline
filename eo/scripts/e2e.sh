#!/usr/bin/env bash
set -euo pipefail

# Use env vars from Makefile; provide defaults just in case
LOG_DIR=${LOG_DIR:-logs}
MAX_TRIES=${MAX_TRIES:-3}
SLEEP=${SLEEP:-5}

mkdir -p "$LOG_DIR"

# 1) Start Prefect server (background)
echo "[1/5] Starting Prefect server…"
nohup prefect server start \
    > "$LOG_DIR/prefect_server.log" 2>&1 &
PREFECT_PID=$!
echo "    → PID $PREFECT_PID, logs → $LOG_DIR/prefect_server.log"

# 2) Wait for Prefect API
echo -n "[2/5] Waiting for Prefect API at ${PREFECT_API_URL}"
tries=1
until curl -sSf "${PREFECT_API_URL}" > /dev/null; do
  if [ "$tries" -ge "$MAX_TRIES" ]; then
    echo " ❌ after $tries attempts"
    exit 1
  fi
  echo -n " (retry $tries/$MAX_TRIES in ${SLEEP}s)"
  sleep "$SLEEP"
  tries=$((tries+1))
done
echo " ✅"

# 3) Launch Prefect flow (background)
echo "[3/5] Launching Prefect flow (eo_monthly_mosaic)…"
nohup poetry run python -m prefect_dag.eo_monthly_mosaic \
    > "$LOG_DIR/flow.log" 2>&1 &
FLOW_PID=$!
echo "    → PID $FLOW_PID, logs → $LOG_DIR/flow.log"

# 4) Free up the FastAPI port if already in use
echo "[4/5] Checking port ${FASTAPI_PORT} for existing process…"
if lsof -i tcp:"${FASTAPI_PORT}" -sTCP:LISTEN -t >/dev/null; then
  EXISTING=$(lsof -i tcp:"${FASTAPI_PORT}" -sTCP:LISTEN -t)
  echo "    → Port ${FASTAPI_PORT} in use by PID(s): ${EXISTING}. Killing…"
  kill -9 ${EXISTING}
  echo "    → Freed port ${FASTAPI_PORT}"
else
  echo "    → Port ${FASTAPI_PORT} is free"
fi

# 5) Launch FastAPI in the foreground
echo "[5/5] Starting FastAPI at http://${FASTAPI_HOST}:${FASTAPI_PORT}…"
echo "    + poetry run uvicorn api:app --host ${FASTAPI_HOST} --port ${FASTAPI_PORT} --reload"
exec poetry run uvicorn api:app \
    --host "${FASTAPI_HOST}" \
    --port "${FASTAPI_PORT}" \
    --reload
