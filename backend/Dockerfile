# Stage 1: Build dependencies
FROM python:3.13-slim AS builder
RUN pip install uv --no-cache-dir --root-user-action=ignore -i https://pypi.tuna.tsinghua.edu.cn/simple
WORKDIR /build
COPY pyproject.toml uv.lock ./
# 增加超时时间，允许大型包下载
ENV UV_HTTP_TIMEOUT=300
RUN uv sync --frozen --no-group dev

# Stage 2: Runtime
FROM python:3.13-slim AS runtime
RUN groupadd -r innovos && useradd -r -g innovos innovos
COPY --from=builder /build/.venv /app/.venv
RUN find /app/.venv/bin -type f -exec sed -i '1s|#!/build/.venv/bin/python|#!/usr/bin/env python3|' {} +
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
RUN chown -R innovos:innovos /app
USER innovos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
