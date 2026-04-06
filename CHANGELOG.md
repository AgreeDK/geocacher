# Changelog — OpenSAK
All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — In development
- HTML/PDF reports and statistics
- Improved GPS auto-detection on all Linux distros
- More languages (German, Swedish, …)
- Favourite points (requires Geocaching.com API)

---

## [1.6.2] — 2026-04-06
### Fixed
- **"Fix: remove duplicate key and translate missing French strings in fr.py"**
---

## [1.6.1] — 2026-04-06
### Fixed
- **GPX import: large files no longer freeze** — debug code removed
---

## [1.6.0] — 2026-04-06
### Fixed
- **GPX import: large files no longer freeze** — complete rewrite of import engine:
  - Caches are now committed to database in batches of 200 instead of one giant transaction
  - Waypoint lookup uses a single in-memory dict instead of 11,000 individual LIKE queries (3 min → 3 sec)
  - `apply_filters()` no longer eager-loads logs/waypoints/user_note for all caches — loaded on-demand when a cache is selected
  - Table reload after import skips map update — map updates lazily when a cache is clicked
  - Successfully tested with 53,415 caches and 19,644 waypoints from a full GSAK export
- **GPX import: 0 skipped waypoints** — extra waypoints with unknown prefix formats (e.g. `JJ28J63`, `Q14N2QD`) are now correctly parsed using the `Waypoint|type` field
- **GPX import: duplicate waypoints** — GSAK exports sometimes include each waypoint twice; duplicates are now deduplicated before insert
- **GPX import: UNIQUE constraint on logs** — all negative GSAK dummy log IDs (−2, −3, …) are now treated as dummy and given a generated unique ID
- **Database migration** message no longer repeats on startup

### Changed
- Live progress counter shown in import dialog during large imports
- Import dialog shows "Saving to database…" during final commit phase
- After import, status bar shows cache count and prompts user to click a cache to view map

### Files changed
- `src/opensak/importer/__init__.py`
- `src/opensak/filters/engine.py`
- `src/opensak/db/database.py`
- `src/opensak/gui/dialogs/import_dialog.py`
- `src/opensak/gui/mainwindow.py`
- `src/opensak/lang/da.py`, `en.py`, `fr.py`, `pt.py`, `cs.py`

---

