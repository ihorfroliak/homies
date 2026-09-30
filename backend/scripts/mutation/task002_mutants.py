"""TASK-002 mutation harness — proves each repaired invariant's tests bite.

Usage (from backend/, with a disposable PostgreSQL/PostGIS test database —
the PG tests DROP and recreate its schema):

    TEST_DATABASE_URL=postgresql+psycopg://... PG_BIN=<pg client dir> \
        python scripts/mutation/task002_mutants.py [MUTANT_ID ...]

Results: printed, and written to $MUTATION_OUT (default: mutation-results.json
in the current directory). Source bytes are restored after every mutant and
checked by SHA-256; the working tree must be clean before and after.

For each mutant: apply one exact textual replacement, run the named tests,
restore the original bytes (verified by SHA-256), classify.

killed   = pytest exit 1 and the summary reports failures and no errors
survived = tests pass with the mutant in place
invalid  = collection/setup errors, or the replacement did not apply once
"""

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
ENV = dict(os.environ)
OUT = pathlib.Path(os.environ.get("MUTATION_OUT", "mutation-results.json"))

T = "tests/"
MUTANTS = [
    {
        "id": "M01-legacy-router-in-phase1",
        "invariant": "legacy runtime isolation (routes)",
        "file": "app/composition.py",
        "old": "        admin_router,\n    ]\n",
        "new": "        admin_router,\n        __import__('app.modules.listings.router', fromlist=['router']).router,\n    ]\n",
        "tests": [T + "test_phase1_runtime.py"],
    },
    {
        "id": "M02-legacy-worker-in-phase1",
        "invariant": "legacy runtime isolation (workers)",
        "file": "app/composition.py",
        "old": "    from app.modules.events.worker import worker as notification_worker\n\n    return [\n",
        "new": "    from app.modules.events.worker import worker as notification_worker\n    from app.modules.booking.expiry import worker as _bw\n\n    return [\n        BackgroundWorker(name='booking-expiry', start=_bw.start, stop=_bw.stop, enabled=lambda: True),\n",
        "tests": [T + "test_phase1_runtime.py"],
    },
    {
        "id": "M03-publish-without-lock",
        "invariant": "publication/revoke serialisation (lock)",
        "file": "app/modules/properties/coordination.py",
        "old": "        .with_for_update()\n",
        "new": "\n",
        "tests": [T + "test_publication_race_pg.py"],
    },
    {
        "id": "M04-publish-without-recheck",
        "invariant": "publication/revoke serialisation (re-check under lock)",
        "file": "app/modules/properties/router.py",
        # Since TASK-004 the re-check under the lock is authorize_for_mutation.
        "old": "        authority.authorize_for_mutation(db, user, prop.id, \"PUBLISH_LISTING\", verified=True)\n",
        "new": "        pass\n",
        "tests": [T + "test_publication_race_pg.py"],
    },
    {
        "id": "M05-publish-unconditional-status",
        "invariant": "publication CAS (no archived resurrection)",
        "file": "app/modules/properties/router.py",
        "old": "            ClassifiedOffer.status.in_(PUBLISHABLE_FROM),\n",
        "new": "\n",
        "tests": [T + "test_publication_race_pg.py::test_an_archived_listing_is_not_republished"],
    },
    {
        "id": "M06-reveal-without-viewer-lock",
        "invariant": "contact quota serialisation",
        "file": "app/modules/properties/router.py",
        "old": "    db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))\n\n    already = db.scalar(",
        "new": "    already = db.scalar(",
        "tests": [T + "test_concurrency_r4_pg.py::test_f03_two_new_disclosures_at_quota_one_admit_exactly_one"],
    },
    {
        "id": "M07-viewing-no-relock-no-cas",
        "invariant": "viewing state CAS",
        "file": "app/modules/engagement/viewings.py",
        "old": "        .where(Viewing.id == viewing.id, Viewing.status.in_(allowed_from),\n               Viewing.version == viewing.version)\n",
        "new": "        .where(Viewing.id == viewing.id)\n",
        "extra": [(
            "    # Re-read under the row lock: a cancel may have committed while we waited\n    # for the settings lock (TASK-001 F-06).\n    viewing = _locked(db, viewing_id)\n",
            "",
        )],
        "tests": [T + "test_concurrency_r4_pg.py::test_f06_a_stale_confirmation_cannot_resurrect_a_cancelled_viewing"],
    },
    {
        "id": "M08-viewing-db-check-removed",
        "invariant": "viewing state (database backstop)",
        "file": "alembic/versions/d3f5b7a9c1e4_engagement_integrity.py",
        "old": "    op.create_check_constraint(CHECK, \"viewings\", \"(status = 'CANCELLED') = (cancelled_at IS NOT NULL)\")\n",
        "new": "    pass\n",
        "tests": [T + "test_concurrency_r4_pg.py::test_no_viewing_is_ever_confirmed_with_a_cancellation_time"],
    },
    {
        "id": "M09-conversation-without-sender-lock",
        "invariant": "conversation serialisation",
        "file": "app/modules/engagement/router.py",
        "old": "    db.execute(select(User.id).where(User.id == user.id).with_for_update(key_share=True))\n\n    # One conversation per tenant per listing",
        "new": "    # One conversation per tenant per listing",
        "tests": [T + "test_concurrency_r4_pg.py::test_f09_two_simultaneous_starts_make_one_conversation",
                  T + "test_concurrency_r4_pg.py::test_f09_two_new_threads_at_quota_one_admit_exactly_one"],
    },
    {
        "id": "M10-conversation-unique-index-removed",
        "invariant": "conversation uniqueness (database)",
        "file": "alembic/versions/d3f5b7a9c1e4_engagement_integrity.py",
        "old": "    op.create_index(\n        INDEX, \"conversations\", [\"listing_id\", \"requester_user_id\"], unique=True,\n",
        "new": "    op.create_index(\n        INDEX, \"conversations\", [\"listing_id\", \"requester_user_id\"], unique=False,\n",
        "tests": [T + "test_concurrency_r4_pg.py::test_f09_the_database_holds_one_active_thread"],
    },
    {
        "id": "M11-latitude-range-api",
        "invariant": "coordinate range (API)",
        "file": "app/modules/properties/schemas.py",
        "old": "Field(default=None, ge=-90, le=90, allow_inf_nan=False)",
        "new": "Field(default=None, allow_inf_nan=False)",
        "tests": [T + "test_coordinates.py", T + "test_coordinates_pg.py::test_the_invalid_pair_from_the_audit_is_refused"],
    },
    {
        "id": "M12-coordinate-range-db",
        "invariant": "coordinate range (database)",
        "file": "alembic/versions/a7c9e1f3b5d2_coordinate_integrity.py",
        "old": "        (f\"ck_{name}_latitude_range\", f\"{lat} IS NULL OR {lat} BETWEEN -90 AND 90\"),\n",
        "new": "        (f\"ck_{name}_latitude_range\", f\"{lat} IS NULL OR {lat} BETWEEN -900 AND 900\"),\n",
        "tests": [T + "test_coordinates_pg.py::test_the_database_refuses_invalid_exact_positions"],
    },
    {
        "id": "M13-media-keeps-source-info",
        "invariant": "media metadata normalisation (fresh image)",
        "file": "app/modules/media/sanitize.py",
        "old": "            fresh = Image.frombytes(pixels.mode, pixels.size, pixels.tobytes())\n",
        "new": "            fresh = pixels.copy(); fresh.info = dict(opened.info)\n",
        "tests": [T + "test_media_pipeline.py", T + "test_media_regressions.py"],
    },
    {
        "id": "M14-media-stores-original-bytes",
        "invariant": "media metadata normalisation (re-encode)",
        "file": "app/modules/media/sanitize.py",
        "old": "    return CleanImage(data=encoded, mime_type=mime, width=image.width, height=image.height)\n",
        "new": "    return CleanImage(data=data, mime_type=mime, width=image.width, height=image.height)\n",
        "tests": [T + "test_media_pipeline.py", T + "test_media_regressions.py"],
    },
    {
        "id": "M15-body-read-then-checked",
        "invariant": "streaming body bound",
        "file": "app/modules/media/router.py",
        "old": "        body.extend(chunk)\n        if len(body) > limit:\n            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, \"Image is too large\")\n    return bytes(body)\n",
        "new": "        body.extend(chunk)\n    if len(body) > limit:\n        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, \"Image is too large\")\n    return bytes(body)\n",
        "tests": [T + "test_media_regressions.py"],
    },
    {
        "id": "M16-dst-no-uniqueness",
        "invariant": "DST validity check",
        "file": "app/modules/engagement/viewings.py",
        "old": "    if first.utcoffset() != second.utcoffset():\n        return None\n",
        "new": "",
        "tests": [T + "test_viewing_dst.py"],
    },
    {
        "id": "M17-dst-no-real-end-check",
        "invariant": "slot inside its local window",
        "file": "app/modules/engagement/viewings.py",
        "old": "                if end.astimezone(zone).replace(tzinfo=None) > window_end:\n                    continue\n",
        "new": "",
        "tests": [T + "test_viewing_dst.py"],
    },
    {
        "id": "M18-negative-price-check-weakened",
        "invariant": "negative price CHECK",
        "file": "alembic/versions/d4e8b2c61a95_price_components.py",
        "old": "sa.CheckConstraint(\"amount_minor >= 0\", name=\"ck_listing_price_components_amount\")",
        "new": "sa.CheckConstraint(\"amount_minor >= -999\", name=\"ck_listing_price_components_amount\")",
        "tests": [T + "test_pricing_pg.py::test_a_negative_price_never_reaches_a_row"],
    },
    {
        "id": "M19-revoke-without-lock",
        "invariant": "revoke is ordered with publication",
        "file": "app/modules/properties/authority.py",
        # Since TASK-004 two mechanisms order revoke after an in-flight
        # publication: revoke's Property lock, and publication's FOR SHARE on
        # the authority row. Removing only the first leaves an equivalent
        # mutant (it survived on the TASK-004 rerun); both are removed here.
        "old": "    coordination.lock_property(db, authority.property_id)\n",
        "new": "",
        # TASK-008 reshaped the authority-row lock (its result is now kept).
        "extra": [(
            "        .order_by(PropertyAuthority.id).with_for_update(read=True)\n",
            "        .order_by(PropertyAuthority.id)\n",
        )],
        "tests": [T + "test_publication_race_pg.py::test_a_revoke_arriving_during_publication_waits_and_takes_it_down"],
    },
    {
        "id": "M20-quarantined-served",
        "invariant": "old C8 bytes never served",
        "file": "app/modules/media/models.py",
        "old": "        return self.state == \"READY\" and self.processing_version == PIPELINE_VERSION\n",
        "new": "        return self.state in (\"READY\", \"QUARANTINED\")\n",
        "tests": [T + "test_media_regressions.py"],
    },
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(tests: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=900,
    )
    return proc.returncode, proc.stdout + proc.stderr


def summary(out: str) -> str:
    lines = [ln for ln in out.strip().splitlines() if re.search(r"\d+ (passed|failed|error)", ln)]
    return lines[-1] if lines else out.strip().splitlines()[-1]


def main() -> None:
    if not ENV.get("TEST_DATABASE_URL"):
        raise SystemExit("TEST_DATABASE_URL must point at a disposable test database")
    only = set(sys.argv[1:])
    selected = [m for m in MUTANTS if not only or m["id"] in only]
    results = []
    for m in selected:
        path = ROOT / m["file"]
        original = path.read_bytes()
        digest = sha(original)
        base_code, base_out = run(m["tests"])
        base = summary(base_out)
        if base_code != 0:
            results.append({"id": m["id"], "verdict": "invalid-baseline", "baseline": base})
            print(m["id"], "BASELINE NOT GREEN:", base, flush=True)
            continue
        text = original.decode("utf-8")
        nl = "\r\n" if "\r\n" in text else "\n"
        norm = text.replace("\r\n", "\n")
        replacements = [(m["old"], m["new"])] + list(m.get("extra", []))
        applied = True
        for old, new in replacements:
            if norm.count(old) != 1:
                applied = False
                break
            norm = norm.replace(old, new, 1)
        if not applied:
            results.append({"id": m["id"], "verdict": "invalid-not-applied"})
            print(m["id"], "NOT APPLIED", flush=True)
            continue
        try:
            path.write_bytes(norm.replace("\n", nl).encode("utf-8"))
            code, out = run(m["tests"])
        finally:
            path.write_bytes(original)
        assert sha(path.read_bytes()) == digest, f"restore failed for {path}"
        s = summary(out)
        if code == 0:
            verdict = "SURVIVED"
        elif code == 1 and " failed" in s and " error" not in s:
            verdict = "killed"
        else:
            verdict = "invalid-error"
        results.append({"id": m["id"], "invariant": m["invariant"], "verdict": verdict,
                        "baseline": base, "mutant": s, "tests": m["tests"]})
        print(f"{m['id']}: {verdict} | baseline: {base} | mutant: {s}", flush=True)
    OUT.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
