VENV := .venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip3

.PHONY: dev install uninstall test venv symlink

venv:
	test -d $(VENV) || python3 -m venv $(VENV)

symlink:
	mkdir -p "$(HOME)/.local/bin"
	ln -sf "$(PWD)/.venv/bin/ai" "$(HOME)/.local/bin/ai"

dev: venv
	$(PIP) install -e ".[dev]"
	$(MAKE) symlink

install: venv
	$(PIP) install .
	$(MAKE) symlink

uninstall:
	$(PIP) uninstall -y ai-launcher || true
	rm -f "$(HOME)/.local/bin/ai"

test: venv
	$(PYTHON) -m pytest tests/ -v
