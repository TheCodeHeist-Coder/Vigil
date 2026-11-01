#!/usr/bin/env bash
# Sets up Vigil on an Ubuntu server that already runs other apps. Safe to run again.
#
# Nothing here touches existing containers, databases or web servers. It adds:
#   /opt/vigil, a vigil user, five vigil@ services, the vigil-kafka and vigil-yugabyte
#   containers, and two firewall rules.
#
# Run from the laptop first, so the server needs no Node and no model export:
#   rsync -a .env manual models data web/dist <server>:/opt/vigil-files/
# Then on the server, as root:
#   git clone -b build https://github.com/TheCodeHeist-Coder/Vigil.git /opt/vigil
#   GATEWAY_BIND=172.18.0.1 PROXY_SUBNET=172.18.0.0/16 /opt/vigil/deploy/setup.sh
#
# To remove everything:
#   systemctl disable --now vigil@{ingest,edge,sequencer,reasoner,gateway}
#   cd /opt/vigil && docker compose --profile db down -v
#   ufw delete allow 40000:40099/udp; ufw delete allow from $PROXY_SUBNET to any port 8100 proto tcp
#   rm -rf /opt/vigil /etc/systemd/system/vigil@.service; userdel vigil
set -euo pipefail

APP=/opt/vigil
FILES=/opt/vigil-files
SERVICES="ingest edge sequencer reasoner gateway"
UDP_PORTS=40000-40099
: "${GATEWAY_BIND:?Set GATEWAY_BIND to the Docker gateway IP of your reverse proxy}"
: "${PROXY_SUBNET:?Set PROXY_SUBNET to the Docker subnet of your reverse proxy}"
cd "$APP"

[ "$(id -u)" = 0 ] || { echo "Run this as root."; exit 1; }
[ -f "$FILES/.env" ] || { echo "Copy the files to $FILES first."; exit 1; }
grep -q '^VIGIL_ACCESS_KEY=.' "$FILES/.env" || { echo "VIGIL_ACCESS_KEY is missing. A public server must not run without it."; exit 1; }

echo "== files"
cp "$FILES/.env" .env
cp -r "$FILES/manual/." manual/
cp -r "$FILES/models/." models/
mkdir -p data web/dist
cp -r "$FILES/data/." data/
cp -r "$FILES/dist/." web/dist/
sed -i '/^KAFKA_BIND=/d;/^BIND_HOST=/d;/^GATEWAY_BIND=/d;/^WEBRTC_PORTS=/d;/^LAN_IP=/d' .env
printf 'KAFKA_BIND=127.0.0.1\nBIND_HOST=127.0.0.1\nGATEWAY_BIND=%s\nWEBRTC_PORTS=%s\nLAN_IP=localhost\n' "$GATEWAY_BIND" "$UDP_PORTS" >> .env

echo "== packages"
apt-get update -qq
apt-get install -y -qq libgl1 libegl1 libgles2 libglib2.0-0 >/dev/null
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

echo "== Kafka and YugabyteDB"
docker compose --profile db up -d
echo "waiting for YugabyteDB"
ready=0
for _ in $(seq 1 90); do
  if docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -c "SELECT 1"' >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
[ "$ready" = 1 ] || { echo "YugabyteDB did not start."; docker logs --tail 20 vigil-yugabyte; exit 1; }
docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -tc "SELECT 1 FROM pg_database WHERE datname = '"'"'vigil'"'"'"' | grep -q 1 \
  || docker exec vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -c "CREATE DATABASE vigil;"'
docker exec -i vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -d vigil -q' < db/schema.sql

echo "== app"
id vigil >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin vigil
chown -R vigil:vigil "$APP"
chmod 640 .env
as_vigil() { sudo -u vigil -H "$@"; }
as_vigil uv sync --no-dev
for _ in $(seq 1 30); do as_vigil .venv/bin/python -m tools.topics >/dev/null 2>&1 && break; sleep 1; done
as_vigil .venv/bin/python -m services.knowledge.main manual/vdn1.md

echo "== services"
cp deploy/vigil@.service /etc/systemd/system/
systemctl daemon-reload
for name in $SERVICES; do systemctl enable --now "vigil@$name"; systemctl restart "vigil@$name"; done

echo "== firewall"
ufw allow "${UDP_PORTS/-/:}/udp" comment 'Vigil WebRTC video'
ufw allow from "$PROXY_SUBNET" to any port 8100 proto tcp comment 'Vigil through the proxy'

echo
echo "Done. Gateway is on http://$GATEWAY_BIND:8100, for your reverse proxy."
