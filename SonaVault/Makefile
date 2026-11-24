.PHONY: up down logs migrate seed test lint fmt keys

COMPOSE = docker compose -f infra/docker/docker-compose.yml --env-file .env

up:
	$(COMPOSE) --profile core up -d --build

up-full:
	$(COMPOSE) --profile core --profile vllm --profile redis-queue --profile monitoring up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

migrate:
	cd apps/api && alembic upgrade head

migration:
	cd apps/api && alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed_sanctsound.py

test:
	cd apps/api && pytest -q

lint:
	ruff check apps/api/src
	mypy apps/api/src

fmt:
	ruff check --fix apps/api/src
	ruff format apps/api/src

keys:
	openssl genpkey -algorithm ED25519 -out infra/docker/secrets/jwt_ed25519_private.pem
	@echo "SV_MASTER_KEK_B64=$$(openssl rand -base64 32)"
	@echo "SV_BLIND_INDEX_KEY_B64=$$(openssl rand -base64 32)"
	@echo "SV_INTERNAL_SERVICE_TOKEN=$$(openssl rand -base64 32)"
	@echo "SV_MEDIAMTX_WEBHOOK_SECRET=$$(openssl rand -base64 32)"
