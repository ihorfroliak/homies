# Location & search benchmark — TASK-010 (2026-09-25)

**Status: strategic observation, not verified fact.** Written from general
product knowledge of these marketplaces; **no live site was inspected in this
task**. Before any claim here is used externally (marketing, investor, SEO
copy), re-check it against the live product and record the source URL and
date (07 §5).

Method (07 §5): industry standard → competitor strength → user friction →
Homies improvement → evidence Homies will be able to measure.

| Topic | Industry standard (observed pattern) | Typical strength | Typical friction | Homies capability built / enabled | Future evidence |
|---|---|---|---|---|---|
| Place search | Free-text box with suggestions for cities, districts, regions (Otodom, OLX, idealista, ImmoScout24) | Fast entry; familiar | Suggestions mix official units and informal names inconsistently; same-name places need disambiguation | Localities with their area path ("Balice — małopolskie, krakowski, Zabierzów"); official areas and search areas kept apart (`admin_areas` vs `geo_areas`) | Suggestion-to-search conversion; zero-result rate |
| Region browsing | Pages per city/region, often SEO landing pages | Strong organic acquisition | Landing pages built on names break on renames | Stable Homies ids + slugs separate from identity; rename in place | Organic traffic per area page |
| Map | Map with viewport search and clustered pins | Visual exploration | Exact pins leak the home; approximate pins jump around | Existing privacy-reduced public point (grid, deterministic) + boundaries in PostGIS for area search | Map-to-contact rate |
| Neighbourhoods | Some portals offer neighbourhood filters in large cities | Matches how renters think | Neighbourhoods often only where the portal curated them | `geo_areas` seam for any locality, curated or sourced | Coverage of top cities; filter use |
| Address entry (owner) | Typed address, sometimes geocoder suggestions | Quick | Typos, unit mixed into street line, no verification | Structured address: locality from reference data, street/building/unit separate, resolution + source + verification recorded | Share of STRUCTURED addresses; duplicate-listing rate |
| Listing location display | City + district + approximate map | Enough to decide on a visit | Inconsistent district naming; sometimes exact street shown | `place` built only from reference entities; street/building/unit never public | Privacy incidents (target 0) |
| Cross-border | International platforms (HousingAnywhere, Spotahome, Airbnb, Booking) handle many countries | Consistent UX across countries | Country-specific address rules flattened | Any-depth hierarchy with country `kind_code`; ISO country codes; currency per country as default only | Time to add a second country (target: data only) |

**Where Homies should aim to be better, not the same:** transparent place
naming (official area path shown when it disambiguates), private-by-default
location with an explicit precision choice, and structured addresses that
make later trust signals possible (verified address, duplicate detection,
freshness). None of these is measured yet — the "Future evidence" column
names what to instrument.
