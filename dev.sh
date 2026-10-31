#!/usr/bin/env bash
# Starts everything on this machine. Logs go to logs/. Stop with ./dev.sh stop
set -u
cd "$(dirname "$0")"
mkdir -p logs
SERVICES="ingest edge sequencer reasoner gateway"

stop_all() {
  for name in $SERVICES web; do
    if [ -f "logs/$name.pid" ]; then
      kill "$(cat "logs/$name.pid")" 2>/dev/null
      rm -f "logs/$name.pid"
    fi
  done
  echo "stopped"
}

if [ "${1:-}" = "stop" ]; then
  stop_all
  exit 0
fi

stop_all >/dev/null
docker compose up -d kafka
echo "waiting for Kafka"
for _ in $(seq 1 30); do
  uv run python -m tools.topics >/dev/null 2>&1 && break
  sleep 1
done

for name in $SERVICES; do
  nohup uv run python -m "services.$name.main" >"logs/$name.log" 2>&1 &
  echo $! >"logs/$name.pid"
  echo "started $name"
done

(cd web && nohup pnpm dev >../logs/web.log 2>&1 & echo $! >../logs/web.pid)
echo "started web"
echo
echo "Operator    https://localhost:5173/#/"
echo "Camera      https://localhost:5173/#/camera"
echo "Phone       https://<this-laptop-ip>:5173/#/phone"
echo "Supervisor  https://localhost:5173/#/supervisor"
