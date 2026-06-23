# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt pyproject.toml /build/
WORKDIR /build
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/* && \
    groupadd -r innovos && useradd -r -g innovos innovos
# Copy system-installed packages from builder
COPY --from=builder /usr/local /usr/local
WORKDIR /app
# Alembic migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/
# Application code
COPY app/ ./app/
COPY data/ ./data/
RUN chown -R innovos:innovos /app
USER innovos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
# Run alembic migrations on startup, then start the app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
