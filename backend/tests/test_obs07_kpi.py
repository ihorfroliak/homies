"""OBS-07: ledger-backed KPI queries.

These tests target the ways a reporting endpoint lies rather than crashes. A
KPI that is merely wrong still renders, still looks authoritative, and gets
acted on — so each property below is one the founder would otherwise have no
way to distrust:

* GMV comes from the ledger, so a refunded booking cannot inflate it.
* Currencies never mix (the H1 defect, in reporting clothing).
* The window is half-open, so a boundary day is not counted twice.
* Commission is what was actually recognised, not `gmv * fee_bps`.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.admin import kpi as kpi_service
from app.modules.ledger import service as ledger
from app.modules.ledger.models import JournalEntry, JournalLine

WINDOW = kpi_service.Window(start=date(2026, 1, 1), end=date(2026, 2, 1))


def _post(db, kind, lines, *, currency="PLN", when=None, booking_id=None):
    """Insert a balanced entry, optionally back-dated.

    Built directly instead of through `ledger.post_entry()` because the row has
    to carry `created_at` at INSERT time. `journal_entries` is append-only, and
    on Postgres that is enforced by a database trigger (D-04) — back-dating
    with a later UPDATE raises `append-only table journal_entries: UPDATE is
    not permitted`. The first version of this suite did exactly that: it passed
    on SQLite, which has no such trigger, and CI caught it against the real
    engine. `post_entry()` flushes before returning, so its row already exists
    by the time a test could touch the timestamp.

    The balance checks below mirror the ones `post_entry()` enforces, so this
    helper cannot quietly create an entry the service would have rejected; the
    reconciliation cross-check below proves the resulting set is well-formed.
    """
    assert sum(amount for _, amount in lines) == 0, "test entry does not balance"
    assert all(amount != 0 for _, amount in lines), "test entry has a zero-amount line"

    entry = JournalEntry(kind=kind, currency=currency, booking_id=booking_id)
    if when is not None:
        entry.created_at = when
    db.add(entry)
    db.flush()
    for code, amount in lines:
        account = ledger.ensure_account(db, code)
        db.add(JournalLine(entry_id=entry.id, account_id=account.id, amount=amount))
    db.commit()
    return entry


def _capture(db, amount, **kw):
    return _post(db, "payment_captured",
                 [(ledger.PROVIDER_CASH, amount), (ledger.BOOKING_ESCROW, -amount)], **kw)


def _refund(db, amount, **kw):
    return _post(db, "refund",
                 [(ledger.BOOKING_ESCROW, amount), (ledger.PROVIDER_CASH, -amount)], **kw)


def _allocate(db, total, fee, host="h1", **kw):
    return _post(db, "payout_allocated", [
        (ledger.BOOKING_ESCROW, total),
        (ledger.host_payable_code(host), -(total - fee)),
        (ledger.PLATFORM_REVENUE, -fee),
    ], **kw)


@pytest.fixture
def db(client):  # noqa: ARG001 — client creates the schema and the session factory
    from tests.conftest import TestingSession

    with TestingSession() as session:
        yield session


IN_WINDOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def test_gmv_comes_from_the_ledger_not_the_booking_total(db):
    """A refunded booking must not inflate GMV.

    `bookings.total_amount` survives a refund untouched, so summing that column
    would report money the business gave back as revenue.
    """
    _capture(db, 100_000, when=IN_WINDOW)
    _refund(db, 100_000, when=IN_WINDOW)

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["gmv_captured"] == 100_000
    assert report.money["refunded"] == 100_000
    assert report.money["gmv_net"] == 0
    assert report.ratios_bps["refund_rate"] == 10_000  # 100%


def test_currencies_never_mix(db):
    """H1 in reporting clothing: summing across currencies is meaningless."""
    _capture(db, 100_000, currency="PLN", when=IN_WINDOW)
    _capture(db, 500_000, currency="EUR", when=IN_WINDOW)

    pln = kpi_service.compute(db, currency="PLN", window=WINDOW)
    eur = kpi_service.compute(db, currency="EUR", window=WINDOW)
    assert pln.money["gmv_captured"] == 100_000
    assert eur.money["gmv_captured"] == 500_000


def test_window_is_half_open_so_a_boundary_day_is_not_double_counted(db):
    """December's last day must not appear in both December and January."""
    last_moment_of_january = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
    first_moment_of_february = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    _capture(db, 10_000, when=last_moment_of_january)
    _capture(db, 70_000, when=first_moment_of_february)

    january = kpi_service.compute(db, currency="PLN", window=WINDOW)
    february = kpi_service.compute(
        db, currency="PLN", window=kpi_service.Window(date(2026, 2, 1), date(2026, 3, 1))
    )
    assert january.money["gmv_captured"] == 10_000
    assert february.money["gmv_captured"] == 70_000


