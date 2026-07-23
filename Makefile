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
