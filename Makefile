PYTHON ?= .venv/bin/python

.PHONY: dev build web-dev

# Build the website, then serve it and the local API through Portless.
dev: build
	portless run --name oral-board-local-lab $(PYTHON) src/server.py

build: web/node_modules
	cd web && npm run build

web/node_modules: web/package-lock.json
	cd web && npm ci
	touch web/node_modules

# Live-reloading website on Vite; proxies /api to a server already running on 127.0.0.1:8765
# (start it with: $(PYTHON) src/server.py). Set LAB_API to point elsewhere.
web-dev: web/node_modules
	cd web && npm run dev
