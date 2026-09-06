.PHONY: test examples lint format typecheck build check publish publish-test \
		clean docs docs-serve docs-deploy qa

test:
	@uv run pytest tests/ -v --cov-fail-under=90

# Runs tests/examples/example.py, writing the generated .pd and .svg files to
# build/eg-output (override with PY2PD_EG_OUTPUT), then checks each .pd
# round-trips through the parser and loads in PureData if a binary is found.
examples:
	@uv run python tests/examples/example.py
	@uv run python tests/examples/check_output.py

lint:
	@uv run ruff check src/ tests/

format:
	@uv run ruff format src/ tests/

typecheck:
	@uv run mypy --strict src/ 
	@uv run mypy tests/

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
	@uv run --group docs mkdocs build

docs-serve:
	@uv run --group docs mkdocs serve

# Builds and pushes the site to the gh-pages branch, which GitHub Pages serves
# at https://shakfu.github.io/py2pd/. This publishes: it pushes to origin.
#
# The deploy commit records the current HEAD sha, so refuse to run from a dirty
# tree -- otherwise the published site contains work that sha does not describe.
# Set ALLOW_DIRTY=1 to deploy a preview anyway.
docs-deploy:
	@test -n "$(ALLOW_DIRTY)" || git diff --quiet HEAD || { \
		echo "working tree has uncommitted changes."; \
		echo "commit them first, or run: make docs-deploy ALLOW_DIRTY=1"; \
		exit 1; \
	}
	@uv run --group docs mkdocs gh-deploy --strict

clean:
	@rm -rf __pycache__ .pytest_cache .mypy_cache dist/ site/ build/
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -delete
