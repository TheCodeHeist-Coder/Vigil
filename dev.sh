#!/usr/bin/env bash
# Starts everything on this machine. Logs go to logs/. Stop with ./dev.sh stop
set -u
cd "$(dirname "$0")"
mkdir -p logs
SERVICES="ingest edge sequencer reasoner gateway"

stop_all() {
  for name in $SERVICES web web-https; do
    if [ -f "logs/$name.pid" ]; then
      kill "$(cat "logs/$name.pid")" 2>/dev/null
      rm -f "logs/$name.pid"
    fi
  done
  # Two copies of a service would both act on every message, so make sure none survive.
  pkill -f '^\.venv/bin/python -m services\.' 2>/dev/null
  sleep 2
  pkill -9 -f '^\.venv/bin/python -m services\.' 2>/dev/null
  # Vite restarts itself when its config changes, so free the ports directly.
  fuser -k 5173/tcp 5174/tcp >/dev/null 2>&1
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
  .venv/bin/python -m tools.topics >/dev/null 2>&1 && break
  sleep 1
done

for name in $SERVICES; do
  nohup .venv/bin/python -m "services.$name.main" >"logs/$name.log" 2>&1 </dev/null &
  echo $! >"logs/$name.pid"
  echo "started $name"
done

(
  cd web
  nohup pnpm exec vite >../logs/web.log 2>&1 </dev/null &
  echo $! >../logs/web.pid
  VIGIL_HTTPS=1 nohup pnpm exec vite >../logs/web-https.log 2>&1 </dev/null &
  echo $! >../logs/web-https.pid
)
echo "started web"
echo
echo "On this laptop"
echo "  Bench       http://localhost:5173/#/"
echo "  Camera      http://localhost:5173/#/camera"
echo "  Supervisor  http://localhost:5173/#/supervisor"
echo
echo "On a phone, on the same network, accepting the certificate warning"
LAN=$(hostname -I 2>/dev/null | cut -d' ' -f1)
echo "  Phone       https://$LAN:5174/#/phone"
echo "  Camera      https://$LAN:5174/#/camera"
