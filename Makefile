COMPOSE = docker compose -f ops/docker-compose.yml

.PHONY: up down logs ps test lint fmt build db-upgrade db-fresh test-pg

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

# TD-01: migrations are the single schema source of truth.
# Apply migrations to the DB in backend settings (DATABASE_URL):
db-upgrade:
	cd backend && python -m alembic upgrade head

# Build a schema for the Postgres integration/migration tests, then run them.
# TEST_DATABASE_URL must point at a throwaway Postgres database.
#   TEST_DATABASE_URL=postgresql+psycopg://homies:homies@localhost:5433/homies_ci make test-pg
test-pg:
	cd backend && python -m pytest tests/test_td01_migrations.py -q

# Stripe Test Mode suite. Needs real test credentials; never runs in ordinary
# CI and refuses to run against a live key.
#   STRIPE_LIVE_TESTS=1 STRIPE_API_KEY=sk_test_... \
#   STRIPE_TEST_CONNECTED_ACCOUNT=acct_... make test-stripe
test-stripe:
	cd backend && STRIPE_LIVE_TESTS=1 python -m pytest tests/stripe_live -v

lint:
	cd backend && python -m ruff check app tests

fmt:
	cd backend && python -m ruff format app tests
