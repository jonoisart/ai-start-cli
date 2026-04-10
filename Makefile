VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip3

.PHONY: dev install uninstall test venv

venv:
	python3 -m venv $(VENV)

dev: venv
	$(PIP) install -e .

install: venv
	$(PIP) install .

uninstall:
	$(PIP) uninstall -y ai-launcher

test: venv
	$(PYTHON) -m pytest tests/ -v
