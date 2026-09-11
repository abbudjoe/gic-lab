QUARTO ?= $(if $(wildcard .tools/quarto-1.9.38/bin/quarto),.tools/quarto-1.9.38/bin/quarto,quarto)
UV_RUN := uv run --no-sync

.PHONY: setup sync lock-check format lint typecheck test validate site state-capsule registry-check control-compose category3-shadow incident-check agent-check check-python check ci-check

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

state-capsule:
	$(UV_RUN) giclab-control state-capsule --repository . --deterministic

registry-check:
	$(UV_RUN) giclab-control registry-check --repository .

control-compose:
	$(UV_RUN) giclab-control compose --repository . --all-registered

category3-shadow:
	$(UV_RUN) giclab-control shadow --repository . --all-required

incident-check:
	$(UV_RUN) giclab-control incident-check --repository .

agent-check:
	$(UV_RUN) giclab-control agent-check --repository .

check-python: lock-check sync lint typecheck agent-check test validate

check: check-python site

ci-check: lock-check sync lint typecheck agent-check validate site
	test -n "$(BASE_SHA)"
	test -n "$(HEAD_SHA)"
	$(UV_RUN) python -m giclab.ci_pytest_parity --repository . --base-sha "$(BASE_SHA)" --head-sha "$(HEAD_SHA)" $(if $(PARITY_EVIDENCE_ROOT),--evidence-root "$(PARITY_EVIDENCE_ROOT)")
