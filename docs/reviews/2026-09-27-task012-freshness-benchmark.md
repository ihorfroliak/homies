# Listing freshness & availability benchmark — TASK-012 (2026-09-27)

> **HISTORICAL RESEARCH** — retained for provenance. Sanitised under the D-106 research-governance policy on 2026-10-06 (TASK-016): the names of commercial platforms in the observed-pattern lists were replaced by generic market-capability references; nothing else was changed, and the original historical content remains recoverable from Git history. Non-canonical and not an implementation template. "07 §5" below refers to the benchmark method that D-106 superseded.

**Status: strategic observation, not verified fact.** Written from general
product knowledge of these marketplaces; **no live site was inspected in this
task**. Before any claim here is used externally, re-check it against the
live product and record the source URL and date (07 §5).

Method (07 §5): industry expectation → friction → Homies opportunity →
evidence Homies can measure.

| Topic | Industry expectation (observed pattern: large property-classifieds portals and mid/long-term rental platforms) | Typical friction | Homies (TASK-012) | Evidence to measure |
|---|---|---|---|---|
| Listing lifetime | Paid or time-boxed listings that expire after a fixed period; renewal is a payment or a click | Expiry is about the listing fee, not about whether the flat is still free; renters still meet let flats | Freshness = an explicit "still current" confirmation every 14 days; stale at 21 days, off the board automatically | Stale-listing rate; share of contacts on listings confirmed < 7 days ago |
| "Is it still available?" | Renters ask the owner by message; many listings answer only by silence | The most common first message is a question the platform could answer | Public `confirmed_on` + FRESH / RECONFIRM_DUE, worded as "confirmed current", not "verified" | Share of first messages asking about availability (future NLP), reply rate |
| Owner effort | Renewal flows vary; often buried in account menus | Owners forget; supply rots | One action (`confirm`), same one to come back from stale; reminder events ready for a channel | Time-to-reconfirm; reactivation rate |
| Move-in date | Usually a date field, often optional; "od zaraz" (from now) common | Missing date read as "now" by filters | Unknown stays unknown: shown as not given, excluded from an explicit `available_by` filter | Share of listings with a date; filter use |
| Listing quality | Some portals show completeness bars to owners, sometimes tied to ranking or paid boosts | Opaque scores, paid visibility | Deterministic checklist, required vs recommended, owner-only, never ranking | Completeness distribution; effect on contact rate (later) |

**Where Homies aims to be better:** freshness that means "the owner said it is
still current", not "the fee is still paid"; honesty about unknown dates; and
guidance without a hidden score. None of this is measured yet — the last
column names what to instrument from the events of D-65.
