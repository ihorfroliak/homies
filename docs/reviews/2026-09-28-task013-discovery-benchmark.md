# Discovery / search / map benchmark — TASK-013 (2026-09-28)

> **HISTORICAL RESEARCH** — retained for provenance. Sanitised under the D-106 research-governance policy on 2026-10-06 (TASK-016): the names of commercial platforms in the observed-pattern lists were replaced by generic market-capability references; nothing else was changed, and the original historical content remains recoverable from Git history. Non-canonical and not an implementation template. "07 §5" below refers to the benchmark method that D-106 superseded.

**Status: strategic observation, not verified fact.** Written from general
product knowledge of these marketplaces; **no live site was inspected in this
task**. Re-check against the live products, with URL and date, before any
external use (07 §5).

| Topic | Industry standard (large property-classifieds portals and mid/long-term rental platforms) | Competitor strength | User friction | Homies (TASK-013) | Measurable improvement |
|---|---|---|---|---|---|
| List + map | Split list/map on desktop, toggle on mobile; "search this area" | Visual exploration | Map and list often disagree after panning; markers for listings the list excludes | One query model; the map reports how many matches have no point and whether it truncated | Share of sessions using the map; map→detail rate |
| Price filter | One "price" field, often rent only | Simple | Fees and utilities discovered later; filter lies about affordability | Rent, stated monthly total and move-in total as separate filters; utilities basis shown | Contact rate on listings within budget; complaints about hidden costs |
| Freshness | Listing age or "updated" dates; stale ads linger | Volume | Renters contact let flats | Only listings confirmed current within 21 days are searchable (TASK-012) | Share of contacts on listings confirmed < 7 days |
| Location privacy | Exact pins or approximate circles, varying by portal | Precise orientation | Exact pins expose homes; approximate pins sometimes still searchable exactly | Map and spatial search both use the public grid point only | Privacy incidents (target 0) |
| Availability | "Available from" often optional; "od zaraz" | Quick | Missing dates read as "now" | Unknown stays unknown and never matches a date filter | Share of listings with a stated date |
| Sorting | "Promoted" first, then newest/price | Revenue | Opaque order, paid placement | No hidden ranking; deterministic sorts; confirmation never bumps order | Complaints about ranking (target 0) |
| Shareable searches | URL parameters on most portals | Linkable | Long, unstable URLs | Canonical query string returned by every search | Saved-search conversion (TASK-014) |
