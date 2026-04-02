# OpenSAK — Open Source Swiss Army Knife for Geocaching

A modern, cross-platform geocaching management tool for **Linux**, **Windows** and **macOS** — a free, open source successor to GSAK, built in Python.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Beta-orange)

---

> **⚠️ Hobby Project Notice**
>
> This project is developed in my spare time as a personal hobby project.
> Bug reports and suggestions are welcome via GitHub Issues, but responses
> and updates are not guaranteed. Development happens when time and interest allow.
>
> Pull requests are welcome, though they may not always be reviewed or merged.
>
> The software is provided as-is, without warranty or guaranteed support.

---

## Features

### Import & Database
- 📥 **Import** GPX files and Pocket Query ZIP files from Geocaching.com
- 🗄️ **Multiple databases** — keep regions separate (e.g. Zealand, Bornholm, Cyprus)
- 📍 **Home points** — save multiple named home points (Home, Cottage, Hotel…) and switch instantly from the toolbar
- ✅ **Update finds** from a reference database (e.g. your "My Finds" PQ)

### Trip Planning
- 🗺️ **Trip Planner** (`Ctrl+T`) — plan a geocaching trip in two modes:
  - **Radius** — find caches within a set distance from your active home point; sort by distance, difficulty, terrain, date or name
  - **Route A→B→…** — find caches along a multi-point route (up to 10 waypoints); caches sorted in driving order along the route
- Route points can be typed in any coordinate format or picked from your saved home points
- **Preview on map** — open selected trip caches on an interactive map with one click
- Export trip caches directly to GPS or as a GPX file

### View & Navigation
- 🗺️ **Interactive map** with OpenStreetMap and colour-coded cache pins with clustering
- 🔍 **Advanced filter dialog** — 3 tabs: General, Dates and Attributes (~70 Groundspeak attributes)
- 📊 **Configurable columns** — 17+ columns, toggle on/off
- 🎨 **Status icons** in list — ✅ found, ❌ DNF, 🔒 archived, ⚠️ unavailable
- 🔗 **Click GC code** → opens cache page on geocaching.com
- 🗺️ **Click coordinates** → opens in Google Maps or OpenStreetMap

### Cache Details
- 📋 **Cache details** — description, hints and logs
- 🔓 **ROT13 hint decoding** — one click to decode / re-hide the hint
- 🔍 **Search in logs** — real-time search with match highlighting
- 📍 **Corrected coordinates** — store solved puzzle coordinates per cache; used in GPS export and shown on map
- ✏️ **Add / edit / delete** caches manually

### Right-click Menu
- 🌐 Open on geocaching.com
- 🗺️ Open in map app (Google Maps / OpenStreetMap)
- 📋 Copy GC code / coordinates (in your chosen format)
- ☑ Mark as found / not found
- 📍 Add / edit / clear corrected coordinates
- ⇄ Open coordinate converter directly from the cache list

### GPS Export
- 📤 **Send to Garmin GPS** — auto-detects USB-mounted Garmin devices
- 🗑️ **Optional: delete existing GPX files** on device before upload
- 💾 **Save as GPX file** — export to any location

### Geocaching Tools
- **⇄ Coordinate Converter** — convert between DD, DMM and DMS formats with one click
- **📐 Coordinate Projection** — calculate a new coordinate from bearing and distance
- **🔢 Digit Checksum** — sum all digits in a coordinate (N/S and E/W separately)
- **⊕ Midpoint** — find the great-circle midpoint between two coordinates
- **📏 Distance & Bearing** — distance and azimuth between two coordinates
- All tools open pre-filled with the currently selected cache's coordinates

### Language Support
- 🌍 **Danish, English and French** built in
- 🔧 **Easy to add new languages** — copy one file, translate, done

---

## Known Limitations (Beta)

- Favourite points cannot be imported from GPX/PQ files (requires Geocaching.com API)
- No Geocaching.com Live API integration
- GPS auto-detection on Linux may not find all Garmin devices automatically
- macOS builds are not signed with an Apple Developer certificate (right-click → Open on first launch)

---

## System Requirements

| Platform | Requirement |
|---|---|
| **Linux** | Ubuntu 20.04+ / Linux Mint 20+ / Debian 11+ |
| **Windows** | Windows 10 or newer |
| **macOS** | macOS 11 (Big Sur) or newer |
| **Python** | 3.10 or newer |
| **Disk space** | ~500 MB (including PySide6) |

---

## Installation

### 🐧 Linux — Automatic installer (recommended)

The easiest way to install OpenSAK on Linux. The script installs all dependencies,
downloads OpenSAK, and creates a shortcut in your application menu automatically.

```bash
curl -fsSL https://raw.githubusercontent.com/AgreeDK/OpenSAK/main/scripts/install-opensak.sh | bash
```

