.PHONY: test lint format typecheck build check publish publish-test clean

test:
	@uv run pytest tests/ -v

lint:
	@uv run ruff check src/ tests/

format:
	@uv run ruff format src/ tests/

typecheck:
	@uv run mypy src/

build:
	@rm -rf dist/
	@uv build

check:
	@uv twine check dist/*

publish-test:
	@uv twine upload --repository testpypi dist/*

publish:
	@uv twine upload dist/*

clean:
	@rm -rf __pycache__ .pytest_cache .mypy_cache dist/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -delete
