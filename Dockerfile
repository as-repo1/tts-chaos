FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=2002 \
    ENABLE_DOCS=false \
    CORS_ORIGINS=http://localhost:2002,http://127.0.0.1:2002

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY backend ./backend
COPY frontend ./frontend
COPY docs ./docs

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .[edge]

RUN mkdir -p /app/models /app/generated_audio /app/backend/app/data

EXPOSE 2002

CMD ["sh", "-c", "uvicorn backend.app.main:app --host ${HOST} --port ${PORT}"]
