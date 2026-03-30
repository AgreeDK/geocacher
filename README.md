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
- 📍 **Centre point per database** — distances calculated from your chosen home location
- ✅ **Update finds** from a reference database (e.g. your "My Finds" PQ)

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
- ✏️ **Add / edit / delete** caches manually

### Right-click Menu
- 🌐 Open on geocaching.com
- 🗺️ Open in map app (Google Maps / OpenStreetMap)
- 📋 Copy GC code / coordinates
- ☑ Mark as found / not found

### GPS Export
- 📤 **Send to Garmin GPS** — auto-detects USB-mounted Garmin devices
- 🗑️ **Optional: delete existing GPX files** on device before upload
- 💾 **Save as GPX file** — export to any location

### Language Support
- 🌍 **Danish and English** built in
- 🔧 **Easy to add new languages** — copy one file, translate, done

---

## Known Limitations (Beta)

- Favourite points cannot be imported from GPX/PQ files (requires Geocaching.com API)
- No Geocaching.com Live API integration
- macOS and Windows not yet fully tested — feedback welcome!

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

> **Note:** A pre-built Windows `.exe` is not yet available. It will appear here once
> the first release is published. Until then, please use the manual install method below.

When available, download the latest **OpenSAK-Windows.zip** from the
[Releases page](https://github.com/AgreeDK/OpenSAK/releases), unzip it, and
double-click `OpenSAK.exe` — no Python or Git installation required.

---

### 🍎 macOS — App bundle (recommended)

> **Note:** A pre-built macOS `.dmg` is not yet available. It will appear here once
> the first release is published. Until then, please use the manual install method below.

When available, download the latest **OpenSAK-macOS.dmg** from the
[Releases page](https://github.com/AgreeDK/OpenSAK/releases), open it, and drag
OpenSAK to your Applications folder.

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
1. Go to **Tools → Settings**
2. Enter your home coordinates (latitude / longitude)
3. Choose your preferred map app (Google Maps or OpenStreetMap)

### 4. Filter and find caches
- **Quick filter** — dropdown at the top of the window
- **Advanced filter** — click 🔍 **Filter** in the toolbar (Ctrl+F)
  - General, Dates and ~70 Groundspeak attributes
  - Save filter profiles for reuse

---

## Updating Finds from "My Finds"

1. Download your **"My Finds"** Pocket Query from geocaching.com
2. Create a new database called "My Finds" in OpenSAK
3. Import the My Finds ZIP file into that database
4. Switch back to the database you want to update
5. Go to **Tools → Update finds from reference database**

---

## Changing the Language

1. Go to **Tools → Settings**
2. Select your language in the **Language** section
3. Restart OpenSAK — the new language takes effect on next startup

Currently supported: **Danish (da)**, **English (en)**

### Adding a New Language
1. Copy `src/opensak/lang/en.py` to e.g. `src/opensak/lang/de.py`
2. Translate the string values (keys must not be changed)
3. Register the language in `src/opensak/lang/__init__.py`:
   ```python
   AVAILABLE_LANGUAGES = {
       "da": "Dansk",
       "en": "English",
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
│   │   └── en.py                   # English
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
│       └── dialogs/
│           ├── filter_dialog.py    # Advanced filter (3 tabs)
│           ├── import_dialog.py
│           ├── waypoint_dialog.py
│           ├── column_dialog.py
│           ├── database_dialog.py
│           ├── found_dialog.py
│           ├── gps_dialog.py
│           └── settings_dialog.py
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
- [x] Windows installer (.exe) — built automatically via GitHub Actions
- [x] Linux AppImage — built automatically via GitHub Actions
- [x] GitHub Actions CI/CD pipeline
- [ ] More languages (German, Swedish, …)

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
- Everyone who has tested the app and provided feedback!
