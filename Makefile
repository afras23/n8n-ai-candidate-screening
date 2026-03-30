.PHONY: dev test lint format typecheck migrate docker clean evaluate

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	@python -c "import greenlet" 2>/dev/null || { \
		echo "Missing greenlet (required for SQLAlchemy async engine.dispose). Run: pip install -r requirements.txt" 1>&2; \
		exit 1; \
	}
	DATABASE_URL=postgresql+asyncpg://test:test@127.0.0.1:5432/test_db \
	OPENAI_API_KEY=test-openai-key \
	pytest tests/ -v --tb=short

lint:
	ruff check app tests conftest.py migrations
	ruff format --check app tests conftest.py migrations

format:
	ruff format app tests conftest.py migrations

typecheck:
	mypy app

migrate:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL must be set for migrations" 1>&2; exit 1)
	alembic upgrade head

docker:
	docker compose up --build -d

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

evaluate:
	DATABASE_URL=postgresql+asyncpg://test:test@127.0.0.1:5432/test_db \
	OPENAI_API_KEY=test-openai-key \
	PYTHONPATH=. python scripts/evaluate.py
