"""The readiness dependency-decision budget is 3 seconds (PR-001RA2 RA2-N1).

PROBE_DEADLINE_S is the time after which the PostgreSQL probe has *decided*
"not ready". It is not the time the HTTP response takes: clean-up the driver
owns can run longer after the decision (see app/core/health.py), and nothing
here claims otherwise. These tests pin the decision budget itself, which the
fault-injection suite alone did not (mutant m12b, 3.0 → 60.0, survived it).
"""

import asyncio
import time

import psycopg

from app.core import health

DECISION_BUDGET_S = 3.0
# How late the decision may land on a loaded CI runner: scheduling slack only,
# far below any budget a mutant could move it to.
SLACK_S = 1.0


def test_the_decision_budget_is_three_seconds():
    assert health.PROBE_DEADLINE_S == DECISION_BUDGET_S


def test_a_probe_that_never_answers_is_decided_not_ready_at_the_budget(monkeypatch):
    async def never_connects(*args, **kwargs):
        await asyncio.sleep(3600)  # cancelled by the deadline; no connection, no clean-up

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", never_connects)
    started = time.perf_counter()  # monotonic: immune to wall-clock steps
    result = health.check_database("postgresql+psycopg://probe:probe@192.0.2.1:5432/probe")
    elapsed = time.perf_counter() - started
    assert result.ok is False and result.error == "TimeoutError"
    assert DECISION_BUDGET_S <= elapsed < DECISION_BUDGET_S + SLACK_S, elapsed