## [1.5.2] — 2026-04-05
### Fixed
- **Coordinate parser** now accepts the geocaching.com copy-paste format `N 34° 58.088' E 034° 03.281'` (DMM with degree sign and apostrophe) — no manual editing required (fixes #9)
- **Edit cache dialog** — coordinates are now displayed in the user's chosen format (DMM/DMS/DD) instead of raw decimal degrees; accepts all supported formats including paste from geocaching.com

### Files changed
- `src/opensak/coords.py`
- `src/opensak/gui/dialogs/waypoint_dialog.py`

---

## [1.5.1] — 2026-04-05
### Added
- **Fix: import GPX from GSAK** — fix issue with multiple WP

---

## [1.5.0] — 2026-04-05
### Added
- **Trip Planner: Save to database** — export selected trip caches directly to a new or existing OpenSAK database:
  - Choose between creating a new `.db` file or adding to an existing one
  - Duplicate GC codes are automatically skipped; a summary shows how many were added vs. skipped
  - File dialog opens in the same folder as the active database for easy access
- **Trip Planner: Live map updates** — the map preview now refreshes automatically whenever the cache selection changes (count, filters, radius, route), no need to close and reopen the map

### Fixed
- **Trip Planner: Map preview** is now a fully interactive, independent window — zoom, pan and cache popups work correctly; the window no longer stays locked behind the Trip Planner dialog
- **Trip Planner** is now non-blocking (`show()` instead of `exec()`) so the map window and the planner can be used side by side

### Changed
- All five language files updated with new Trip Planner strings (`da`, `en`, `fr`, `pt`, `cs`)

### Files changed
- `src/opensak/gui/dialogs/trip_dialog.py`
- `src/opensak/gui/mainwindow.py`
- `src/opensak/lang/da.py`, `en.py`, `fr.py`, `pt.py`, `cs.py`

---

## [1.4.8] — 2026-04-04
### Added
- **Attributes** updated thanks to Pierre Lejeune

---

## [1.4.7] — 2026-04-04
### Added
- **Icons** app Icons fix & update

---

## [1.4.6] — 2026-04-04
### Added
- **Icons** app Icons added

---

## [1.4.5] — 2026-04-04
### Added
- **Fixed** import result dialog now uses i18n strings (fixes #7)

---

## [1.4.4] — 2026-04-04
### Added
- **Czech translation** (`lang/cs.py`) — contributed by Michal Gavlík

---

## [1.4.3] — 2026
### Fixed
- Security improvements and minor bug fixes

---

## [1.4.2] — 2026
### Fixed
- GPX import: added support for `groundspeak/cache/1/0` namespace (used by My Finds PQ), resolving issue #2

---

## [1.4.1] — 2026
### Added
- **Portuguese translation** (`lang/pt.py`) — contributed by Fabio
- Translation completeness tests added

---

## [1.4.0] — 2026
### Added
- **Trip Planner** — new dialog to plan a geocaching trip:
  - **Radius tab** — select caches within a set distance from the active home point; sort by distance, difficulty, terrain, date or name
  - **Route tab (A→B→…)** — find caches along a multi-point route (up to 10 waypoints); caches sorted in driving order along the route
  - Route points can be typed in any coordinate format (DMM, DMS, DD) with live validation, or picked directly from saved home points
  - Route points can be reordered with ▲/▼ buttons or drag-and-drop
  - Common filters: max cache count, not-found only, available only
  - **🗺️ Show on map** — opens a non-blocking map popup showing selected caches on an interactive OSM map
  - Export selected caches directly to GPS device or GPX file
- **Home points list** — replace single home coordinate with a named list (e.g. Home, Cottage, Hotel):
  - Add, edit, activate and delete points from Settings
  - Accepts any coordinate format (DMM, DMS, DD) with live validation; displays in your chosen format
  - Active point marked with ★ in the list
  - **Quick-switch dropdown** in the toolbar — switch active home point instantly without opening Settings
  - Distance column and trip planner update immediately when home point changes

### Fixed
- Settings menu renamed from "Tools" to "Settings" to avoid duplicate "Tools" entry in menu bar

---

## [1.3.5] — 2026
### Added
- Corrected coordinates now included as a filter option in the filter dialog

---

## [1.3.4] — 2026
### Fixed
- Import of large GSAK exports no longer fails

---

## [1.3.3] — 2026
### Fixed
- D/T filter not displaying correctly on smaller screens
- Filter dialog resize and move behaviour corrected

---

## [1.3.2] — 2026
### Fixed
- D/T filter display issue
- Corrected coordinate display in detail panel

---

## [1.3.1] — 2026
### Added
- **Corrected Coordinates** — add solved coordinates to mystery caches:
  - Add corrected coordinate via right-click menu or detail panel
  - Corrected waypoint shown on map with orange pin overlay
  - Corrected coordinate used in GPS export

---

## [1.3.0] — 2026
### Added
- **Geocaching Tools menu** — new dedicated menu in the menu bar with five geocaching utilities:
  - **⇄ Coordinate Converter** (`Ctrl+K`) — convert between DD, DMM and DMS; open result in map
  - **📐 Coordinate Projection** (`Ctrl+P`) — project a new coordinate from start point, bearing and distance
  - **🔢 Digit Checksum** — sum all digits in a coordinate; shows N/S and E/W parts separately
  - **⊕ Midpoint** — calculate the great-circle midpoint between two coordinates
  - **📏 Distance & Bearing** — distance and azimuth (both directions) between two coordinates
- **Coordinate format preference** in Settings — choose between DMM (default, geocaching standard), DMS and DD
- **Coordinate converter button** (⇄) in the cache detail panel next to coordinates
- All tools pre-fill with the currently selected cache's coordinates where applicable

---

## [1.2.1] — 2026
### Fixed
- macOS release now ships as two separate installers (arm64 and x86_64) instead of a Universal Binary that exceeded GitHub's 2 GB file size limit

---

## [1.2.0] — 2026
### Added
- **French translation** (`lang/fr.py`) — contributed by Pierre LEJEUNE (@theyoungstone)
- `CONTRIBUTORS.md` — contributor credits

### Fixed
- Version number in About dialog now read dynamically from `__init__.py` — no longer hardcoded in translation files
- Filter dialog now opens tall enough to show all options without manual resizing
- GC code placeholder in filter dialog is now translated
- Red "no device" hint text in GPS dialog now wraps correctly instead of being truncated
- All hardcoded Danish strings in waypoint dialog replaced with `tr()` calls
- Cancel/Save buttons in waypoint dialog now translated correctly in all languages

### Changed
- Default language on first launch changed from Danish to English

---

## [1.1.0] — 2026
### Added
- **GitHub Actions CI/CD pipeline** — automatic builds on version tag push
- **Windows installer** — `.exe` packaged with PyInstaller, distributed as `.zip`
- **Linux AppImage** — single-file executable for all major distributions
- **macOS installer** — `.dmg` for Apple Silicon (arm64) and Intel (x86_64)
- **GPS export** — send caches directly to a Garmin GPS device via USB
- **Delete GPX files on device** before upload (with confirmation dialog and file list)
- **Save as GPX file** — export to any local path
- **Language support** — Danish and English built in; easily extensible
- **Language switcher** in Settings dialog — takes effect on next restart
- i18n engine (`tr()`) covering all ~220 UI strings across the entire application

---

## [0.2.0] — 2026
### Added
- **Advanced filter dialog** with 3 tabs (General, Dates, Attributes)
- **Filter toolbar** — 🔍 Filter (`Ctrl+F`) and ❌ Clear filter
- **ROT13 hint decoding** — one click to decode / re-hide
- **Search in logs** with real-time match highlighting
- **Status icons** — ✅ found, ❌ DNF, 🔒 archived, ⚠️ unavailable
- **Click GC code** → opens cache page on geocaching.com
- **Click coordinates** → opens in preferred map app
- **Right-click context menu** in cache list
- **Configurable map app** — Google Maps or OpenStreetMap
- **Update finds from reference database** (My Finds PQ workflow)
- **Favourite ★ column**
- **Waypoint CRUD** — add, edit and delete caches manually
- **Column chooser** — 17+ columns, toggle on/off

---

## [0.1.0] — 2026
### Added
- Import GPX files and Pocket Query ZIP files
- SQLite database with all Groundspeak fields
- Multiple databases with manager dialog
- Centre point per database
- Filter engine with 18 filter types and AND/OR nesting
- Saved filter profiles
- Interactive OSM map with colour-coded pins and clustering
- Cache detail panel with description, hints and logs
- Settings — home coordinates, distance unit, map app
