.PHONY: test lint format typecheck build check publish publish-test \
		clean docs qa

test:
	@uv run pytest tests/ -v

lint:
	@uv run ruff check src/ tests/

format:
	@uv run ruff format src/ tests/

typecheck:
	@uv run mypy src/

qa: test lint typecheck format

build:
	@rm -rf dist/
	@uv build
	@uv run twine check dist/*

check:
	@uv run twine check dist/*

publish-test:
	@uv run twine upload --repository testpypi dist/*

publish:
	@uv run twine upload dist/*

docs:
	@cd docs && uv run --group docs make html

clean:
	@rm -rf __pycache__ .pytest_cache .mypy_cache dist/ docs/_build/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -delete
