# TASK-010 — mutation evidence

Harnesses: [`task010_mutants.py`](../../backend/scripts/mutation/task010_mutants.py)
(new; runner shared with `task002_mutants.py`), and regression reruns of
`task004_mutants.py`, `task006_mutants.py` and `task008_mutants.py` — the
foundation race tests those harnesses rely on had their commit-order evidence
rewritten in TASK-010. Run 2026-09-25 on the TASK-010 working tree, local
disposable PostgreSQL 16.4 / PostGIS 3.4.3 container, Python 3.14.3 venv.
Rules as before: green baseline per mutant; killed only when pytest exits 1
with failures and no errors; original bytes restored and verified by SHA-256
after each mutant; a separate `sha256sum -c` of the touched source files after
the run matched.

Preconditions (same tree): full SQLite suite 740 passed / 207 skipped; full
PostgreSQL/PostGIS suite 946 passed / 1 skipped.

## TASK-010 mutants — 10 / 10 killed

| Mutant | Invariant | Killing test(s) | Verdict |
|---|---|---|---|
| G01 `postal_code` added to the public `PublicPlace` schema | public place carries no private address component | `test_the_public_listing_shows_the_place_and_nothing_private`, `test_public_schemas_cannot_carry_private_address_fields` | killed |
| G02 hierarchy trigger reads the parent without `FOR SHARE` | no cycle under concurrent re-parenting | `test_two_concurrent_reparentings_cannot_close_a_loop` | killed |
| G03 trigger's level rule removed (`level = parent.level + 1`) | levels follow the parent → acyclic | `test_levels_must_follow_the_parent`, `test_a_cycle_cannot_be_written` | killed |
| G04 `ROOM` accepted and mapped as a property type (API) | ROOM is a Space, never a property classification | `test_room_and_incoherent_classifications_are_refused` | killed |
| G05 database category CHECK admits `ROOM` | ROOM never a category (database) | `test_the_database_refuses_incoherent_classification` | killed |
| G06 `(source_code, external_id)` uniqueness removed | external ids unique within their source namespace | `test_external_ids_are_unique_within_their_source_only` | killed |
| G07 locality-in-address-country check removed | an address's places are in its country | `test_a_locality_in_another_country_is_refused` | killed |
| G08 backfill marks legacy addresses `USER_INPUT` | brownfield backfill never pretends to know the source | `test_upgrading_baseline_002_backfills_every_property_without_guessing` | killed |
| G09 aparthotel fail-closed only for legacy-only classification | APARTHOTEL_UNIT fails closed however classified | `test_an_aparthotel_unit_classified_canonically_still_fails_closed` | killed |
| G10 region filter matches the area itself, not its descendants | a region filter covers every area beneath it | `test_search_by_country_region_locality_and_area` | killed |

Not mutated (and why): G09's mirror — dropping only the `subtype` half of the
aparthotel guard — would survive, because the API always writes the legacy
`property_type` mirror as `aparthotel_unit`; the two halves are deliberate
defence in depth while the legacy column exists.

## Regression reruns

Run after the rewrite of the commit-order evidence in
`test_publication_authority_race_pg.py` and
`test_publication_proof_replacement_pg.py` (transaction id instead of
HTTP/thread completion order), to show the rewritten tests still kill what
they killed. No harness was re-pointed; every mutant applied.

* **TASK-004 A01–A09: 9 / 9 killed.** A01–A04 (a proof row left
  unprotected) are the mutants that exercise the rewritten race tests.
* **TASK-006 B01–B07: 7 / 7 killed.**
* **TASK-008 D01–D17: 17 / 17 killed; E01–E04 survived** exactly as in
  TASK-008. Per the TASK-009 adjudication carried forward, E01/E02 are
  LOAD-BEARING, E03 is TREAT AS LOAD-BEARING and E04 is schema-redundant;
  their survival is a test-evidence gap (no PostgreSQL test isolates them),
  not permission to delete them. **All four restrictions remain in the code.**
  Adding the isolating tests is carried-forward debt, not TASK-010 scope.
* Afterwards `sha256sum -c` over every tracked `app/` file: all restored.

What this does not show: that every alternative implementation would be
caught; that reference data at national scale behaves (none ingested); or
anything about production.
