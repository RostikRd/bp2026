#!/bin/bash
# Builds complete Docker image (backend + frontend) for BP2026 application
set -e

NO_CACHE_FLAG=""
if [[ "$1" == "--no-cache" ]]; then
    NO_CACHE_FLAG="--no-cache"
    echo "⚠️  --no-cache mode: rebuilding everything from scratch (no cache)"
fi

echo "🚀 Building full image (Backend + Frontend)..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$SCRIPT_DIR"

cd "$DOCKER_DIR"

if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose not found."
    exit 1
fi

echo "📦 Building full image..."
$COMPOSE_CMD build $NO_CACHE_FLAG

echo ""
echo "✅ Full image built successfully!"
echo ""
echo "💡 To start the application, use:"
echo "   bash docker/start.sh"

