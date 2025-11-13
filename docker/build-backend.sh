#!/bin/bash
# Builds only backend Docker image (functional part) for BP2026 application
set -e

echo "🔨 Building Backend (functional part)..."

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

echo "📦 Building image with target 'backend'..."
docker build \
    --target backend \
    -f "$DOCKER_DIR/Dockerfile" \
    -t bp2026-backend:latest \
    "$PROJECT_ROOT"

echo ""
echo "✅ Backend built successfully!"
echo ""
echo "💡 To build full image with frontend, use:"
echo "   bash docker/build-frontend.sh"
echo "   or"
echo "   bash docker/build-all.sh"

