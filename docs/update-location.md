# Update County / State / Country

OpenSAK can automatically fill in the county, state, and country fields for your caches using an offline reverse geocoding lookup. The process is instant for any database size — no network connection required.

---

## Opening the dialog

Click **File → Update County / State / Country**.

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

## Data source and accuracy

Location data comes from [GeoNames](https://www.geonames.org/), a curated global geographic database bundled with the `reverse_geocoder` library. Lookups use a K-D tree that loads once in about one second and then resolves any number of coordinates instantly.

**Known limitations:**

- The lookup is point-based (nearest known locality), not polygon-based. Caches on or very close to an administrative boundary may resolve to the wrong side.
- GeoNames data is periodically updated but may not reflect very recent political changes (e.g. county redefinitions).
- Virginia (USA) has independent cities that are legally separate from the surrounding county. The offline lookup may assign the surrounding county instead of the correct independent city.

---

## Updating a single cache

Right-click any cache in the cache list and choose **Update County / State / Country** to run the lookup for that cache only. The same scope and corrected-coordinates logic applies.

---

## Auto-geocode on import

When importing a GPX or PQ zip file, the import dialog shows a **Geocode missing location data after import** checkbox. When checked, OpenSAK automatically runs the offline lookup for any newly imported caches that are missing location fields. This runs as part of the import flow without opening a separate dialog.
