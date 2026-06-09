PYTHON ?= python3
VENV ?= .venv
PIP = $(VENV)/bin/pip
PY = $(VENV)/bin/python
PACKAGE = satx

.PHONY: help venv deps dev-install dev_install install run format format-check test uninstall deploy clean

help:
	@echo "SatX development targets:"
	@echo "  make venv          Create virtualenv"
	@echo "  make deps          Install HackRF, rtl_433, satdump (Homebrew)"
	@echo "  make dev-install   deps + editable install with dev deps"
	@echo "  make install       deps + install satx CLI into venv"
	@echo "  make run           Run from source via start.sh"
	@echo "  make format        Format code with black"
	@echo "  make format-check  Verify formatting (CI)"
	@echo "  make test          Run unit tests"
	@echo "  make uninstall     Uninstall package from venv"
	@echo "  make deploy        Placeholder deploy target"
	@echo "  make clean         Remove build artifacts"

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip

deps:
	@command -v brew >/dev/null || (echo "Homebrew required: https://brew.sh" >&2 && exit 1)
	brew list hackrf >/dev/null 2>&1 || brew install hackrf
	brew list rtl_433 >/dev/null 2>&1 || brew install rtl_433
	brew list satdump >/dev/null 2>&1 || brew install satdump

dev-install: deps venv
	$(PIP) install -e ".[dev]"

dev_install: dev-install

install: deps venv
	$(PIP) install -e .

run:
	./start.sh

format:
	$(PY) -m black $(PACKAGE) tests

format-check:
	$(PY) -m black --check $(PACKAGE) tests

test:
	$(PY) -m pytest tests/ -v

uninstall:
	$(PIP) uninstall -y satx || true

deploy:
	@echo "No deploy target configured for satx."

clean:
	rm -rf build dist *.egg-info .pytest_cache
