# M0: ruff + pytest only (requirements §6). The full gate of CODING_STANDARDS §9 arrives in task A1.
PYTHON ?= /usr/bin/python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: setup lint fmt test

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e '.[dev]'

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test:
	$(BIN)/pytest -q
