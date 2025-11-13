#!/bin/bash
# Stops BP2026 Docker container
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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

echo "🛑 Stopping container..."
$COMPOSE_CMD down

echo "✅ Container stopped."

