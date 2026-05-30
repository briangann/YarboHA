PYTHON ?= python

.PHONY: lint test check

lint:
	pyright custom_components/yarbo/

test:
	$(PYTHON) -m pytest tests/ -v

check: lint test
