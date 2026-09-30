"""TASK-012R mutation harness — session-TimeZone-independent temporal invariants.

Same rules and runner as task002_mutants.py: green baseline first; killed
only on test failures with no errors; original bytes restored and SHA-256
verified. Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task012r_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

TZ = "tests/test_listing_freshness_tz_pg.py"
FRESH = "app/modules/properties/freshness.py"

harness.MUTANTS = [
    {
        "id": "Z01-sql-day-interval-arithmetic",
        "invariant": "21 days = 21 x 24 h elapsed in SQL, in every session zone",
        "file": FRESH,
        "old": "        return now - func.make_interval(0, 0, 0, 0, 0, 0, delta.total_seconds())\n",
        "new": "        return now - literal(delta)\n",
        "tests": [
            TZ + "::test_freshness_is_elapsed_time_in_every_session_zone"
                 "[Europe/Warsaw-autumn-exactly-21x24h]",
            TZ + "::test_all_seven_public_paths_agree_in_every_session_zone"
                 "[Europe/Warsaw-spring-20d23h30m]",
        ],
    },
    {
        "id": "Z02-python-age-without-utc-normalisation",
        "invariant": "Python freshness age is elapsed time, not wall-clock",
        "file": FRESH,
        "old": "    age = to_utc(now) - to_utc(last_confirmed)  # elapsed, never wall-clock\n",
        "new": "    age = now - last_confirmed\n",
        "tests": [
            TZ + "::test_freshness_is_elapsed_time_in_every_session_zone"
                 "[Europe/Warsaw-autumn-exactly-14x24h]",
            TZ + "::test_freshness_is_elapsed_time_in_every_session_zone"
                 "[Europe/Warsaw-spring-just-before-14x24h]",
        ],
    },
    {
        "id": "Z03-move-in-on-the-session-date",
        "invariant": "move-in NOW/FROM_DATE uses the database UTC date",
        "file": "app/modules/properties/router.py",
        "old": ('    return "NOW" if offer.available_from <= freshness.utc_date(now) '
                'else "FROM_DATE"\n'),
        "new": '    return "NOW" if offer.available_from <= now.date() else "FROM_DATE"\n',
        "tests": [TZ + "::test_move_in_is_decided_on_the_utc_date"
                       "[Pacific/Kiritimati-utc-27th-session-28th]"],
    },
    {
        "id": "Z04-dedup-key-from-offset-isoformat",
        "invariant": "one reminder-cycle identity per instant, whatever the offset",
        "file": FRESH,
        "old": ('    stamp = canonical_instant(last_confirmed) if last_confirmed '
                'else "none"\n'),
        "new": '    stamp = last_confirmed.isoformat() if last_confirmed else "none"\n',
        "tests": [TZ + "::test_a_reminder_cycle_is_one_identity_across_session_zones"
                       "[UTC-Europe/Warsaw]"],
    },
    {
        "id": "Z05-db-now-left-in-session-zone",
        "invariant": "the database decision instant is handed on in UTC",
        "file": FRESH,
        "old": "        assert value is not None\n        return to_utc(value)\n",
        "new": "        assert value is not None\n        return value\n",
        "tests": [TZ + "::test_db_now_is_the_database_instant_in_utc[Europe/Warsaw]"],
    },
    {
        "id": "Z06-canonical-instant-keeps-offset",
        "invariant": "canonical instant spelling is UTC",
        "file": FRESH,
        "old": '    return to_utc(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")\n',
        "new": '    return value.isoformat()\n',
        "tests": [TZ + "::test_a_reminder_cycle_is_one_identity_across_session_zones"
                       "[Europe/Warsaw-UTC]"],
    },
]


if __name__ == "__main__":
    harness.main()
