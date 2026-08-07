QUARTO ?= $(if $(wildcard .tools/quarto-1.9.38/bin/quarto),.tools/quarto-1.9.38/bin/quarto,quarto)
UV_RUN := uv run --no-sync

.PHONY: setup sync lock-check format lint typecheck test validate site check-python check

setup: sync

sync:
	uv sync --all-groups --frozen --no-editable --reinstall-package giclab

lock-check:
	uv lock --check

format:
	$(UV_RUN) ruff format .
	$(UV_RUN) ruff check --fix .

lint:
	$(UV_RUN) ruff format --check .
	$(UV_RUN) ruff check .

typecheck:
	$(UV_RUN) mypy

test:
	$(UV_RUN) pytest

validate:
	$(UV_RUN) giclab-validate all

site:
	$(UV_RUN) giclab-build-site-data
	$(QUARTO) render notebook
	$(UV_RUN) giclab-validate site

check-python: lock-check sync lint typecheck test validate

check: check-python site
