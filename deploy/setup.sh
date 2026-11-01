#!/usr/bin/env bash
# Sets up Vigil on an Ubuntu or Debian server. Safe to run again.
#
#   git clone -b build https://github.com/TheCodeHeist-Coder/Vigil.git /opt/vigil
#   scp .env <server>:/opt/vigil/.env
#   sudo /opt/vigil/deploy/setup.sh
#
# Set DOMAIN to use your own domain. Without it, the server's IP becomes a free
# sslip.io address, which still gets a real HTTPS certificate.
set -euo pipefail

APP=/opt/vigil
SERVICES="ingest edge sequencer reasoner gateway"
cd "$APP"

[ "$(id -u)" = 0 ] || { echo "Run this with sudo."; exit 1; }
grep -q '^GEMINI_API_KEY=.' .env || { echo "Copy your .env to $APP/.env first."; exit 1; }
grep -q '^VIGIL_ACCESS_KEY=.' .env || { echo "Set VIGIL_ACCESS_KEY in .env first. A public server must not run without it."; exit 1; }

if ss -ltnp | grep -E ':(80|443) ' | grep -qv caddy; then
  echo "Something else is using port 80 or 443:"
  ss -ltnp | grep -E ':(80|443) '
  echo "Stopping so nothing on this server breaks. Add Vigil to that web server instead,"
  echo "pointing it at localhost:8100, then run this again with SKIP_CADDY=1."
  [ "${SKIP_CADDY:-0}" = 1 ] || exit 1
fi

PUBLIC_IP=$(curl -4 -fsS https://ifconfig.me)
DOMAIN=${DOMAIN:-$(echo "$PUBLIC_IP" | tr . -).sslip.io}

echo "== packages"
apt-get update -qq
apt-get install -y -qq curl git ca-certificates debian-keyring debian-archive-keyring apt-transport-https gnupg libgl1 libglib2.0-0 >/dev/null
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs >/dev/null
fi
corepack enable >/dev/null 2>&1 || npm install -g pnpm >/dev/null

echo "== settings"
sed -i '/^KAFKA_BIND=/d;/^BIND_HOST=/d;/^LAN_IP=/d' .env
printf 'KAFKA_BIND=127.0.0.1\nBIND_HOST=127.0.0.1\nLAN_IP=localhost\n' >> .env
chmod 640 .env

echo "== Kafka and YugabyteDB"
docker compose --profile db up -d
echo "waiting for YugabyteDB"
for _ in $(seq 1 90); do
  docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -c "SELECT 1"' >/dev/null 2>&1 && break
  sleep 2
done
docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -tc "SELECT 1 FROM pg_database WHERE datname = '"'"'vigil'"'"'"' | grep -q 1 \
  || docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -c "CREATE DATABASE vigil;"'
docker exec -i vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -d vigil -q' < db/schema.sql

echo "== app"
id vigil >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin vigil
chown -R vigil:vigil "$APP"
as_vigil() { sudo -u vigil -H "$@"; }
as_vigil uv sync --no-dev
(cd web && as_vigil pnpm install --frozen-lockfile && as_vigil pnpm exec vite build)
for _ in $(seq 1 30); do as_vigil .venv/bin/python -m tools.topics >/dev/null 2>&1 && break; sleep 1; done
as_vigil .venv/bin/python -m tools.fetch_models
as_vigil .venv/bin/python -m services.knowledge.main manual/vg100.md

echo "== services"
cp deploy/vigil@.service /etc/systemd/system/
systemctl daemon-reload
for name in $SERVICES; do systemctl enable --now "vigil@$name"; systemctl restart "vigil@$name"; done

if [ "${SKIP_CADDY:-0}" != 1 ]; then
  echo "== HTTPS"
  if ! command -v caddy >/dev/null; then
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy >/dev/null
  fi
  cp deploy/Caddyfile /etc/caddy/Caddyfile
  mkdir -p /etc/systemd/system/caddy.service.d
  printf '[Service]\nEnvironment=DOMAIN=%s\n' "$DOMAIN" > /etc/systemd/system/caddy.service.d/domain.conf
  systemctl daemon-reload
  systemctl restart caddy
fi

# WebRTC video reaches the server on random UDP ports.
if command -v ufw >/dev/null && ufw status | grep -q 'Status: active'; then
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 1024:65535/udp >/dev/null
fi

KEY=$(grep '^VIGIL_ACCESS_KEY=' .env | cut -d= -f2)
echo
echo "Done. If your provider has its own firewall, also open TCP 80 and 443, and UDP 1024-65535."
echo "Team link:  https://$DOMAIN/?key=$KEY"
echo "Phone:      https://$DOMAIN/?key=$KEY#/phone"
echo "Camera:     https://$DOMAIN/?key=$KEY#/camera"
