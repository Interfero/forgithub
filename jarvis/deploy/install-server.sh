#!/usr/bin/env bash
# Быстрый старт на Ubuntu 22.04/24.04 (VPS)
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Установите Docker: https://docs.docker.com/engine/install/ubuntu/"
  exit 1
fi

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Создан .env — отредактируйте JARVIS_PUBLIC_URL и JARVIS_CORS_ORIGINS"
fi

docker compose build
docker compose up -d

echo ""
echo "Jarvis: http://127.0.0.1:8000 (на сервере)"
echo "Дальше: nginx + certbot для HTTPS и постоянного адреса"
echo "Документация: docs/DEPLOY_SERVER.md"
