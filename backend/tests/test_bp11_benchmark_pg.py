"""Opt-in reproducible synthetic BP-11 endpoint benchmark; never a timing test.

BP11_BENCHMARK_OUTPUT selects an output JSON file. TEST_DATABASE_URL must name
an empty disposable database: the shared PG fixture rebuilds its schema.
"""

import json
import os
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.modules.engagement import viewings
from app.modules.engagement.models import Viewing, ViewingBlackout, ViewingSettings, ViewingWindow
from app.modules.identity.models import User
from tests.conftest import TEST_DATABASE_URL, auth, register_and_login, verify_ownership
from tests.test_viewings import OFFER, PROPERTY

OUTPUT = os.environ.get("BP11_BENCHMARK_OUTPUT")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL or not OUTPUT, reason="opt-in PG benchmark")


def test_endpoint_benchmark(pg_client, pg_migrated_engine, monkeypatch):
    owner = register_and_login(pg_client, "bp11-owner@example.com", "host")
    prop = pg_client.post("/v1/properties", json=PROPERTY, headers=auth(owner)).json()["id"]
    verify_ownership(pg_client, owner, prop)
    listing = pg_client.post(f"/v1/properties/{prop}/classifieds", json=OFFER,
                             headers=auth(owner)).json()["id"]
    assert pg_client.post(f"/v1/classifieds/{listing}/publish", headers=auth(owner)).status_code == 200
    monkeypatch.setattr(viewings, "_now", lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))
    lock = threading.Lock()
    metrics = {"sql": 0, "sql_ms": 0.0, "candidates": 0}
    original = viewings.unique_instant

    def candidate(wall, zone):
        with lock:
            metrics["candidates"] += 1
        return original(wall, zone)

    monkeypatch.setattr(viewings, "unique_instant", candidate)

    def before(conn, cursor, statement, parameters, context, executemany):
        context.bp11_started = perf_counter()

    def after(conn, cursor, statement, parameters, context, executemany):
        with lock:
            metrics["sql"] += 1
            metrics["sql_ms"] += (perf_counter() - context.bp11_started) * 1000

    results = []
    for name in ("small_weekly", "many_weekly", "one_off", "dense", "blackouts", "full",
                 "maximum_days", "no_settings", "spring_dst", "autumn_dst"):
        first = date(2027, 3, 28) if name == "spring_dst" else (
            date(2027, 10, 31) if name == "autumn_dst" else date(2027, 2, 1))
        days = 31 if name in ("many_weekly", "maximum_days", "dense", "full") else 1
        with Session(pg_migrated_engine) as db:
            for table in (Viewing, ViewingBlackout, ViewingWindow, ViewingSettings):
                db.query(table).filter(table.listing_id == listing).delete()
            requester = db.query(User).filter(User.email == "bp11-owner@example.com").one().id
            if name != "no_settings":
                db.add(ViewingSettings(listing_id=listing, minimum_notice_minutes=0,
                                       duration_minutes=10, max_concurrent_bookings=2))
                if name in ("many_weekly", "maximum_days", "dense", "full"):
                    for weekday in range(7):
                        for hour in range(6, 22):
                            db.add(ViewingWindow(listing_id=listing, window_type="WEEKLY",
                                                 weekday=weekday, local_start_time=time(hour),
                                                 local_end_time=time(hour, 50)))
                else:
                    db.add(ViewingWindow(listing_id=listing,
                                         window_type="WEEKLY" if name == "small_weekly" else "ONE_OFF",
                                         weekday=first.weekday() if name == "small_weekly" else None,
                                         local_date=None if name == "small_weekly" else first,
                                         local_start_time=time(0 if "dst" in name else 10),
                                         local_end_time=time(5 if "dst" in name else 12)))
                at = datetime.combine(first, time(5), timezone.utc)
                if name in ("dense", "full"):
                    for offset in range(31 * 24):
                        for _ in range(2 if name == "full" else 1):
                            start = at + timedelta(hours=offset)
                            db.add(Viewing(listing_id=listing, requester_user_id=requester,
                                           starts_at=start, ends_at=start + timedelta(minutes=50),
                                           status="CONFIRMED"))
                if name == "blackouts":
                    db.add(ViewingBlackout(listing_id=listing, starts_at=at,
                                          ends_at=at + timedelta(hours=5), reason="private"))
            db.commit()
        event.listen(pg_migrated_engine, "before_cursor_execute", before)
        event.listen(pg_migrated_engine, "after_cursor_execute", after)

        def request():
            begin = perf_counter()
            response = pg_client.get(f"/v1/classifieds/{listing}/viewing-slots",
                                     params={"start": first.isoformat(), "days": days},
                                     headers=auth(owner))
            assert response.status_code == 200, response.text
            return (perf_counter() - begin) * 1000, response.json()["slots"]

        try:
            metrics.update(sql=0, sql_ms=0.0, candidates=0)
            sequential = [request() for _ in range(3)]
            row = {"fixture": name, "days": days,
                   "candidates": metrics["candidates"] // 3,
                   "returned": len(sequential[0][1]), "sql_statements": metrics["sql"] / 3,
                   "sql_ms_mean": metrics["sql_ms"] / 3,
                   "wall_ms_p50": statistics.median(r[0] for r in sequential),
                   "wall_ms_max": max(r[0] for r in sequential),
                   "slots": sequential[0][1]}
            metrics.update(sql=0, sql_ms=0.0, candidates=0)
            with ThreadPoolExecutor(max_workers=4) as pool:
                concurrent = list(pool.map(lambda _: request(), range(4)))
            assert all(r[1] == sequential[0][1] for r in concurrent)
            row.update(concurrent_requests=4, concurrent_sql_total=metrics["sql"],
                       concurrent_sql_ms_total=metrics["sql_ms"],
                       concurrent_wall_ms_p50=statistics.median(r[0] for r in concurrent),
                       concurrent_wall_ms_max=max(r[0] for r in concurrent))
            results.append(row)
        finally:
            event.remove(pg_migrated_engine, "before_cursor_execute", before)
            event.remove(pg_migrated_engine, "after_cursor_execute", after)
        if name == "dense":
            with pg_migrated_engine.connect() as conn:
                conn.execute(text("ANALYZE viewings"))
                params = {"l": listing, "s": at, "e": at + timedelta(days=31)}
                plans = {}
                for label, projection in (("candidate_count", "count(*)"),
                                          ("range_projection", "starts_at, ends_at")):
                    plans[label] = list(conn.scalars(text(
                        f"EXPLAIN (ANALYZE, BUFFERS) SELECT {projection} FROM viewings "
                        "WHERE listing_id=:l AND status='CONFIRMED' "
                        "AND starts_at < :e AND ends_at > :s"), params))
                row["query_plans"] = plans
    Path(OUTPUT).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
