"""TASK-012 mutation harness — listing freshness, availability, quality.

Same rules and runner as task002_mutants.py: green baseline first; killed
only on test failures with no errors; original bytes restored and SHA-256
verified. Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task012_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

API = "tests/test_listing_freshness.py"
PG = "tests/test_listing_freshness_pg.py"
SEARCH = "tests/test_classifieds_search.py"
FRESH = "app/modules/properties/freshness.py"
ROUTER = "app/modules/properties/router.py"
MIGRATION = "alembic/versions/b8d0f2a4c6e8_listing_freshness.py"

harness.MUTANTS = [
    {
        "id": "F01-visibility-predicate-ignores-freshness",
        "invariant": "a stale listing is not public (list, media via the shared clause)",
        "file": FRESH,
        "old": ("        ClassifiedOffer.last_confirmed_available_at.is_not(None),\n"
                "        ClassifiedOffer.last_confirmed_available_at > cutoff,\n"),
        "new": "",
        "tests": [API + "::test_a_stale_listing_disappears_from_every_public_path_before_any_sweep"],
    },
    {
        "id": "F02-detail-ignores-freshness",
        "invariant": "the detail page follows the same rule as the list",
        "file": ROUTER,
        "old": "    if offer is None or not freshness.is_public(offer, now):\n",
        "new": "    if offer is None or offer.status != \"active\":\n",
        "tests": [API + "::test_a_stale_listing_disappears_from_every_public_path_before_any_sweep"],
    },
    {
        "id": "F03-stale-boundary-moved-in-sql",
        "invariant": "exactly 21 days is stale (database rule)",
        "file": FRESH,
        "old": "        ClassifiedOffer.last_confirmed_available_at > cutoff,\n",
        "new": "        ClassifiedOffer.last_confirmed_available_at >= cutoff,\n",
        "tests": [PG + "::test_the_thresholds_on_the_database"],
    },
    {
        "id": "F04-due-boundary-moved-in-python",
        "invariant": "exactly 14 days is RECONFIRM_DUE (derived state)",
        "file": FRESH,
        "old": "    if age < CONFIRMATION_VALID_FOR:\n",
        "new": "    if age <= CONFIRMATION_VALID_FOR:\n",
        "tests": [API + "::test_the_policy_boundaries"],
    },
    {
        "id": "F05-sweep-waits-and-overwrites-newer-confirmation",
        "invariant": "a newer confirmation always beats the sweep",
        "file": FRESH,
        "old": ("        .limit(limit)\n"
                "        .with_for_update(skip_locked=True)\n"
                "        .scalar_subquery()\n"),
        "new": ("        .limit(limit)\n"
                "        .scalar_subquery()\n"),
        "extra": [(
            "               ClassifiedOffer.status == \"active\",\n"
            "               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)\n"
            "        .values(status=\"stale\")\n",
            "               ClassifiedOffer.status == \"active\")\n"
            "        .values(status=\"stale\")\n",
        )],
        "tests": [PG + "::test_a_confirmation_in_flight_is_skipped_by_the_sweep_and_wins"],
    },
    {
        "id": "F06-confirm-without-authorization",
        "invariant": "only someone with verified authority confirms / reactivates",
        "file": ROUTER,
        "old": ("    offer = _authorized_offer(db, user, offer_id, verified=True)\n"
                "    prop = coordination.lock_property(db, offer.property_id)\n"
                "    if prop is None:\n"
                "        raise HTTPException(status.HTTP_404_NOT_FOUND, \"Offer not found\")\n"
                "    try:\n"
                "        authority.authorize_for_mutation(db, user, prop.id, \"PUBLISH_LISTING\", "
                "verified=True)\n"
                "    except HTTPException as exc:\n"
                "        if exc.status_code == status.HTTP_404_NOT_FOUND:\n"
                "            raise HTTPException(status.HTTP_404_NOT_FOUND, \"Offer not found\") "
                "from None\n"
                "        raise\n"
                "    # The row lock"),
        "new": ("    offer = db.get(ClassifiedOffer, offer_id)\n"
                "    prop = coordination.lock_property(db, offer.property_id)\n"
                "    # The row lock"),
        "tests": [API + "::test_only_someone_with_authority_can_confirm",
                  API + "::test_a_revoked_right_cannot_bring_a_stale_listing_back"],
    },
    {
        "id": "F07-archived-is-confirmable",
        "invariant": "archived is never resurrected",
        "file": "app/modules/properties/models.py",
        "old": 'CONFIRMABLE_FROM = ("active", "stale")\n',
        "new": 'CONFIRMABLE_FROM = ("active", "stale", "archived")\n',
        "tests": [API + "::test_draft_paused_and_archived_are_not_confirmable"],
    },
    {
        "id": "F08-reactivation-skips-publication-checks",
        "invariant": "stale → active only through every publication check",
        "file": ROUTER,
        "old": ("    try:\n"
                "        spaces.ensure_listable(offer.space)\n"
                "    except spaces.SpaceArchived:\n"
                "        db.rollback()\n"),
        "new": ("    try:\n"
                "        pass\n"
                "    except spaces.SpaceArchived:\n"
                "        db.rollback()\n"),
        "tests": [API + "::test_reactivation_runs_every_publication_check"],
    },
    {
        "id": "F09-sweep-touches-paused",
        "invariant": "the sweep only moves active listings",
        "file": FRESH,
        "old": ("        .where(ClassifiedOffer.status == \"active\",\n"
                "               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)\n"
                "        .order_by"),
        "new": ("        .where(ClassifiedOffer.status.in_((\"active\", \"paused\", \"archived\")),\n"
                "               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)\n"
                "        .order_by"),
        "extra": [(
            "               ClassifiedOffer.status == \"active\",\n"
            "               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)\n"
            "        .values(status=\"stale\")\n",
            "               ClassifiedOffer.status.in_((\"active\", \"paused\", \"archived\")),\n"
            "               ClassifiedOffer.last_confirmed_available_at <= stale_cutoff)\n"
            "        .values(status=\"stale\")\n",
        )],
        "tests": [API + "::test_the_sweep_never_touches_paused_draft_or_archived"],
    },
    {
        "id": "F10-events-not-deduplicated",
        "invariant": "a rerun emits no duplicate event",
        "file": FRESH,
        "old": '    key = f"{event_type}:{offer_id}:{stamp}"[:96]\n',
        "new": '    key = f"{event_type}:{offer_id}:{datetime.now().timestamp()}"[:96]\n',
        "tests": [API + "::test_the_sweep_records_stale_once_and_is_idempotent"],
    },
    {
        "id": "F11-publication-is-not-confirmation",
        "invariant": "publication counts as confirmation",
        "file": ROUTER,
        "old": ('            .values(status="active", published_at=now, '
                'last_confirmed_available_at=now)\n'),
        "new": '            .values(status="active", published_at=now)\n',
        "tests": [API + "::test_publication_counts_as_confirmation"],
    },
    {
        "id": "F12-null-available-from-matches-available-by",
        "invariant": "an unknown move-in date is not 'available now'",
        "file": ROUTER,
        "old": "        filters.append(ClassifiedOffer.available_from <= available_by)\n",
        "new": ("        filters.append(or_(ClassifiedOffer.available_from.is_(None),\n"
                "                           ClassifiedOffer.available_from <= available_by))\n"),
        "tests": [SEARCH + "::test_an_offer_with_no_start_date_is_unknown_not_available_now",
                  API + "::test_move_in_is_derived_now_or_later_or_unknown"],
    },
    {
        "id": "F13-availability-term-unvalidated",
        "invariant": "minimum lease > 0",
        "file": "app/modules/properties/schemas.py",
        "old": ("        if self.min_term_months < MIN_CLASSIFIED_TERM_MONTHS:\n"
                "            raise ValueError(\n"
                "                f\"min_term_months must be at least {MIN_CLASSIFIED_TERM_MONTHS}, \"\n"
                "                \"or mark the offer open_ended\"\n"
                "            )\n"
                "        return self\n\n\nclass ClassifiedPage"),
        "new": "        return self\n\n\nclass ClassifiedPage",
        "tests": [API + "::test_availability_is_validated"],
    },
    {
        "id": "F14-quality-required-and-recommended-swapped",
        "invariant": "a recommendation never presents as a publication blocker",
        "file": "app/modules/properties/quality.py",
        "old": '    add("add_photos", False, len(offer.media) >= RECOMMENDED_PHOTOS)\n',
        "new": '    add("add_photos", True, len(offer.media) >= RECOMMENDED_PHOTOS)\n',
        "tests": [API + "::test_owner_view_separates_required_from_recommended"],
    },
    {
        "id": "F15-migration-invents-confirmation",
        "invariant": "backfill uses publication evidence only",
        "file": MIGRATION,
        "old": ('    op.execute("UPDATE classified_offers SET last_confirmed_available_at = '
                'published_at "\n'),
        "new": ('    op.execute("UPDATE classified_offers SET last_confirmed_available_at = '
                'now() "\n'),
        "tests": [PG + "::test_upgrading_the_accepted_task_010r_schema_backfills_from_publication_only"],
    },
    {
        "id": "F16-migration-performs-lifecycle-transition",
        "invariant": "the migration changes no listing status",
        "file": MIGRATION,
        "old": '    op.create_index(INDEX, "classified_offers", ["status", "last_confirmed_available_at"])\n',
        "new": ('    op.create_index(INDEX, "classified_offers", ["status", "last_confirmed_available_at"])\n'
                '    op.execute("UPDATE classified_offers SET status = \'stale\' WHERE status = '
                '\'active\' AND last_confirmed_available_at < now() - interval \'21 days\'")\n'),
        "tests": [PG + "::test_upgrading_the_accepted_task_010r_schema_backfills_from_publication_only"],
    },
]


if __name__ == "__main__":
    harness.main()
