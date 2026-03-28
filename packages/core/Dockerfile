# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["uvicorn", "agentrouter.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
