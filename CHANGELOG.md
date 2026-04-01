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

## [1.3.4] — 2026
### Added
- **fix problem with import of large GSAK export**
  -

## [1.3.3] — 2026
### Added
- **fix of DT filter not displaying correctlyCorrected Coordinate**
  - ** resize and move of windows

## [1.3.2] — 2026
### Added
- **fix of DT filter not displaying correctlyCorrected Coordinate**
  - 

## [1.3.1] — 2026
### Added
- **Corrected Coordinate** — new option to add corrected coordinate to caches:
  - add corrected coordinate to the cache
  - show the corrected waypoint on maps
  - use corrested coordinate in GPS upload

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
- French language (`lang/fr.py`) — contributed by Pierre LEJEUNE (@theyoungstone)
- `CONTRIBUTORS.md` — contributor credits

### Fixed
- Version number in About dialog is now read dynamically from `__init__.py` — no longer hardcoded in translation files
- Filter dialog now opens tall enough to show all options without manual resizing
- GC code placeholder in filter dialog is now translated
- Red "no device" hint text in GPS dialog now wraps correctly instead of being truncated
- All hardcoded Danish strings in waypoint dialog replaced with `tr()` calls — labels, placeholders and checkboxes are now fully translated
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
- **Filter toolbar** — 🔍 Filter (Ctrl+F) and ❌ Clear filter
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
