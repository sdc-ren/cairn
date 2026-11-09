# Quality gate of CODING_STANDARDS §9. `make setup` once, then `make lint test`.
PYTHON ?= /usr/bin/python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup lint fmt test cov reqcov gen check

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e '.[dev]'

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/mypy
	$(BIN)/pylint --disable=all --enable=duplicate-code src tests
	$(BIN)/vulture src --min-confidence 80
	$(BIN)/python scripts/check_sizes.py --max-module-lines 300

fmt:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	$(BIN)/pytest -q

cov:
	$(BIN)/pytest -q --cov --cov-report=term-missing

reqcov:
	$(BIN)/python scripts/req_coverage.py --level M1

gen:
	$(BIN)/python scripts/gen_plugin.py

check: lint cov reqcov
	$(BIN)/python scripts/gen_plugin.py --check
