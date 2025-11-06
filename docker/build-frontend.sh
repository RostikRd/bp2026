#!/bin/bash
# Скрипт для збірки тільки frontend (веб-частина)

set -e

echo "🎨 Збірка Frontend (веб-частина)..."

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

# Білдимо тільки frontend target
echo "📦 Збірка образу з target 'frontend'..."
docker build \
    --target frontend \
    -f "$DOCKER_DIR/Dockerfile" \
    -t bp2026-frontend:latest \
    "$PROJECT_ROOT"

echo ""
echo "✅ Frontend зібрано успішно!"
echo ""
echo "💡 Для збірки повного образу використайте:"
echo "   bash docker/build-all.sh"

