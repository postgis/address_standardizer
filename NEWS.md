# address_standardizer

## Version 3.7

2026/xx/xx

### Breaking Changes

- #6053, `address_standardizer` moved out of the main PostGIS tree into its own
  repository (Paul Ramsey)

### Bug Fixes

- Harden scanner and rule parsing bounds checks
  (reported by Eric Ridge, PlanetScale; rule-type fix by Mehmet Ince;
  fixed by Darafei Praliaskouski)
- #1599, `parse_address()` and `normalize_address()` now canonicalize trailing
  country tokens to ISO 3166-1 alpha-2 codes and expose country on normalized
  addresses (Darafei Praliaskouski)
- Standardize parsed macro components for structured parser consumers
  (Darafei Praliaskouski)
- Harden `parse_address()` input handling and state/country extraction around
  split macro components (Darafei Praliaskouski)
- Avoid potential NULL dereferences in `std_free()` and portal cache lookups
  (Maksim Korotkov)
- Fix a memory leak in `address_standardizer` error handling paths
  (Maksim Korotkov)
- Add `PG_MODULE_MAGIC` for PostgreSQL < 18 and `PG_MODULE_MAGIC_EXT` for
  PostgreSQL >= 18 builds (Regina Obe, Paul Ramsey)
