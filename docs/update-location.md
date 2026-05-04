# Update County / State / Country

OpenSAK can automatically fill in the county, state, and country fields for your caches using reverse geocoding. The process runs in two phases — a fast offline pass, followed by an optional online refinement step.

---

## Opening the dialog

Click **Waypoint → Update County / State / Country**.

This option is only visible when the `update-location` feature flag is enabled. See [Feature Flags](feature-flags.md) for details.

---

## Scope options

| Option | Behaviour |
|---|---|
| **Only caches with missing location data** | Skips caches that already have all three fields filled in. Recommended for most runs. |
| **Update all caches** | Overwrites existing values for every cache in the database. |

---

## Corrected coordinates

When **Use corrected coordinates when available** is checked (the default), caches with a corrected final waypoint are looked up using those coordinates instead of the original listing coordinates. This is the correct behaviour for mystery and multi-caches where the final location differs from the published coordinates.

---

## Phase 1 — offline lookup (always runs)

Location data comes from [GeoNames](https://www.geonames.org/), a curated global geographic database bundled with the `reverse_geocoder` library. Lookups use a K-D tree that loads once in about one second and then resolves any number of coordinates instantly — no network connection required, no rate limits.

**Known limitations of Phase 1:**

- The lookup is point-based (nearest known locality), not polygon-based. Caches on or very close to an administrative boundary may resolve to the wrong side.
- GeoNames data is periodically updated but may not reflect very recent political changes (e.g. county redefinitions).
- Virginia (USA) has independent cities that are legally separate from the surrounding county. The offline lookup may assign the surrounding county instead of the correct independent city.

---

## Phase 2 — Nominatim refinement (optional, online)

When **Also refine with Nominatim** is checked, a second pass runs after Phase 1 using the [Nominatim](https://nominatim.org/) reverse geocoding API (OpenStreetMap polygon data). This provides higher-accuracy results — especially for county — because it uses actual administrative boundary polygons rather than nearest-point matching.

**Important notes:**

- Requires an internet connection.
- Rate-limited to **1 request per second** per Nominatim's usage policy. For large databases this can take a long time (e.g. ~3 hours for 10 000 caches).
- Phase 1 results are always written first. Nominatim only overwrites a field if it returns a non-empty value — Phase 1 data is never erased by a failed or empty Nominatim response.
- Progress and estimated time remaining are shown in the dialog. You can cancel at any time and keep whatever has been refined so far.

---

## Updating a single cache

Right-click any cache in the cache list and choose **Update location data…** to run the lookup for that cache only. The same corrected-coordinates logic applies, and the Nominatim checkbox is available here as well.

---

## Auto-geocode on import

When importing a GPX or PQ zip file, the import dialog shows a **Geocode missing location data after import** checkbox. When checked, OpenSAK automatically runs the offline lookup (Phase 1) for any newly imported caches that are missing location fields. This runs as part of the import flow without opening a separate dialog.
