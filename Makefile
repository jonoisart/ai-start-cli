VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip3

.PHONY: dev install uninstall test venv symlink

venv:
	python3 -m venv $(VENV)

symlink:
	ln -sf "$(PWD)/.venv/bin/ai" "$(HOME)/bin/ai"

dev: venv
	$(PIP) install -e .
	$(MAKE) symlink

install: venv
	$(PIP) install .
	$(MAKE) symlink

uninstall:
	$(PIP) uninstall -y ai-launcher
	rm -f "$(HOME)/bin/ai"

test: venv
	$(PYTHON) -m pytest tests/ -v
