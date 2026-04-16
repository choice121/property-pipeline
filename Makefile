.PHONY: all start setup check stop push docker-up docker-down docker-build help

all: start

start:
	@bash start.sh

setup:
	@echo "==> Setting up Python virtual environment..."
	@if [ ! -f .venv/bin/python ]; then python3 -m venv .venv; fi
	@.venv/bin/pip install --no-user -q -r backend/requirements.txt
	@echo "==> Installing frontend dependencies..."
	@if [ ! -d frontend/node_modules ]; then cd frontend && npm install --silent; fi
	@echo "==> Setup complete. Run 'make start' to launch."

check:
	@echo "==> Checking environment..."
	@if [ -f backend/.env ]; then set -a; . backend/.env; set +a; fi; \
	ALL_OK=true; \
	for var in SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY IMAGEKIT_PUBLIC_KEY IMAGEKIT_PRIVATE_KEY IMAGEKIT_URL_ENDPOINT; do \
	  eval "val=\$$var"; \
	  if [ -z "$$val" ]; then echo "  MISSING: $$var"; ALL_OK=false; \
	  else echo "  OK:      $$var"; fi; \
	done; \
	for var in SUPABASE_ANON_KEY DEEPSEEK_API_KEY CHOICE_LANDLORD_ID GITHUB_TOKEN; do \
	  eval "val=\$$var"; \
	  if [ -z "$$val" ]; then echo "  OPTIONAL (not set): $$var"; \
	  else echo "  OK:      $$var"; fi; \
	done; \
	if [ "$$ALL_OK" = "false" ]; then echo ""; echo "Add missing vars to backend/.env"; exit 1; fi; \
	echo ""; echo "All required credentials are present."

push:
	@if [ -f backend/.env ]; then \
	  _GT=$$(grep '^GITHUB_TOKEN=' backend/.env | cut -d= -f2- | tr -d '[:space:]'); \
	  _GR=$$(grep '^GITHUB_REPO=' backend/.env | cut -d= -f2- | tr -d '[:space:]'); \
	  git push "https://$$_GT@github.com/$$_GR.git" main; \
	else \
	  echo "backend/.env not found"; exit 1; \
	fi

stop:
	@pkill -f "vite.*--port 5000" 2>/dev/null && echo "Stopped: Vite" || true
	@pkill -f "uvicorn" 2>/dev/null && echo "Stopped: Uvicorn" || true
	@pkill -f "python.*main.py" 2>/dev/null || true

docker-build:
	docker build -t property-pipeline .

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

help:
	@echo ""
	@echo "Property Pipeline commands:"
	@echo ""
	@echo "  make            Start the full app (backend + frontend)"
	@echo "  make setup      Install all dependencies without starting"
	@echo "  make check      Validate all environment credentials"
	@echo "  make push       Push to GitHub (no token prompt ever)"
	@echo "  make stop       Kill running services"
	@echo "  make docker-up  Run via Docker Compose"
	@echo "  make docker-down Stop Docker Compose stack"
	@echo ""
