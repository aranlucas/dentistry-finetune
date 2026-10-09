PYTHON ?= .venv/bin/python

.PHONY: dev dev-direct

dev:
	portless run --name oral-board-local-lab $(PYTHON) src/server.py

dev-direct:
	$(PYTHON) src/server.py --port 8765
