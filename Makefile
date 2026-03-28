.PHONY: install dev lint typecheck test run migrate sdk-install sdk-test

install:
	cd packages/core && uv sync

dev:
	cd packages/core && uv run uvicorn kestrel.app:create_app --factory --reload --port 8080

lint:
	cd packages/core && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/

format:
	cd packages/core && uv run ruff format src/ tests/ && uv run ruff check --fix src/ tests/

typecheck:
	cd packages/core && uv run mypy src/

test:
	cd packages/core && uv run pytest -v --cov=kestrel --cov-report=term-missing

migrate:
	cd packages/core && uv run alembic upgrade head

sdk-install:
	cd packages/sdk-python && uv sync --all-extras

sdk-test:
	cd packages/sdk-python && uv run pytest -v