def test_entries_outside_the_window_are_excluded(db):
    _capture(db, 42_000, when=datetime(2025, 12, 31, tzinfo=timezone.utc))
    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["gmv_captured"] == 0


def test_commission_is_recognised_not_derived_from_gmv(db):
    """Captured money is not yet earned revenue.

    Commission is booked at payout_allocated, after the stay completes. A
    booking that is paid but not yet completed has earned the platform nothing
    — the guest can still cancel — so `gmv * fee_bps` would book revenue the
    business is not entitled to keep.
    """
    _capture(db, 100_000, when=IN_WINDOW)  # paid, stay not finished
    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["gmv_captured"] == 100_000
    assert report.money["commission_recognised"] == 0
    assert report.ratios_bps["take_rate"] == 0

    _allocate(db, total=100_000, fee=15_000, when=IN_WINDOW)  # stay completed
    after = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert after.money["commission_recognised"] == 15_000
    assert after.ratios_bps["take_rate"] == 1_500  # 15% of net GMV


def test_ratios_are_integers_in_basis_points(db):
    """Chosen so truncation and half-up rounding disagree.

    200000/300000 is 66.666...%, which is 6667 bps rounded half-up and 6666
    truncated — a test using 1/3 would pass under either and prove nothing.
    """
    _capture(db, 300_000, when=IN_WINDOW)
    _refund(db, 200_000, when=IN_WINDOW)
    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.ratios_bps["refund_rate"] == 6667
    assert all(type(v) is int for v in report.ratios_bps.values())
    assert all(type(v) is int for v in report.money.values())


def test_empty_window_reports_zero_not_an_error(db):
    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["gmv_captured"] == 0
    assert report.ratios_bps["take_rate"] == 0
    assert report.adr_minor_units == 0


def test_payouts_and_escrow_do_not_leak_into_gmv(db):
    """payout_sent also credits provider_cash; only captures are GMV."""
    _capture(db, 100_000, when=IN_WINDOW)
    _post(db, "payout_sent", [
        (ledger.host_payable_code("h1"), 85_000),
        (ledger.PROVIDER_CASH, -85_000),
    ], when=IN_WINDOW)

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.money["gmv_captured"] == 100_000, "a payout must not reduce GMV"
    assert report.money["payouts_sent"] == 85_000


# --- endpoint ----------------------------------------------------------------


