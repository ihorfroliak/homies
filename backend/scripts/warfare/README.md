# Warfare harnesses (D6 survival validation)

Real adversarial/stress scripts run against the **live** docker stack —
not unit tests. They fire concurrent traffic (httpx + ThreadPoolExecutor)
at `http://localhost:8000` and assert money/concurrency invariants hold.

Prereq: stack up (`make up`) and an admin user
(`docker exec homies-api-1 python -m app.scripts.create_admin admin@homies.example admin-live-password-1`).

| Script | What it attacks |
|---|---|
| `live_smoke.py` | happy path + double-book + webhook-secret on real Postgres |
| `warfare.py` | concurrency: 60x same-date booking, 200x webhook replay, 10x payout, ghost-booking gap, reconciliation |
| `db_warfare.py` | kills Postgres mid-load, verifies ACID recovery (no partial corruption) |
| `refund_warfare.py` | refund-abuse / cancel-rebook loop, boundary validation |

Run: `.venv\Scripts\python backend\scripts\warfare\warfare.py`

Results and verdicts: `docs/design/d6-warfare-report.md`.
