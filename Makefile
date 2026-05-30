PYTHON     ?= .venv/bin/python
HA_BRANCH  ?= 2026.5.4
HA_CLONE    = /tmp/ha-core

.PHONY: help setup lint test import-check check
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  setup         create .venv, install HA core + dev deps (run once)"
	@echo "  lint          run pyright type check"
	@echo "  test          run pytest unit tests"
	@echo "  import-check  verify all Python files compile without syntax errors"
	@echo "  check         lint + test + import-check"

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	git clone --depth 1 --branch $(HA_BRANCH) https://github.com/home-assistant/core.git $(HA_CLONE)
	.venv/bin/pip install --no-deps $(HA_CLONE)
	.venv/bin/pip install voluptuous
	.venv/bin/pip install -r requirements_dev.txt

lint:
	.venv/bin/pyright custom_components/yarbo/

test:
	$(PYTHON) -m pytest tests/ -v

import-check:
	$(PYTHON) -m compileall custom_components/yarbo/ -q

check: lint test import-check
