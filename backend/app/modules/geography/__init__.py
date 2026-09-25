"""Geography: where things are, for any European country (TASK-010).

Country → AdministrativeArea (any depth) → Locality → Address, plus GeoArea
for search areas (districts, neighbourhoods) that need not be official units,
and GeoExternalRef for authoritative identifiers (TERYT, PRG, …) that are
kept beside Homies' own ids, never instead of them.

Universal names only: `województwo`, `powiat`, `gmina` are values of
`kind_code` (PL_VOIVODESHIP, PL_COUNTY, PL_MUNICIPALITY), not entities.
"""
