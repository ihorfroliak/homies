"""TASK-014 mutation / fault harness — saved listings, saved searches, alerts.

Same rules and runner as task002_mutants.py: green baseline first; killed only
on test failures with no errors; original bytes restored and SHA-256 verified.
Usage from backend/:

    TEST_DATABASE_URL=postgresql+psycopg://... \\
        python scripts/mutation/task014_mutants.py [MUTANT_ID ...]
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import task002_mutants as harness  # noqa: E402

SL = "tests/test_saved_listings.py"
SS = "tests/test_saved_searches.py"
GEN = "tests/test_public_generation.py"
AL = "tests/test_saved_search_alerts.py"
PG = "tests/test_saved_search_alerts_pg.py"
SAVED_ROUTER = "app/modules/saved/router.py"
SAVED_SERVICE = "app/modules/saved/service.py"
SEARCH = "app/modules/properties/search.py"
PUBLICITY = "app/modules/properties/publicity.py"
MATCHING = "app/modules/alerts/matching.py"
DELIVERY = "app/modules/alerts/delivery.py"
EVENTS_WORKER = "app/modules/events/worker.py"
MIGRATION = "alembic/versions/f3b5d7e9a1c2_saved_search_alerts.py"

harness.MUTANTS = [
    {
        "id": "A01-saved-listing-delete-without-owner",
        "invariant": "a user can only remove their own saves (no IDOR)",
        "file": SAVED_ROUTER,
        "old": ("    removed = db.execute(delete(SavedListing).where(SavedListing.user_id == user.id,\n"
                "                                                    SavedListing.listing_id == "
                "listing_id))\n"),
        "new": "    removed = db.execute(delete(SavedListing).where(SavedListing.listing_id == listing_id))\n",
        "tests": [SL + "::test_saves_are_private_to_their_owner"],
    },
    {
        "id": "A01b-saved-listing-list-without-owner",
        "invariant": "a user only ever lists their own saves",
        "file": SAVED_ROUTER,
        "old": "        select(SavedListing).where(SavedListing.user_id == user.id)\n        .order_by(",
        "new": "        select(SavedListing)\n        .order_by(",
        "tests": [SL + "::test_saves_are_private_to_their_owner"],
    },
    {
        "id": "A02-tombstone-leaks-listing-details",
        "invariant": "a non-public save is a tombstone: no title, price, place, media",
        "file": SAVED_ROUTER,
        "old": "        ClassifiedOffer.id.in_(ids), freshness.public_clause(db))))\n",
        "new": "        ClassifiedOffer.id.in_(ids))))\n",
        "tests": [SL + "::test_non_public_save_is_a_privacy_safe_tombstone"],
    },
    {
        "id": "A03-evaluation-without-public-clause",
        "invariant": "stored-search evaluation carries the public rule itself",
        "file": SEARCH,
        "old": "            .where(ClassifiedOffer.id == listing_id, freshness.public_clause(db))\n",
        "new": "            .where(ClassifiedOffer.id == listing_id)\n",
        "tests": [AL + "::test_evaluation_never_matches_a_listing_that_is_not_public"],
    },
    {
        "id": "A04-no-baseline-initial-flood",
        "invariant": "matches existing when a search is saved never alert",
        "file": MATCHING,
        "old": "               SavedSearch.baseline_at < became_public_at)\n",
        "new": "               SavedSearch.baseline_at.is_not(None))\n",
        "tests": [AL + "::test_existing_matches_never_alert"],
    },
    {
        "id": "A05-reconfirm-opens-an-episode",
        "invariant": "public → public never increments public_generation",
        "file": PUBLICITY,
        "old": "    opening = not was_public(row.status, row.last_confirmed_available_at, now)\n",
        "new": "    opening = True\n",
        "tests": [GEN + "::test_already_public_republish_and_reconfirm_open_no_episode"],
    },
    {
        "id": "A06-silent-expiry-reactivation-no-episode",
        "invariant": "generation follows the public RULE, not the status label",
        "file": PUBLICITY,
        "old": "    return status == \"active\" and freshness.state(last_confirmed, now) in (\n",
        "new": "    return status == \"active\" or freshness.state(last_confirmed, now) in (\n",
        "tests": [GEN + "::test_silent_freshness_expiry_then_confirm_opens_a_new_episode"],
    },
    {
        "id": "A07-generation-and-event-not-atomic",
        "invariant": "generation, event and work item commit together or not at all",
        "file": PUBLICITY,
        "old": ("        raise RuntimeError(\"listing changed under its own row lock\")\n"
                "    if opening:\n"),
        "new": ("        raise RuntimeError(\"listing changed under its own row lock\")\n"
                "    db.commit()\n"
                "    if opening:\n"),
        "tests": [GEN + "::test_generation_event_and_work_item_are_atomic"],
    },
    {
        "id": "A08-match-uniqueness-removed",
        "invariant": "one SavedSearchMatch per (search, listing, generation) — database-backed",
        "file": MIGRATION,
        "old": ("        sa.Column(\"saved_search_id\", sa.String(36),\n"
                "                  sa.ForeignKey(\"saved_searches.id\", ondelete=\"CASCADE\"), "
                "primary_key=True),\n"
                "        sa.Column(\"listing_id\", sa.String(36), "
                "sa.ForeignKey(\"classified_offers.id\"),\n"
                "                  primary_key=True),\n"
                "        sa.Column(\"public_generation\", sa.BigInteger(), primary_key=True),\n"
                "        sa.Column(\"user_id\","),
        "new": ("        sa.Column(\"saved_search_id\", sa.String(36),\n"
                "                  sa.ForeignKey(\"saved_searches.id\", ondelete=\"CASCADE\")),\n"
                "        sa.Column(\"listing_id\", sa.String(36), "
                "sa.ForeignKey(\"classified_offers.id\")),\n"
                "        sa.Column(\"public_generation\", sa.BigInteger()),\n"
                "        sa.Column(\"user_id\","),
        "tests": [PG + "::test_b_two_searches_one_user_one_delivery"],
    },
    {
        "id": "A09-user-delivery-dedup-removed",
        "invariant": "one delivery per (user, listing, generation, channel) — database-backed",
        "file": MIGRATION,
        "old": ("        sa.UniqueConstraint(\"user_id\", \"listing_id\", \"public_generation\", "
                "\"channel\",\n"
                "                            name=\"uq_alert_deliveries_user_episode_channel\"),\n"),
        "new": "",
        "tests": [PG + "::test_b_two_searches_one_user_one_delivery"],
    },
    {
        "id": "A10-send-time-public-check-removed",
        "invariant": "a queued alert for a listing no longer public is suppressed as such",
        "file": DELIVERY,
        "old": ("    if offer is None or not freshness.is_public(offer, now):\n"
                "        return Check(\"listing_not_public\")\n"),
        "new": ("    if offer is None:\n"
                "        return Check(\"listing_not_public\")\n"),
        "tests": [AL + "::test_listing_no_longer_public_suppresses_queued_delivery"],
    },
    {
        "id": "A11-send-time-rematch-removed",
        "invariant": "a queued alert is re-matched against the canonical query at send time",
        "file": DELIVERY,
        "old": "    still = [s for (s, _), hit in zip(valid, flags) if hit]\n",
        "new": "    still = [s for s, _ in valid]\n",
        "tests": [AL + "::test_listing_no_longer_matching_suppresses_queued_delivery"],
    },
    {
        "id": "A12-unsubscribe-does-nothing",
        "invariant": "an unsubscribe suppresses queued future deliveries",
        "file": DELIVERY,
        "old": "                       .values(notifications_enabled=False, updated_at=now,\n",
        "new": "                       .values(updated_at=now,\n",
        "tests": [AL + "::test_unsubscribe_from_one_search_suppresses_its_queued_delivery"],
    },
    {
        "id": "A13-alert-smtp-to-user-id",
        "invariant": "alert email goes to the verified address, never the user id",
        "file": DELIVERY,
        "old": "    result = channel_for(\"email\").send(to=user.email, subject=message[\"subject\"],\n",
        "new": "    result = channel_for(\"email\").send(to=d.user_id, subject=message[\"subject\"],\n",
        "tests": [AL + "::test_alert_email_goes_to_the_verified_address_never_the_user_id"],
    },
    {
        "id": "A13b-transactional-smtp-to-user-id",
        "invariant": "the legacy delivery worker resolves the address at send time",
        "file": EVENTS_WORKER,
        "old": "    return user.email\n",
        "new": "    return user.id\n",
        "tests": [AL + "::test_transactional_email_resolves_the_address_at_send_time"],
    },
    {
        "id": "A14-unknown-criterion-dropped",
        "invariant": "an invalid stored query is INVALID, never silently broadened",
        "file": SEARCH,
        "old": "            _refuse(f\"'{name}' is not a search parameter\")\n",
        "new": "            continue\n",
        "tests": [SS + "::test_a_corrupted_stored_query_is_invalid_not_broadened"],
    },
    {
        "id": "A14b-retired-place-ignored",
        "invariant": "a stored query naming a retired place never alerts",
        "file": SAVED_SERVICE,
        "old": "    q = search.parse_query_string(db, saved.canonical_query, ctx)\n"
               "    search.check_references(db, q, ctx)\n",
        "new": "    q = search.parse_query_string(db, saved.canonical_query, ctx)\n",
        "tests": [AL + "::test_invalid_stored_query_never_alerts"],
    },
    {
        "id": "A15-ack-consumes-newer-generation",
        "invariant": "acknowledging generation N never consumes N+1",
        "file": MATCHING,
        "old": ("        .where(ListingPublicGeneration.listing_id == listing_id,\n"
                "               ListingPublicGeneration.public_generation == generation,\n"
                "               ListingPublicGeneration.alert_status.in_("),
        "new": ("        .where(ListingPublicGeneration.listing_id == listing_id,\n"
                "               ListingPublicGeneration.alert_status.in_("),
        "tests": [PG + "::test_c_acknowledging_n_never_consumes_n_plus_one"],
    },
    {
        "id": "A16-alert-matching-on-exact-point",
        "invariant": "spatial alert matching uses the PUBLIC point only",
        "file": SEARCH,
        "old": "_PUBLIC_GEOG: ColumnElement[Any] = literal_column(\"classified_offers.public_geog\")\n",
        "new": "_PUBLIC_GEOG: ColumnElement[Any] = literal_column(\"properties.exact_geog\")\n",
        "tests": [PG + "::test_spatial_matching_uses_the_public_point_only"],
    },
    {
        "id": "A17-paused-search-still-sends",
        "invariant": "a search paused after the match is suppressed at send time",
        "file": DELIVERY,
        "old": "    live = [s for s in linked if s.status == \"active\" and s.notifications_enabled]\n",
        "new": "    live = linked\n",
        "tests": [AL + "::test_paused_search_suppresses_queued_delivery"],
    },
    {
        "id": "A18-saved-search-without-owner",
        "invariant": "saved searches are private to their owner (no IDOR)",
        "file": SAVED_ROUTER,
        "old": ("    found = db.scalar(select(SavedSearch).where(SavedSearch.id == search_id,\n"
                "                                                SavedSearch.user_id == user_id))\n"),
        "new": "    found = db.scalar(select(SavedSearch).where(SavedSearch.id == search_id))\n",
        "tests": [SS + "::test_saved_searches_are_private_to_their_owner"],
    },
]


if __name__ == "__main__":
    harness.main()
