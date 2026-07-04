COMPOSE = docker compose -f ops/docker-compose.yml

.PHONY: up down logs ps test lint fmt build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

test:
	cd backend && python -m pytest -q

lint:
	cd backend && python -m ruff check app tests

fmt:
	cd backend && python -m ruff format app tests
