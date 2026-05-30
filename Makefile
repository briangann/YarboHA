PYTHON ?= python

.PHONY: help lint test check
.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  lint   run pyright type check"
	@echo "  test   run pytest unit tests"
	@echo "  check  lint + test"

lint:
	pyright custom_components/yarbo/

test:
	$(PYTHON) -m pytest tests/ -v

check: lint test