def test_endpoint_returns_the_report(client, admin_token):
    resp = client.get(
        "/v1/admin/kpi?from=2026-01-01&to=2026-02-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "ledger"
    assert body["window"]["end_exclusive"] is True
    assert "gmv_net" in body["money_minor_units"]


def test_endpoint_declares_what_it_cannot_answer(client, admin_token):
    """Six numbers look complete. The founder must be able to tell that CM2 is
    absent because the data does not exist, not because it is zero."""
    body = client.get(
        "/v1/admin/kpi?from=2026-01-01&to=2026-02-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    kpis = {u["kpi"] for u in body["unavailable"]}
    assert any("CM2" in k for k in kpis)
    assert any("Occupancy" in k for k in kpis)
    assert all(u["reason"] and u["unblocked_by"] for u in body["unavailable"])


def test_endpoint_rejects_an_inverted_window(client, admin_token):
    resp = client.get(
        "/v1/admin/kpi?from=2026-02-01&to=2026-01-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_endpoint_is_admin_only(client):
    client.post("/v1/auth/register", json={
        "email": "guest-kpi@example.com", "password": "password-123456", "role": "guest"})
    token = client.post("/v1/auth/login", json={
        "email": "guest-kpi@example.com", "password": "password-123456"}).json()["access_token"]
    resp = client.get(
        "/v1/admin/kpi?from=2026-01-01&to=2026-02-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_kpi_totals_agree_with_the_reconciliation_report(db):
    """Cross-check against an independent reader of the same ledger.

    If the KPI query and reconcile() disagree about the money, one of them is
    wrong and neither can be trusted.
    """
    _capture(db, 100_000, when=IN_WINDOW)
    _allocate(db, total=100_000, fee=15_000, when=IN_WINDOW)
    _post(db, "payout_sent", [
        (ledger.host_payable_code("h1"), 85_000),
        (ledger.PROVIDER_CASH, -85_000),
    ], when=IN_WINDOW)

    recon = ledger.reconcile(db)
    assert recon["ok"] is True, recon

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    balances = recon["balances"]
    # provider_cash = captured - payouts_sent (nothing refunded here)
    assert report.money["gmv_captured"] - report.money["payouts_sent"] == balances["provider_cash"]
    # platform_revenue is an income account: credit-negative in the ledger,
    # reported positive as recognised commission.
    assert report.money["commission_recognised"] == -balances[ledger.PLATFORM_REVENUE]


def test_nights_and_adr_use_the_same_window_as_the_money(client, admin_token, db):
    """An ADR mixing one window's revenue with another's nights is not a price."""
    from app.modules.booking.models import Booking

    booking = Booking(
        guest_id="g1", listing_id="l1",
        check_in=date(2026, 3, 1), check_out=date(2026, 3, 5),  # 4 nights
        total_amount=80_000, currency="PLN", status="confirmed",
        idempotency_key="kpi-adr-test",
    )
    db.add(booking)
    db.commit()
    _capture(db, 80_000, when=IN_WINDOW, booking_id=booking.id)

    report = kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert report.nights_sold == 4
    assert report.adr_minor_units == 20_000

    outside = kpi_service.compute(
        db, currency="PLN", window=kpi_service.Window(date(2026, 6, 1), date(2026, 7, 1))
    )
    assert outside.nights_sold == 0, "nights must follow the capture window, not the stay dates"


def test_ledger_stays_append_only_under_the_kpi_query(db):
    """Reporting must never mutate the source of truth."""
    _capture(db, 50_000, when=IN_WINDOW)
    before = db.scalars(select(JournalEntry.id)).all()
    kpi_service.compute(db, currency="PLN", window=WINDOW)
    assert db.scalars(select(JournalEntry.id)).all() == before


# --- real Postgres (gated) ----------------------------------------------------
#
# SQLite stores datetimes as strings and is loose about timezones; Postgres uses
# native timestamptz. For a money report whose whole correctness rests on window
# boundaries, the SQLite pass proves the arithmetic but not the boundary — a
# timezone conversion could shift a capture into the neighbouring month and
# silently misstate GMV for both. These run in CI against postgres:16.


def test_window_boundaries_hold_on_real_postgres(pg_session):
    """The boundary case, on the engine that actually stores timestamptz."""
    _capture(pg_session, 10_000, when=datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc))
    _capture(pg_session, 70_000, when=datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc))

    january = kpi_service.compute(pg_session, currency="PLN", window=WINDOW)
    february = kpi_service.compute(
        pg_session, currency="PLN", window=kpi_service.Window(date(2026, 2, 1), date(2026, 3, 1))
    )
    assert january.money["gmv_captured"] == 10_000
    assert february.money["gmv_captured"] == 70_000
    assert january.money["gmv_captured"] + february.money["gmv_captured"] == 80_000


def test_currency_scoping_holds_on_real_postgres(pg_session):
    for amount, currency in ((100_000, "PLN"), (500_000, "EUR")):
        ledger.post_entry(
            pg_session,
            kind="payment_captured",
            lines=[(ledger.PROVIDER_CASH, amount), (ledger.BOOKING_ESCROW, -amount)],
            currency=currency,
        )
    pg_session.commit()

    wide = kpi_service.Window(date(2020, 1, 1), date(2100, 1, 1))
    assert kpi_service.compute(pg_session, currency="PLN", window=wide).money[
        "gmv_captured"
    ] == 100_000
