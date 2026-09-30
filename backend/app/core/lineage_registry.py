"""Compatibility classification of the migrations written before PR-002.

Historical evidence, frozen: these migrations are not rewritten. Each is
classified on two independent axes (PR-002 Phase A, re-reviewed against
IBB-001):

* schema_transition — EXPAND if the release before the migration kept working
  on the schema after it; BARRIER if the step broke that release's schema
  assumptions (a one-step NOT NULL, a drop, a constraint swap) — or is the base;
* rollback_to_previous — SAFE only if running / returning to the previous
  release on the new schema reopens no fixed defect and loses no invariant.
  "Additive" does not imply SAFE: five historical steps (and TASK-014) are
  schema-compatible but rollback-BLOCKED.

The PR-002 lineage migration writes exactly these rows into `schema_lineage`
(a test pins the two to each other). Migrations from PR-002 on declare their
own `schema_transition` / `rollback_to_previous` module attributes.
"""

# revision: (schema_transition, rollback_to_previous, why)
REGISTRY: dict[str, tuple[str, str, str]] = {
    "2d9d18df4688": ("BARRIER", "BLOCKED", "base schema — there is no previous release"),
    "87cebed1635f": ("EXPAND", "SAFE", "adds disputes (legacy)"),
    "b910997aa651": ("BARRIER", "BLOCKED", "commission_bps backfill + NOT NULL in one step: old booking INSERT fails"),
    "f91f4ece13f6": ("EXPAND", "SAFE", "adds properties, classified_offers, contact_reveals"),
    "c4d2e77a1b30": ("BARRIER", "BLOCKED", "property_id NOT NULL + exclusion swap: old legacy writers fail"),
    "9010d2077493": ("EXPAND", "SAFE", "attribute catalogue table + seed"),
    "d3f81ba0c47e": ("EXPAND", "BLOCKED", "verified email/phone: the old release runs without the verified-phone gate (anti-scraping)"),
    "e5a2c91b7d34": ("EXPAND", "SAFE", "index on contact_reveals"),
    "a1c6d2e8b407": ("EXPAND", "SAFE", "money int4 → int8 widening"),
    "b7e4f19a2c60": ("EXPAND", "BLOCKED", "legal parties / authority backfill: old writers leave rows without authority (authorisation regresses)"),
    "c9d3a5e71f28": ("BARRIER", "BLOCKED", "classified_offers.space_id NOT NULL: old offer INSERT fails"),
    "d4e8b2c61a95": ("BARRIER", "BLOCKED", "price components + drop of 5 flat price columns: old SELECTs fail"),
    "f1a7c3d9e2b4": ("EXPAND", "BLOCKED", "PostGIS public point: the old read path predates location privacy"),
    "a8b2c4d6e1f3": ("EXPAND", "SAFE", "adds organisations, memberships, mandates"),
    "b3c5d7e9f1a2": ("EXPAND", "SAFE", "adds conversations, messages"),
    "c4d6e8f0a2b3": ("EXPAND", "SAFE", "adds viewings"),
    "d5e7f9a1b3c4": ("EXPAND", "SAFE", "adds file objects and media"),
    "a7c9e1f3b5d2": ("EXPAND", "SAFE", "coordinate CHECKs — fail closed for old writers"),
    "b8d0f2a4c6e1": ("EXPAND", "SAFE", "CHECK min_term >= 1 (the old floor was 6)"),
    "c1e3a5b7d9f2": ("EXPAND", "BLOCKED", "media processing_version: the old media walker serves GPS-bearing bytes (F-02)"),
    "d3f5b7a9c1e4": ("EXPAND", "SAFE", "partial UNIQUE active thread, cancelled-state CHECK — fail closed"),
    "e4f6a8b0c2d4": ("BARRIER", "BLOCKED", "properties.address_id NOT NULL + UNIQUE: old POST /properties fails"),
    "a7c9e1f3b5d7": ("EXPAND", "SAFE", "EXACT → APPROXIMATE, CHECK excludes EXACT — privacy-positive, fails closed"),
    "b8d0f2a4c6e8": ("EXPAND", "BLOCKED", "freshness: new status 'stale'; the old app cannot republish stale listings and shows past-window ones"),
    "d0f2b4c6e8a1": ("EXPAND", "SAFE", "discovery indexes only (TASK-013)"),
    "f3b5d7e9a1c2": ("EXPAND", "BLOCKED", "TASK-014 tables + public_generation (constant default): the old release publishes "
                     "without the publicity seam (no generation, no episode → missed alerts) and has no "
                     "unsubscribe endpoint for links already emailed"),
}

HISTORICAL: dict[str, tuple[str, str]] = {rev: (t, r) for rev, (t, r, _) in REGISTRY.items()}
