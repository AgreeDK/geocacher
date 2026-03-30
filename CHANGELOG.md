# Changelog — OpenSAK

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — In development

- HTML/PDF reports and statistics
- Improved GPS auto-detection on all Linux distros
- Windows installer (.exe)
- Linux AppImage
- More languages (German, Swedish, …)
- GitHub Actions CI/CD pipeline

---

## [1.1.0] - 2026-03-30

### Tilføjet
- GitHub Actions CI/CD pipeline — bygger automatisk til Windows, Linux og macOS
- Linux AppImage — én fil, ingen installation nødvendig
- Linux installationsscript (scripts/install-opensak.sh)
- Windows .exe bygges automatisk ved release
- macOS .dmg bygges automatisk ved release

## [0.3.0] — 2026

### Added
- **GPS export** — send caches directly to a Garmin GPS device via USB
- **Delete GPX files on device** before upload (with confirmation dialog)
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
