# Stage 1: Build dependencies
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.13-slim AS runtime
RUN groupadd -r innovos && useradd -r -g innovos innovos
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY app/ ./app/
RUN chown -R innovos:innovos /app
USER innovos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