The installer will:
- Check and install required system packages (`python3`, `git`, `libxcb-cursor0` etc.)
- Clone the repository to `~/opensak`
- Set up a Python virtual environment
- Create an entry in your application menu
- Optionally create a desktop shortcut
- Offer to start OpenSAK immediately when done

> **Manual install:** If you prefer to install manually or the script does not work
> on your distribution, see the [manual Linux instructions](#linux-manual) below.

---

### 🪟 Windows — Standalone installer (recommended)

Download the latest **OpenSAK-Windows.zip** from the
[Releases page](https://github.com/AgreeDK/OpenSAK/releases), unzip it, and
double-click `OpenSAK.exe` — no Python or Git installation required.

---

### 🍎 macOS — App bundle (recommended)

Download the correct `.dmg` for your Mac from the
[Releases page](https://github.com/AgreeDK/OpenSAK/releases):

| Mac type | File to download |
|----------|-----------------|
| Apple Silicon (M1/M2/M3/M4) | `OpenSAK-macOS-arm64.dmg` |
| Intel | `OpenSAK-macOS-x86_64.dmg` |

> **Not sure which Mac you have?** Click the Apple menu () → "About This Mac".
> If it says "Apple M1/M2/M3/M4" choose **arm64**. If it says "Intel" choose **x86_64**.

Open the `.dmg` and drag OpenSAK to your Applications folder.

> On first launch, macOS may block the app because it is not signed with an Apple
> Developer certificate. Right-click → Open to bypass this warning.

---

### Manual installation (all platforms)

Use this method if the automatic installer does not work, or if you prefer
to install from source.

#### Linux (manual) <a name="linux-manual"></a>

```bash
sudo apt update
sudo apt install git python3 python3-venv python3-pip libxcb-cursor0

cd ~
git clone https://github.com/AgreeDK/opensak.git
cd opensak

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run.py
```

#### Windows (manual)

Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) — make sure to check **"Add Python to PATH"**

Install **Git** from [git-scm.com](https://git-scm.com/download/win)

```powershell
cd $env:USERPROFILE
git clone https://github.com/AgreeDK/opensak.git
cd opensak
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

#### macOS (manual)

> ⚠️ macOS is not yet fully tested. Feedback is very welcome!

```bash
xcode-select --install   # if not already installed
brew install python git

cd ~
git clone https://github.com/AgreeDK/opensak.git
cd opensak
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

---

## Getting Started

### 1. Get a Pocket Query from Geocaching.com
1. Log in at [geocaching.com](https://www.geocaching.com)
2. Go to **Pocket Queries** in your profile menu
3. Download a Pocket Query as a `.zip` file

### 2. Import into OpenSAK
1. Start OpenSAK with `python run.py`
2. Click **Import GPX / PQ zip** in the menu bar
3. Select your `.zip` file and click **Import**

### 3. Set your home location
1. Go to **Settings → Settings**
2. Add one or more named home points (e.g. Home, Cottage, Hotel)
3. Coordinates can be entered in any format (DMM, DMS or DD)
4. Activate the home point you want to use — or switch from the toolbar dropdown
5. Choose your preferred **coordinate format** and map app

### 4. Filter and find caches
- **Quick filter** — dropdown at the top of the window
- **Advanced filter** — click 🔍 **Filter** in the toolbar (`Ctrl+F`)
  - General, Dates and ~70 Groundspeak attributes
  - Save filter profiles for reuse

### 5. Plan a trip
1. Click **🗺️ Trip Planner** in the toolbar (`Ctrl+T`)
2. Choose **Radius** to find caches near your home point, or **Route** to find caches along a drive
3. Adjust criteria — the preview updates live
4. Click **🗺️ Show on map** to visualise the selection
5. Export to GPS or save as GPX file

---

## Updating Finds from "My Finds"

1. Download your **"My Finds"** Pocket Query from geocaching.com
2. Create a new database called "My Finds" in OpenSAK
3. Import the My Finds ZIP file into that database
4. Switch back to the database you want to update
5. Go to **Settings → Update finds from reference database**

---

## Changing the Language

1. Go to **Settings → Settings**
2. Select your language in the **Language** section
3. Restart OpenSAK — the new language takes effect on next startup

Currently supported: **Danish (da)**, **English (en)**, **French (fr)**

### Adding a New Language
1. Copy `src/opensak/lang/en.py` to e.g. `src/opensak/lang/de.py`
2. Translate the string values (keys must not be changed)
3. Register the language in `src/opensak/lang/__init__.py`:
   ```python
   AVAILABLE_LANGUAGES = {
       "da": "Dansk",
       "en": "English",
       "fr": "Français",
       "de": "Deutsch",   # ← add this line
   }
   ```
4. Submit a Pull Request — contributions welcome!

---

## Updating to the Latest Version

### If you used the automatic Linux installer

```bash
cd ~/opensak
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

### If you downloaded a release (.exe / .dmg / AppImage)

Download the latest version from the [Releases page](https://github.com/AgreeDK/OpenSAK/releases)
and replace your existing installation.

### If you installed manually from source

```bash
cd ~/opensak
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

git pull origin main
pip install -r requirements.txt
python run.py
```

---

## Uninstalling OpenSAK

OpenSAK does not have an installer or uninstaller. To remove it completely,
delete the following files and folders manually.

> **Tip:** Your geocaching databases are stored inside the data folder below.
> If you want to keep your data for a future reinstall, back up that folder
> before deleting it.

### 🐧 Linux

```bash
rm -rf ~/.local/share/opensak/
rm -rf ~/opensak/
rm -f ~/.local/share/applications/opensak.desktop
rm -f ~/Desktop/opensak.desktop
```

### 🪟 Windows

```cmd
rmdir /s /q "%APPDATA%\opensak"
```
Then delete the folder where you placed `OpenSAK.exe`.

### 🍎 macOS

```bash
rm -rf ~/Library/Application\ Support/opensak/
```
Then drag the OpenSAK app from Applications to Trash.

---

## Reporting Bugs

Please use [GitHub Issues](https://github.com/AgreeDK/opensak/issues) and include:
- Your platform (Linux / Windows / macOS + version)
- Python version: `python3 --version`
- The error message from the terminal (if any)

---

## Project Structure

```
opensak/
├── run.py                          # Entry point
├── requirements.txt
├── scripts/
│   └── install-opensak.sh          # Linux automatic installer
├── src/opensak/
│   ├── app.py                      # Startup + migration
│   ├── config.py                   # Paths + language preference
│   ├── lang/                       # Language files
│   │   ├── __init__.py             # i18n engine (tr() function)
│   │   ├── da.py                   # Danish
│   │   ├── en.py                   # English
│   │   └── fr.py                   # French (contributed by @theyoungstone)
│   ├── db/
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── database.py             # Session management
│   │   ├── manager.py              # Multiple databases
│   │   └── found_updater.py        # Update finds from reference DB
│   ├── importer/                   # GPX + PQ ZIP importer
│   ├── filters/
│   │   └── engine.py               # 18 filter types, AND/OR, profiles
│   ├── gps/
│   │   └── garmin.py               # Garmin detection + GPX generator
│   └── gui/
│       ├── mainwindow.py
│       ├── cache_table.py
│       ├── cache_detail.py
│       ├── map_widget.py
│       ├── settings.py
│       ├── coords.py               # Coordinate format conversion (DD/DMM/DMS)
│       └── dialogs/
│           ├── filter_dialog.py            # Advanced filter (3 tabs)
│           ├── import_dialog.py
│           ├── waypoint_dialog.py
│           ├── column_dialog.py
│           ├── database_dialog.py
│           ├── found_dialog.py
│           ├── gps_dialog.py               # GPS export + delete
│           ├── trip_dialog.py              # Trip planner (radius + route)
│           ├── settings_dialog.py
│           ├── corrected_coords_dialog.py  # Corrected coordinates
│           ├── coord_converter_dialog.py   # Geocaching tool: coordinate converter
│           ├── projection_dialog.py        # Geocaching tool: coordinate projection
│           ├── checksum_dialog.py          # Geocaching tool: digit checksum
│           ├── midpoint_dialog.py          # Geocaching tool: midpoint calculator
│           └── distance_bearing_dialog.py  # Geocaching tool: distance & bearing
└── tests/
    ├── test_db.py                  # 13 tests
    ├── test_importer.py            # 11 tests
    └── test_filters.py             # 39 tests
```

---

## Roadmap

- [ ] HTML/PDF reports and statistics
- [ ] GPS export — improve auto-detection on all Linux distros
- [ ] Favourite points (requires Geocaching.com API)
- [ ] More languages (German, Swedish, …)
- [x] **Trip Planner** — radius and multi-point route corridor with map preview
- [x] **Home points list** — named locations with toolbar quick-switch
- [x] **Corrected coordinates** — store and use solved puzzle coordinates
- [x] Geocaching Tools menu — coordinate converter, projection, checksum, midpoint, distance & bearing
- [x] Coordinate format preference (DMM / DMS / DD)
- [x] French language — contributed by @theyoungstone
- [x] Windows installer (.exe) — built automatically via GitHub Actions
- [x] Linux AppImage — built automatically via GitHub Actions
- [x] macOS installer (.dmg) — arm64 and x86_64, built automatically via GitHub Actions
- [x] GitHub Actions CI/CD pipeline

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [OpenStreetMap](https://www.openstreetmap.org) for map tiles
- [Leaflet.js](https://leafletjs.com) for the map library
- [PySide6 / Qt](https://www.qt.io) for the GUI framework
- [SQLAlchemy](https://www.sqlalchemy.org) for the database layer
- [@theyoungstone](https://github.com/theyoungstone) (Pierre LEJEUNE) for the French translation
- Everyone who has tested the app and provided feedback!
