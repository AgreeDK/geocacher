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
- **Description and map not displayed on Windows 11** — fixed QWebEnginePage profile lifecycle issue that caused the description and map panels to remain blank on Windows 11 (fixes #93).
- **Qt warning at shutdown** — eliminated "Release of profile requested but WebEnginePage still not deleted" warning by ensuring proper destruction order via QApplication.aboutToQuit signal.

---

## [1.11.2] — 2026-04-26
### Fixed
- **Add GC search to Name search field** — Name search field now support both Namr and GC code search (fixes #80).

---

## [1.11.1] — 2026-04-26
### Fixed
- **Sortering huskes per database** — sorteringskolonne og retning gemmes nu
  per database i indstillingerne og genanvendes automatisk ved Refresh, genstart
  og database-skift. Tidligere nulstillede sorteringen til "Name" ved enhver
  opdatering (fixes #63).
- **Corrected coordinates vises i kolonnen** — 📍 ikonet i cache-listen vises
  nu korrekt for caches med korrigerede koordinater. Fejlen skyldtes at
  `user_note` ikke blev indlæst sammen med caches fra databasen (fixes #72).

---

## [1.11.0] — 2026-04-26
### Added
- **GUI Monkey Test in CI** — automated GUI smoke test now runs in CI on every
  push, randomly interacting with the application to catch unexpected crashes
  (PR #71, thanks @Fabio-A-Sa).
- **CI matrix expanded to Python 3.12** — both unit-tests and e2e-tests now
  run against Python 3.11 and 3.12 in parallel (PR #71, thanks @Fabio-A-Sa).

### Fixed
- **CorrectedCoordsDialog** — fixed crash caused by renamed parameters
  `corrected_lat` / `corrected_lon` not matching the updated dialog signature.

### Changed
- **Tests reorganised** — split into `unit-tests/` and `e2e-tests/` folders
  for clearer separation (PR #71, thanks @Fabio-A-Sa).

---

## [1.10.8] — 2026-04-26
### Added
- **GSAK-style container size indicator** — the container column now shows 5 segmented
  squares filling left-to-right by size: Nano=1, Micro=2, Small=3, Regular=4, Large=5.
  Virtual Cache and EarthCache display 5 empty segments with a small **V** or **E** label
  in the last segment (fixes #61, thanks hansblom for the suggestion).

### Fixed
- **Crash when clicking "Add corrected coordinates…"** — fixed a crash that occurred
  when opening the corrected coordinates dialog from the context menu (PR #69, Fabio).
- **"Dato:" hardcoded in Danish** — the date label in the log panel now uses the
  translation system correctly instead of being hardcoded in Danish (PR #65, Fabio).

### Changed
- **Reduced duplicate translation keys** — cleaned up redundant keys across all language
  files to keep translations consistent and easier to maintain (PR #67, Fabio).

---

## [1.10.7] — 2026-04-25
### Changed
- **Handle lower screen resolutions** — better view on low screen resolutions

---

## [1.10.6] — 2026-04-25
### Changed
- **Handle lower screen resolutions** — better view on low screen resolutions

---

## [1.10.5] — 2026-04-24
### Changed
- **New cache type icons** — cache icons updated for better view

---

## [1.10.4] — 2026-04-24
### Changed
- **version number in filenames** — version number should now be added to download filenames.

---

## [1.10.3] — 2026-04-24
### Changed
- **version number in filenames** — version number should now be added to download filenames.

---

## [1.10.2] — 2026-04-24
### Changed
- **Cache type column** — now shows only the cache type icon (no text); the full
  type name is visible as a tooltip on hover. Column width reduced to icon size.
- **Container column** — replaced icon with a filled horizontal bar (GSAK-style)
  showing cache size visually: Nano through Large rendered as a proportional blue bar.
- **Bearing column** — direction now displayed as compass points with degrees,
  e.g. `NØ 42°`, `S 180°`, `V 274°` (previously arrow emoji + degrees).
- **Bearing column** added to default visible columns (after Distance).
- **Flag column** — width increased slightly so the 🚩 icon is fully visible.
- **Default column order** updated to match GSAK layout:
  Flag → GC Code → Name → Type → Container → D → T → Distance → Bearing → Found → Favourite
- **Search fields** moved from the menu bar to a dedicated search toolbar on its own
  line below the main toolbar, left-aligned. Two separate fields: **GC code** (filters
  by GC number only) and **Name** (filters by cache name only).

---

## [1.10.1] — 2026-04-23
### Fixed
- **Black description and map on Windows** (issue #57) — disabled GPU acceleration
  for QtWebEngine (`--disable-gpu`) which caused silent black rendering on Windows
  systems with incomplete or virtual GPU/OpenGL drivers.
- **Incorrect 3-column layout on first launch** — splitter state is now validated
  against the current layout on restore; incompatible saved state (from older versions)
  is discarded and replaced with correct default sizes.

---

## [1.10.0] — 2026-04-23
### Added
- **GSAK field parity (issue #33)** — 11 nye felter på alle caches:
  `dnf_date`, `first_to_find`, `user_flag`, `user_sort`, `user_data_1–4`,
  `distance`, `bearing`, `favorite_points`. Tilføjes automatisk til
  eksisterende databaser ved opstart (migration 4).
- **Fundet dato** — `found_date` hentes nu fra "Found it"-logs i
  reference-databasen ved Opdater fra My Finds PQ og vises som kolonne.
- **11 nye valgfrie kolonner** i kolonnevælgeren: Fundet dato, DNF dato,
  FTF, Fav. point, Flag, Sortering, Brugerdata 1–4.
- **Geocaching brugernavn** — nyt felt i Indstillinger → Generelt til
  at gemme sit geocaching.com brugernavn (bruges til FTF-detektion m.m.).
### Fixed
- Databaser fra den gamle `geocacher/`-mappe flyttes automatisk til
  `opensak/`-mappen ved opstart.
- `found_date` skrives nu korrekt til databasen via direkte SQL
  (ORM tracking-problem med ALTER TABLE kolonner).
- Datetime-parsing af SQLite datoformater med mellemrum og mikrosekunder.

---


## [1.9.3] — 2026-04-23
### Fixed

### Multi-file import (#16)
You can now select multiple GPX or Pocket Query ZIP files at once in the
import dialog. Files are imported one by one in the background, and the
file list shows live status for each file (⏳ waiting → 🔄 importing → ✅ done).
The map and cache list update automatically when import is complete.

### Bug fix
- Map now refreshes automatically after import (previously required manual F5)

---

## [1.9.2] — 2026-04-23
### Fixed
- **Map → list sync** — clicking a pin on the map now highlights and scrolls
  to the corresponding row in the cache list (#50) — contributed by @hansblom
- **Database dialog** — the Delete button is now disabled when the active
  database is selected, preventing accidental deletion (#52)

---

## [1.9.1] - 2026-04-22

### Improved
- Expanded test coverage: added test suite for `found_updater`, Garmin GPS export,
  and `.loc` importer (thanks @Fabio-A-Sa, #54)
- Introduced shared test fixtures via `conftest.py` for better test organization
  (thanks @Fabio-A-Sa, #54)

### Fixed
- Minor corrections to Portuguese (PT) language file (thanks @Fabio-A-Sa, #55)

## [1.9.0] — 2026-04-22
### Added
- **County column** in the cache table with full filter support (#41) — contributed by @Fabio-A-Sa
  - New `county` field on the `Cache` model (database migration runs automatically on first launch)
  - Available in the filter dialog and column chooser
  - Translated into all seven languages
- **FORMAT_DD / FORMAT_DMM / FORMAT_DMS** public aliases in `coords.py` for a cleaner test API

### Fixed
- **Coordinate preview** in the status bar now respects the user's configured coordinate format (DMM/DMS/DD) instead of always displaying raw decimal degrees (#45) — contributed by @Fabio-A-Sa
- **Map widget** `Cannot use 'in' operator to search for '_leaflet_id' in undefined` error no longer occurs when interacting with the map (#47) — contributed by @Fabio-A-Sa
  - `clusterGroup.clearLayers()` replaced with recreate-on-reload pattern to avoid stale internal state
  - `panToCache()` now defensively handles markers invalidated during cluster animations

### Changed
- **Major internal refactor** — types and constants extracted into dedicated utility modules (#42) — contributed by @Fabio-A-Sa
  - New `src/opensak/utils/constants.py` (cache colours, log colours, cache types, container sizes, attributes, earth radius, waypoint prefixes)
  - Extended `src/opensak/utils/types.py` (`GcCode`, `CoordFormat`, `Coordinate`, `LogType`, `ImportType`)
  - `EARTH_RADIUS_M`, `CACHE_TYPES`, `CONTAINER_SIZES` no longer duplicated across dialog files
- **Python 3.10 support dropped** — OpenSAK now requires **Python 3.11 or newer**
  - `StrEnum` (used in `CoordFormat`) was introduced in Python 3.11
  - CI matrix updated to test only 3.11 and 3.12
  - Bundled Python in Windows / Linux / macOS installers is unaffected
- Swedish translations updated for the import dialog (#49) — contributed by @hansblom

### Tests
- **Test coverage nearly doubled: 89 → 173 tests** (#48) — contributed by @Fabio-A-Sa
  - New `tests/test_coords.py` — 257 lines covering `format_coords()` and `parse_coords()` across DD, DMM, DMS formats, hemisphere variants, boundary values and malformed input
  - New `tests/test_utils.py` — 134 lines covering GC code validation and import type detection
  - New `test_county_filter` added to `tests/test_filters.py`

### Files changed
- `src/opensak/__init__.py` (version bump)
- `pyproject.toml` (version bump, `requires-python = ">=3.11"`)
- `src/opensak/coords.py` (FORMAT_* aliases, `format_coords` now honours user setting)
- `src/opensak/db/database.py` (county migration)
- `src/opensak/db/models.py` (county field)
- `src/opensak/filters/engine.py` (county filter)
- `src/opensak/gui/cache_table.py`, `mainwindow.py`, `map_widget.py`
- `src/opensak/gui/dialogs/column_dialog.py`
- `src/opensak/importer/__init__.py`
- `src/opensak/utils/constants.py` (new), `types.py` (extended)
- All seven language files (`cs`, `da`, `de`, `en`, `fr`, `pt`, `se`)
- `tests/test_coords.py` (new), `tests/test_utils.py` (new), `tests/test_filters.py`, `tests/test_importer.py`
- `.github/workflows/ci.yml` (dropped 3.10 from matrix)

### Contributors
- **@Fabio-A-Sa** — county column, coordinate format fix, map TypeError fix, refactor, test coverage
- **@hansblom** — Swedish translation updates

---

## [1.8.1] — 2026-04-08
### Fixed
- **""Fix: Typo in Swedish translation corrected""**

---

## [1.8.0] — 2026-04-08
### Fixed
- **""Add: German language (de) to AVAILABLE_LANGUAGES""**
---

## [1.7.0] — 2026-04-07
### Fixed
- **""Add: Swedish language (se) to AVAILABLE_LANGUAGES""**

---

## [1.6.5] — 2026-04-07
### Fixed
- **"Fix: hardcoded dansih text in DB dialog close issue #28 "**

---

## [1.6.4] — 2026-04-07
### Fixed
- **"Fix: import of GPX file from gc.com with duplicated logs close issue #19 "**

---

## [1.6.3] — 2026-04-06
### Fixed
- **"Fix: Logs not displayed on cache page, close issue #18 "**
  - Strict file type validation for imports, pull request 27 by Fabio-A-Sa

### Files changed
A       .github/ISSUE_TEMPLATE/bug_report.yml
A       .github/ISSUE_TEMPLATE/feature_request.yml
A       .github/ISSUE_TEMPLATE/improvement.yml
M       .gitignore
M       CHANGELOG.md
M       src/opensak/__init__.py
M       src/opensak/api/geocaching.py
M       src/opensak/gui/dialogs/import_dialog.py
M       src/opensak/gui/mainwindow.py
M       src/opensak/lang/cs.py
M       src/opensak/lang/da.py
M       src/opensak/lang/en.py
M       src/opensak/lang/fr.py
M       src/opensak/lang/pt.py
M       src/opensak/utils/doctor.py
M       src/opensak/utils/run_cli.py
M       src/opensak/utils/run_test.py
A       src/opensak/utils/types.py
M       src/opensak/utils/utils.py
M       tests/test_languages.py

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
