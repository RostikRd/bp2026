#!/bin/bash
# Скрипт для запуску Docker контейнера

set -e

echo "🐳 Запуск BP2026 в Docker..."

# Визначаємо директорії
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$SCRIPT_DIR"

# Переходимо в папку docker
cd "$DOCKER_DIR"

# Перевірка наявності Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не встановлений. Будь ласка, встановіть Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Визначаємо команду docker-compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ docker-compose не знайдено."
    echo ""
    echo "📖 Для WSL Ubuntu встановіть Docker одним з способів:"
    echo ""
    echo "1. Docker Desktop for Windows (рекомендовано):"
    echo "   - Завантажте: https://www.docker.com/products/docker-desktop"
    echo "   - Увімкніть WSL Integration в налаштуваннях"
    echo ""
    echo "2. Або встановіть Docker Engine в WSL:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install -y docker.io docker-compose"
    exit 1
fi

echo "✅ Використовується: $COMPOSE_CMD"

# Перевірка наявності .env файлу
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не знайдено. Створюю шаблон..."
    cat > .env << EOF
# API ключі (обов'язково заповніть!)
ANTHROPIC_API_KEY=your_anthropic_key_here
# або використайте OpenAI:
# OPENAI_API_KEY=your_openai_key_here

# Опціональні налаштування моделей
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
OPENAI_MODEL=gpt-4o-mini
EMBED_MODEL=intfloat/multilingual-e5-small
EOF
    echo "📝 Будь ласка, відредагуйте файл docker/.env та додайте ваші API ключі!"
    echo "   Потім запустіть цей скрипт знову."
    exit 1
fi

# Перевірка наявності RAG index
if [ ! -d "$PROJECT_ROOT/rag_index/faiss_e5" ]; then
    echo "⚠️  УВАГА: RAG index не знайдено в rag_index/faiss_e5/"
    echo "   Контейнер запуститься, але RAG функціональність може не працювати."
    echo "   Продовжити? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Перевірка чи образ існує, якщо ні - збудувати
if ! docker images | grep -q "bp2026"; then
    echo "🔨 Docker образ не знайдено. Збірка образу..."
    $COMPOSE_CMD build
else
    echo "✅ Docker образ знайдено."
fi

echo "🚀 Запуск контейнера..."
$COMPOSE_CMD up -d

echo "⏳ Очікування запуску сервера..."
sleep 5

# Перевірка статусу
if $COMPOSE_CMD ps | grep -q "Up"; then
    echo ""
    echo "✅ Контейнер запущено успішно!"
    echo ""
    echo "🌐 Відкрийте в браузері:"
    echo "   - Головна сторінка: http://localhost:8000"
    echo "   - API документація: http://localhost:8000/docs"
    echo ""
    echo "📋 Корисні команди:"
    echo "   Переглянути логи:     cd docker && $COMPOSE_CMD logs -f"
    echo "   Зупинити контейнер:   bash docker/stop.sh"
    echo "   Перезапустити:        cd docker && $COMPOSE_CMD restart"
else
    echo "❌ Помилка запуску контейнера. Перевірте логи:"
    echo "   cd docker && $COMPOSE_CMD logs"
fi

