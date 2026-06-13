PYTHON     ?= .venv/bin/python
PYRIGHT    ?= $(shell command -v pyright 2>/dev/null || echo .venv/bin/pyright)
HA_BRANCH  ?= 2026.5.4
HA_CLONE    = /tmp/ha-core

.PHONY: help setup lint test coverage bandit import-check check
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  setup         create .venv, install HA core + dev deps (run once)"
	@echo "  lint          run pyright type check"
	@echo "  test          run pytest unit tests"
	@echo "  coverage      run pytest with coverage report"
	@echo "  bandit        run bandit security scan"
	@echo "  import-check  verify all Python files compile without syntax errors"
	@echo "  check         lint + test + coverage + bandit + import-check"

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	test -d $(HA_CLONE) || git clone --depth 1 --branch $(HA_BRANCH) https://github.com/home-assistant/core.git $(HA_CLONE)
	.venv/bin/pip install --no-deps $(HA_CLONE)
	.venv/bin/pip install voluptuous
	.venv/bin/pip install -r requirements_dev.txt
	.venv/bin/pre-commit install

lint:
	$(PYRIGHT) custom_components/yarbo/

test:
	$(PYTHON) -m pytest tests/ -v

coverage:
	$(PYTHON) -m pytest tests/ --cov=custom_components/yarbo --cov-report=term-missing

bandit:
	$(PYTHON) -m bandit -c pyproject.toml -r custom_components/yarbo/

import-check:
	$(PYTHON) -m compileall custom_components/yarbo/ -q

check: lint test coverage bandit import-check
