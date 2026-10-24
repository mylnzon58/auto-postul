SHELL := /bin/zsh
PY := uv run

.PHONY: setup dev worker test lint typecheck format check migrate seed login browser rescore sync-applied doctor open status stop clean

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

rescore:
	$(PY) python -m auto_postul.cli rescore

sync-applied:
	$(PY) python -m auto_postul.cli sync-applied

doctor:
	$(PY) python -m auto_postul.cli doctor --ping-gemini

open:
	$(PY) -c "import webbrowser; webbrowser.open('http://127.0.0.1:8765')"

status:
	@echo "--- salud ---"
	@curl -sS http://127.0.0.1:8765/api/health || true
	@echo
	@echo "--- procesos ---"
	@pgrep -fl 'auto_postul.worker|uvicorn auto_postul' || true

stop:
	@-pkill -f 'uvicorn auto_postul.web.app:app' 2>/dev/null || true
	@-pkill -f 'auto_postul.worker' 2>/dev/null || true
	@-pkill -f 'AutoPostul/linkedin/profile' 2>/dev/null || true
	@-pkill -f 'mcp-server-linkedin@4.28.0' 2>/dev/null || true
	@echo "AutoPostul detenido."

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
