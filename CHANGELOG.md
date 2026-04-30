# Changelog — OpenSAK
All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — In development
- HTML/PDF reports and statistics
- Improved GPS auto-detection on all Linux distros
- More languages (generated via Claude API, community proofread)
- Favourite points (requires Geocaching.com API)
- Multi-threading import performance (PR #30, planned for v1.10.0)
- Main window layout redesign: full-width cache list on top, details + map below (issue #33)

---

## [1.11.17] — 2026-04-30
### Added
- **Where-filter** (closes #17) — a powerful SQL-based OR filter that mirrors GSAK's
  "Where" functionality. Instead of chaining multiple passes through the database,
  a single filter expression combines any number of conditions (cache type, D/T,
  hidden date, size, attributes, …) into one efficient query. Contributed by Fabio.
- **Database switcher dropdown** in the toolbar (closes #17) — switch between databases
  directly from the toolbar without opening the Database Manager dialog. The active
  database is always pre-selected; choosing another entry switches immediately.
  Contributed by Fabio.

---

## [1.11.16] — 2026-04-30
### Added
- **Custom Waypoint support** (fixes #141) — the Add/Edit cache dialog now supports
  two modes selected via radio buttons at the top:
  - **Geocache** — existing behaviour; GC code and D/T are validated strictly.
  - **Custom Waypoint** — for personal points of interest such as parking spots,
    hotel stays, multi-cache stages or anything else that is not a geocache.
    The waypoint receives an auto-generated ID (`CW001`, `CW002`, …) and a dedicated
    type dropdown (Parking Area, Trailhead, Stage, Final Location, Reference Point,
    Waypoint, Hotel/POI, Custom). D/T, Container and the Status tab are hidden as
    they are not relevant for custom waypoints.
- **"Belongs to cache" field on Custom Waypoints** — an optional GC code field lets
  you link a custom waypoint to a specific geocache (e.g. a parking coordinate for
  GC12345). This is validated on save (must start with `GC` if filled in) and stored
  in the new `parent_gc_code` column, making the connection explicit in the database —
  something that was not possible in GSAK.

### Fixed
- **Invalid D/T values accepted** (part of #141) — Difficulty and Terrain fields in
  Geocache mode now validate that the entered value is one of the official Groundspeak
  ratings (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0). Previously it was possible
  to save illegal values such as 1.7 by typing them directly into the spin box.

### Changed
- **`parent_gc_code` column added to `caches` table** — Migration #8 adds the column
  automatically on first launch. No re-import required. The column is `NULL` for all
  existing geocaches.
- **8 new translation keys** added to all 7 language files (da, en, fr, de, cs, pt, se).

---

## [1.11.15] — 2026-04-30
### Fixed
- **Missing cache types in filter dialog** (fixes #132) — Cache In Trash Out Event, Lab Cache,
  Community Celebration Event, Geocaching HQ Cache, Geocaching HQ Celebration,
  Geocaching HQ Block Party, Project A.P.E. Cache and Locationless (Reverse) Cache
  were missing from the cache type filter. All 21 official Groundspeak cache types
  are now listed.
- **Corrected coordinates not imported from GSAK** (fixes #129) — Corrected coordinates
  saved in GSAK (`<gsak:LatN>` / `<gsak:LongE>` inside `<gsak:wptExtension>`) are now
  read during GPX import and stored in the cache's UserNote. A value of 0.0/0.0 (GSAK's
  default when no correction is set) is correctly ignored. Existing corrected coordinates
  survive a re-import from a plain geocaching.com GPX file.
- **Container sort order** (fixes #133) — Container column now sorts logically by physical
  size (Micro → Small → Regular → Large) rather than alphabetically. Non-physical types
  (EarthCache, Lab Cache, Virtual, Other) follow in alphabetical letter order (E → L → O → V),
  with empty/not-chosen last.
- **Trip Planner opens multiple windows** (fixes #134) — Opening the Trip Planner while it
  is already visible no longer opens a second window. The existing window is brought to
  the front instead.
- **Missing geocache attributes** (fixes #139) — Eight attribute IDs missing from the
  attributes list have been added: First Aid nearby (38), Livestock nearby (39),
  Flashlight required (42), Fuel nearby (54), Food nearby (55), Wireless Beacon (56),
  Significant Hike (59) and Tourist Friendly (61). IDs 42, 54, 55, 59 and 61 are legacy
  GPX IDs that map to existing attributes; 38, 39 and 56 are new entries with translations
  in all 7 languages.

### Changed
- **Nano container size removed** — "Nano" is not an official Geocaching.com container size
  (it is an informal term for very small Micro caches < 10 ml). Geocaching.com always exports
  these as "Micro". Migration #7 automatically converts any existing `container = 'Nano'`
  values to `'Micro'` in all databases on first launch.

---

## [1.11.14] — 2026-04-29
### Fixed
- issue #130: Deleting a database on Windows no longer fails with WinError 32 ("file in use by another process"). SQLite WAL-mode keeps .db, .db-shm and .db-wal files locked as long as the SQLAlchemy connection pool is open. The fix disposes the engine and releases all file handles before attempting deletion, then forces garbage collection and a short delay to give Windows time to free the handles.

---

## [1.11.13] — 2026-04-29
### Fixed
---
- issue 128: Filter no longer dropped when returning from Settings (#128)
When an advanced filter was active and the user opened and closed the Settings or Preferences dialog, the cache list was refreshed without reapplying the active filter — causing it to appear dropped even though it was still selected in the filter dialog.

The root cause was that _refresh_cache_list() only considered the quick-filter and search fields when rebuilding the filter, ignoring _current_filterset entirely. The fix combines both the advanced filter and the quick-filter/search into a single AND-condition on every refresh, so the active filter is always preserved regardless of what triggers the reload.

## [1.11.12] — 2026-04-29
### Fixed
- issuex #112: Cache selection highlight is now consistent across all platforms. On Windows 10/11 the selected row was shown in gray (system default), making it hard to distinguish from archived caches. The highlight color is now always light blue, matching the appearance on Linux and macOS.
- issue #121: Creating a new database in a custom folder now works correctly. The folder browser has been changed from a "Save file" dialog to a "Select folder" dialog, eliminating the confusion where nothing happened if no filename was typed. The full file path (folder + database name + .db) is now shown as a live preview while typing the name.

---

## [1.11.11] — 2026-04-29
### Fixed

- GC Code and Name search fields now sit directly next to their labels
- no more blank space between label and input box.

### Improved

- Version number is now shown in the splash screen at startup.
- Version number is now shown in the main window title bar.
- app.setApplicationVersion now uses the actual version from __version__ instead of a hardcoded value.

---

## [1.11.10] — 2026-04-29
### Fixed
- Fix: database delete removes shm/wal files (#120) , translate all error messages
- Fix: validate path permissions (#121)
- translate all error messages

---

## [1.11.9] — 2026-04-28
### Fixed
- Fixed crash when deleting caches: child records (logs, attributes, trackables, waypoints, user notes) are now deleted before the parent cache to prevent FOREIGN KEY constraint errors and orphaned data
- Fixed GPX/PQ re-import failing with UNIQUE constraint errors on logs when importing into a database with existing data — caused by orphaned log records from previous cache deletions
- Import now uses SAVEPOINT per cache so a single failing cache no longer rolls back the entire batch
- Fixed RuntimeError in terminal when closing the import dialog after import completes (C++ worker object already deleted)

---

## [1.11.8] — 2026-04-28
### Added
- **Check for latest release** when loading program, its check to see if a new version exist.
  - Check for updates have been added to the Help menu.

---

## [1.11.7] — 2026-04-28
### Added
- **GSAK-style info bar** between cache list and detail/map panel (fixes #116):
  - Active filter name or "None"
  - Total caches in the current database
  - Number of flagged (🚩) caches
  - Active center/home point name
  - Color-coded counts: Found (yellow), All in filter (white), Archived + Deactivated (red), User-owned caches (green)
  - Updates automatically on filter change, database switch, import, and flag toggle
  - Owned cache count matches `placed_by` against stored GC username
- 9 new translation keys added to all 7 language files (da, en, fr, de, cs, pt, se) with proper translations

---

## [1.11.6] — 2026-04-27

### Fixed 
- **FTF false positives - only detect on user's own flag** 
  fixes issue #114 and implement issue #58

---

## [1.11.5] — 2026-04-27
### Added
- **Latitude and Longitude as selectable columns** — new optional columns
  in the cache list show coordinates per cache. Format respects the user's
  coordinate format setting (DD/DMM/DMS) so values match the detail panel.
  Shows corrected coordinates when set (matches map behaviour). Tooltip
  indicates whether coordinates are original or corrected (fixes #84,
  thanks @hansblom for reporting).
- **`format_lat()` and `format_lon()` helpers** in `coords.py` — new
  single-axis formatters used by the Latitude/Longitude columns.
- **Lab Cache 'L' label** — Lab Caches now display empty bars + 'L' in the
  Container column, consistent with Virtual ('V') and EarthCache ('E').

### Fixed
- **Container column sorts by size, not alphabetically** — sorting the
  Container column now produces a logical order grouped by visual style:
  physical containers first (Nano → Micro → Small → Regular → Large), then
  letter-display types alphabetically (E → L → O → V), then empty
  ("Not chosen"). Stable sort preserves a previous secondary order such
  as Distance (fixes #90, thanks @Fabio-A-Sa for reporting).
- **'Other' container visualisation** — was showing 3 filled bars (visually
  identical to Small); now shows 5 empty bars + 'O' label, consistent with
  V/E/L (part of #90).
- **Log count column always 0** — added `log_count` as a cached column on
  the Cache model so the count is available without loading the logs
  relationship (which is `noload`'ed for performance). Migration #6
  populates `log_count` from existing logs on first startup, so existing
  databases show correct counts immediately without re-import (fixes #87,
  thanks @Fabio-A-Sa for reporting).
- **Search field rollback to GSAK-style separate fields** — Name search
  field now searches only cache names (not GC codes too). GC code search
  remains in its own dedicated field. Restores GSAK convention of clear,
  single-purpose search fields (fixes #86, thanks @Fabio-A-Sa for
  reporting; rolls back the combined search added in #80).

### Changed
- **Search toolbar always visible** — the search toolbar can no longer be
  accidentally hidden via the right-click context menu. Forced visible at
  startup to recover from any previously hidden state in QSettings. The
  search bar is essential UI and is planned to host more fields in future.

---

## [1.11.4] — 2026-04-27
### Fixed
- **Version number mismatch** — fixed `__init__.py` to correctly report version 1.11.4 (the v1.11.3 tag was created with `__version__` still set to "1.11.2"; this release brings the version string in sync with the release tag).

---

## [1.11.3] — 2026-04-27
### Fixed
- Fixed duplicate search fields showing in the search toolbar after opening and closing the Column Chooser dialog. The root cause was that `_setup_search_toolbar()` was called every time the toolbar was rebuilt, appending a new set of widgets on top of the existing ones. The fix clears the toolbar before rebuilding.

---

## [1.11.2] — 2026-04-26
### Fixed
- Fixed a crash on startup when no database is selected: `_refresh_cache_list()` and `_update_status_bar()` now guard against a `None` active database path.
- Fixed `status_db_caches` translation key missing in all 7 language files — caused `pytest test_no_missing_keys` to fail.

---

## [1.11.1] — 2026-04-26
### Fixed
- Restored missing import of `QApplication` in `app.py` — caused an immediate crash on startup after the v1.11.0 refactor.

---

## [1.11.0] — 2026-04-26
### Added
- **Fabio's CI/CD refactor** — unit tests and end-to-end tests are now split into separate directories (`tests/unit-tests/` and `tests/e2e-tests/`). GitHub Actions runs unit tests on every push and e2e tests on version tags only.

---

## [1.10.2] — 2026-04-25
### Fixed
- Fixed GPX import crash when `<groundspeak:long_description>` or `<groundspeak:short_description>` elements are missing from a cache entry — `AttributeError: 'NoneType' object has no attribute 'text'`.

---

## [1.10.1] — 2026-04-25
### Fixed
- Fixed import of multiple GPX files (issue #16) — previously only the first file in a multi-file selection was imported; remaining files were silently skipped due to the `QFileDialog` return value not being iterated correctly.

---

## [1.10.0] — 2026-04-25
### Added
- **Import multiple GPX files at once** (issue #16) — the import dialog now accepts a multi-file selection. Each file is imported in sequence with a combined progress bar and a summary report at the end listing per-file results (new, updated, skipped, errors).

---

## [1.9.2] — 2026-04-24
### Fixed
- **Map pin click scrolls to correct cache** (fixes #50) — clicking a pin on the map now selects and scrolls to the matching cache in the list. Previously the selection landed on a wrong row because the map used the raw list index rather than looking up the cache by GC code.
- **Delete button disabled for active database** (fixes #52) — the Delete button in the database manager is now disabled when the selected database is the currently active one, preventing accidental deletion of the open database.

---

## [1.9.1] — 2026-04-23
### Fixed
- Fixed crash when switching databases while a filter was active — `apply_filters()` now always receives a valid session.

---

## [1.9.0] — 2026-04-23
### Added
- **Trip Planner** — plan a geocaching outing directly in OpenSAK:
  - Radius search from home point with configurable distance
  - Route planning (A → B → … up to 10 waypoints) with caches sorted in driving order
  - Filters: max count, not-found only, available only
  - Show selected caches on an interactive OSM map
  - Export directly to GPS or GPX file

---

## [1.8.0] — 2026-04-22
### Added
- **Home points list** — replace single home coordinate with a named list (Home, Cottage, Hotel, …). Quick-switch dropdown in the toolbar.

---

## [1.7.0] — 2026-04-21
### Added
- **GSAK field parity** (issue #33) — migration adds `dnf_date`, `first_to_find`, `user_flag`, `user_sort`, `user_data_1–4`, `distance`, `bearing`, `favorite_points` columns to existing databases.

---

## [1.6.0] — 2026-04-20
### Added
- **Geocaching Tools menu** — Coordinate Converter, Projection, Digit Checksum, Midpoint, Distance & Bearing.
- **Coordinate format preference** — DMM (default), DMS or DD.

---

## [1.5.0] — 2026-04-18
### Added
- **Corrected Coordinates** — add solved coordinates to mystery caches; shown on map with orange pin; used in GPS export.

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
