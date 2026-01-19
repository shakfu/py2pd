.PHONY: test lint format typecheck clean

test:
	@uv run pytest tests/ -v

lint:
	@uv run ruff check src/ tests/

format:
	@uv run ruff format src/ tests/

typecheck:
	@uv run mypy src/

clean:
	@rm -rf __pycache__ .pytest_cache .mypy_cache
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -delete
