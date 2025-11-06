#!/bin/bash
# Скрипт для зупинки Docker контейнера

set -e

# Визначаємо директорії
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR"

# Переходимо в папку docker
cd "$DOCKER_DIR"

# Визначаємо команду docker-compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose не знайдено."
    exit 1
fi

echo "🛑 Зупинка контейнера..."
$COMPOSE_CMD down

echo "✅ Контейнер зупинено."

