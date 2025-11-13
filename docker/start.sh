#!/bin/bash
# Starts BP2026 Docker container with checks for Docker, .env file, and RAG index
set -e

echo "🐳 Starting BP2026 in Docker..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$SCRIPT_DIR"

cd "$DOCKER_DIR"

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose not found."
    echo ""
    echo "📖 For WSL Ubuntu, install Docker using one of the following methods:"
    echo ""
    echo "1. Docker Desktop for Windows (recommended):"
    echo "   - Download: https://www.docker.com/products/docker-desktop"
    echo "   - Enable WSL Integration in settings"
    echo ""
    echo "2. Or install Docker Engine in WSL:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install -y docker.io docker-compose"
    exit 1
fi

echo "✅ Using: $COMPOSE_CMD"

if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating template..."
    cat > .env << EOF
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
OPENAI_MODEL=gpt-4o-mini
EMBED_MODEL=intfloat/multilingual-e5-small
EOF
    echo "📝 Please edit docker/.env file and add your API keys!"
    echo "   Then run this script again."
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/rag_index/faiss_e5" ]; then
    echo "⚠️  WARNING: RAG index not found in rag_index/faiss_e5/"
    echo "   Container will start, but RAG functionality may not work."
    echo "   Continue? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if ! docker images | grep -q "bp2026"; then
    echo "🔨 Docker image not found. Building image..."
    $COMPOSE_CMD build
else
    echo "✅ Docker image found."
fi

echo "🚀 Starting container..."
$COMPOSE_CMD up -d

echo "⏳ Waiting for server to start..."
sleep 5

if $COMPOSE_CMD ps | grep -q "Up"; then
    echo ""
    echo "✅ Container started successfully!"
    echo ""
    echo "🌐 Open in browser:"
    echo "   - Main page: http://localhost:8000"
    echo "   - API documentation: http://localhost:8000/docs"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:            cd docker && $COMPOSE_CMD logs -f"
    echo "   Stop container:       bash docker/stop.sh"
    echo "   Restart:              cd docker && $COMPOSE_CMD restart"
else
    echo "❌ Container startup error. Check logs:"
    echo "   cd docker && $COMPOSE_CMD logs"
fi

