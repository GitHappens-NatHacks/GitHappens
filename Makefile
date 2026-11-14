SHELL := /bin/bash
PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest

.PHONY: dev dev-tauri build build-backend build-frontend test

dev:
	@trap 'kill 0' EXIT; \
	$(PYTHON) -m backend.sidecar_main 8000 & \
	npm --prefix frontend run dev

dev-tauri:
	@trap 'kill 0' EXIT; \
	$(PYTHON) -m backend.sidecar_main 8000 & \
	npx tauri dev

build-backend:
	$(PYTHON) scripts/build_backend.py

build-frontend:
	npm --prefix frontend run typecheck
	npm --prefix frontend run build

build: build-backend build-frontend
	npx tauri build

test:
	TTS_ENABLED=0 GAZE_BACKEND=mediapipe $(PYTEST) -v
	npm --prefix frontend run typecheck
	npm --prefix frontend run build
