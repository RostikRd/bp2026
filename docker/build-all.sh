#!/bin/bash
# Скрипт для збірки повного образу (backend + frontend)

set -e

echo "🚀 Збірка повного образу (Backend + Frontend)..."

# Визначаємо директорію скрипта та корінь проєкту
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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

# Білдимо final target (backend + frontend)
echo "📦 Збірка повного образу..."
docker build \
    --target final \
    -f "$DOCKER_DIR/Dockerfile" \
    -t bp2026:latest \
    "$PROJECT_ROOT"

echo ""
echo "✅ Повний образ зібрано успішно!"
echo ""
echo "💡 Для запуску використайте:"
echo "   bash docker/start.sh"

