#!/usr/bin/env bash
# Builds the web app on the server, in a throwaway container with capped resources,
# so a slow laptop connection is never needed and Node is never installed here.
# The live site is only replaced after a good build.
set -euo pipefail

APP=/opt/vigil
WORK=$(mktemp -d /tmp/vigil-web.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

cd "$APP/web"
tar --exclude=node_modules --exclude=dist -cf - . | tar -xf - -C "$WORK"
docker run --rm --cpus 1 --memory 1g -v "$WORK:/app" -w /app node:22-slim \
  sh -c 'npm install -g pnpm@10 >/dev/null 2>&1 && pnpm install --frozen-lockfile >/dev/null && pnpm exec vite build'
[ -f "$WORK/dist/index.html" ] || { echo "Build failed, the live site was not changed."; exit 1; }

rm -rf "$APP/web/dist.old"
[ -d "$APP/web/dist" ] && mv "$APP/web/dist" "$APP/web/dist.old"
mv "$WORK/dist" "$APP/web/dist"
rm -rf "$APP/web/dist.old"
chown -R vigil:vigil "$APP/web/dist"
systemctl restart vigil@gateway
echo "web app live"
