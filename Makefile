PYTHON ?= .venv/bin/python

.PHONY: dev

dev:
	portless run --name oral-board-local-lab $(PYTHON) src/server.py
