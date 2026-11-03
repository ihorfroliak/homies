# Kraków official district geometry — FE-VIS-001B

Founder decision 2026-11-03: use official districts and exact geography,
superseding the original Home Mapa export's 13 schematic shapes.

Source: Gmina Miejska Kraków, Portal MSIP Obserwatorium,
[dataset 1483](https://msip.krakow.pl/dataset/1483), published by the city
Geodesy Department. Download:
https://msip.um.krakow.pl/Dane/Dzielnice_JSON.zip

Retrieved 2026-11-03. Archive SHA-256:
`5fca108c88267cb35816d5fa68cda9ca07fa776d2fb9532bfd5ecae076bb2b37`.
The archive's `__Aktualnosc__.txt` reports generation **2025-12-05_10:00:39**.
This is the source package vintage, not a claim of November 2026 freshness.
The archive is preserved unchanged. 18 Polygon features, official numeric
and Roman district identifiers, source CRS EPSG:2178; GeoJSON coordinates
are easting then northing. No listing or address data.

## Reproduction

Run `python frontend/web/scripts/build-krakow-districts.py` from the repository,
or add `--check` to verify the checked-in output. Python standard library only.
Pinned archive hash, CRS, identifiers 1–18, closed finite rings and coordinate
bounds are validated before writing. Every source vertex and ring is retained.
Uniform scale to a 1000-unit-wide SVG and north-up y reflection; 4 decimal
rounding only (maximum coordinate displacement under 0.003 metres).
No polygon simplification, geographic inference, runtime network, map tiles
or imported JavaScript from the design export. Interior label points are
computed separately and do not change the boundaries. Colours are place
identity only, retaining the export's hues where names correspond.

## Reuse basis and attribution

Sources inspected 2026-11-03:

- [MSIP terms, 2025-10-29](https://msip.krakow.pl/getHtml?dok_id=228972).
- [MSIP-specific reuse rules, updated 2026-02-26](https://www.bip.krakow.pl/?dok_id=56559&metka=1).
- [General municipal reuse rules](https://www.bip.krakow.pl/?dok_id=48482), linked by the preceding rules for other cases.

The dataset explicitly identifies the downloadable file as OpenData. Engineering
reuse assessment: this is a one-time downloadable dataset rendered locally,
not redistribution or continuous embedding of a REST/WMS/WFS/WMTS map service
(which has separate restrictions under MSIP terms 8–9). General rules II–III
provide for reuse with source, creation/retrieval dates, transformation and
responsibility information. The app's `/zrodla/mapa-krakowa` page provides those
details and links the full official conditions; the map links to that page.
This assessment does not authorize a hosted municipal map service, and is not
a claim that the download has a named CC/ODbL licence. No paid provider involved.

## Search boundary — intentionally unresolved

Current `GeoArea` can be DISTRICT, NEIGHBOURHOOD or SEARCH_AREA. The existing
synthetic rows Stare Miasto, Krowodrza, Podgórze and Kazimierz are all
NEIGHBOURHOOD. `properties/search.py` filters exact Address.geo_area_id;
there is no district containment expansion. Name/slug equality is therefore
not proof of an official district's extent. Linking district I to the existing
Stare Miasto row would omit Kazimierz listings.

This increment makes all 18 official districts inspectable and selectable,
explicitly says that full-district search is pending, retains separate existing
neighbourhood links and the city search, and emits no fabricated counts.
No automatic name-to-slug match and no relabelling of seeded geography.
Next bounded geography work must establish official source identity, verified
address/district membership and privacy-safe search semantics, including
Kazimierz-within-district-I and border cases, before enabling district links.
This is a delivered orientation increment, not full HM-1 search completion.
