.PHONY: help install lint type test arch check fmt

VENV ?= .venv
PY := $(VENV)/bin/python

help:
	@echo "Targets: install, lint, type, test, arch, check, fmt"

install:
	uv venv --python 3.11 $(VENV)
	$(VENV)/bin/python -m pip install -q -U pip
	uv pip install --python $(PY) -e '.[dev,cli]'

fmt:
	$(VENV)/bin/ruff format src tests
	$(VENV)/bin/ruff check --fix src tests

lint:
	$(VENV)/bin/ruff check src tests

type:
	$(VENV)/bin/mypy

arch:
	$(VENV)/bin/lint-imports

test:
	$(VENV)/bin/pytest

# Full gate, same as CI.
check: lint type arch test
