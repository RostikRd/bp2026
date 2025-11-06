# Multi-stage build з окремими targets для backend та frontend

# ============================================
# Stage 1: Builder - встановлення Python залежностей
# ============================================
FROM python:3.11-slim as builder

# Встановлюємо системні залежності для збірки Python пакетів
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копіюємо requirements.txt та встановлюємо залежності
# Важливо: COPY requirements.txt окремо для кращого кешування Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Backend - тільки функціональна частина
# ============================================
FROM python:3.11-slim as backend

# Встановлюємо тільки необхідні системні бібліотеки для роботи
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо встановлені пакети з builder
COPY --from=builder /root/.local /root/.local

# Додаємо Python пакети до PATH
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app

# Копіюємо тільки backend файли
COPY app.py .
COPY src/rag/ask_cli.py src/rag/ask_cli.py
COPY urls.txt .

# Створюємо __init__.py файли для правильного імпорту Python модулів
RUN mkdir -p src/rag && touch src/__init__.py src/rag/__init__.py

# RAG index (якщо вже збудований)
COPY rag_index/ rag_index/

# Створюємо директорію для логів
RUN mkdir -p /app/logs

# Змінні середовища
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ============================================
# Stage 3: Frontend - тільки веб-частина
# ============================================
FROM python:3.11-slim as frontend

WORKDIR /app

# Копіюємо тільки frontend файли
COPY ui/ ui/

# ============================================
# Stage 4: Final - об'єднаний образ (backend + frontend)
# ============================================
FROM backend as final

# Копіюємо frontend з frontend stage
COPY --from=frontend /app/ui /app/ui

# Відкриваємо порт
EXPOSE 8000

# Команда запуску
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
