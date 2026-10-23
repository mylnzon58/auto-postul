SHELL := /bin/zsh
PY := uv run

.PHONY: setup dev worker test lint typecheck format check migrate seed login browser doctor clean

setup:
	uv sync --all-groups
	uv run patchright install chromium

browser:
	uv run patchright install chromium

dev:
	$(PY) uvicorn auto_postul.web.app:app --host 127.0.0.1 --port 8765 --reload

worker:
	$(PY) python -m auto_postul.worker

test:
	$(PY) pytest

lint:
	$(PY) ruff check .
	$(PY) ruff format --check .

format:
	$(PY) ruff check --fix .
	$(PY) ruff format .

typecheck:
	$(PY) mypy src

check: lint typecheck test

migrate:
	$(PY) alembic upgrade head

seed:
	$(PY) python -m auto_postul.db.seed

login:
	$(PY) python -m auto_postul.cli login

doctor:
	$(PY) python -m auto_postul.cli doctor --ping-gemini

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
