# OpenSAK — Open Source geocaching management tool

Et open source geocaching-styringsværktøj til **Linux**, **Windows** og **macOS** — en moderne, cross-platform efterfølger til GSAK, bygget i Python.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Beta-orange)

---

## Funktioner

### Import & Database
- 📥 **Import** af GPX filer og Pocket Query ZIP filer fra Geocaching.com
- 🗄️ **Flere databaser** — hold f.eks. Sjælland, Bornholm og Cypern adskilt
- 📍 **Centerpunkt per database** — afstande beregnes fra dit valgte udgangspunkt
- ✅ **Opdater fund** fra en reference database (f.eks. "Mine Fund" PQ)

### Visning & Navigation
- 🗺️ **Interaktivt kort** med OpenStreetMap og farvekodet cache-pins
- 🔍 **Avanceret filter dialog** — 3 faner: Generelt, Datoer og Attributter
- 📊 **Valgfrie kolonner** — 17+ kolonner kan slås til/fra
- 🎨 **Status ikoner** i listen — ✅ fundet, ❌ DNF, 🔒 arkiveret, ⚠️ utilgængelig
- 🔗 **Klik på GC kode** → åbner cache-siden på geocaching.com
- 🗺️ **Klik på koordinat** → åbner i Google Maps eller OpenStreetMap

### Cache detaljer
- 📋 **Cache detaljer** — beskrivelse, hints og logs
- 🔓 **ROT13 hint dekodning** — ét klik dekoder/genskjuler hintet
- 🔍 **Søg i logs** — realtidssøgning med fremhævning af matches
- ✏️ **Tilføj/rediger/slet** caches manuelt

### Højreklik menu
- 🌐 Åbn på geocaching.com
- 🗺️ Åbn i kortapp (Google Maps / OpenStreetMap)
- 📋 Kopiér GC kode / koordinater
- ☑ Marker som fundet/ikke fundet

---

## Kendte begrænsninger (Beta)

- Favorite points importeres ikke fra GPX/PQ filer
- Ingen Geocaching.com Live API integration (planlagt)
- Ingen GPS device export endnu (under udvikling)
- Ingen rapport/export funktion endnu (under udvikling)
- macOS og Windows er ikke testet endnu — feedback modtages gerne!

---

## Systemkrav

| Platform | Krav |
|---|---|
| **Linux** | Ubuntu 20.04+ / Linux Mint 20+ / Debian 11+ |
| **Windows** | Windows 10 eller nyere |
| **macOS** | macOS 11 (Big Sur) eller nyere |
| **Python** | 3.10 eller nyere |
| **Diskplads** | Ca. 500 MB (inkl. PySide6) |

---

## Installation

### Linux (Ubuntu / Linux Mint / Debian)

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

---

### Windows

**Installer Python 3.10+** fra [python.org](https://www.python.org/downloads/) — husk flueben ved **"Add Python to PATH"**

**Installer Git** fra [git-scm.com](https://git-scm.com/download/win)

```powershell
cd $env:USERPROFILE
git clone https://github.com/AgreeDK/opensak.git
cd opensak
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

---

### macOS

> ⚠️ macOS er ikke testet endnu. Feedback modtages meget gerne!

```bash
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

## Kom i gang — første brug

### 1. Hent en Pocket Query fra Geocaching.com
1. Log ind på [geocaching.com](https://www.geocaching.com)
2. Gå til **Pocket Queries** under dit profilmenu
3. Hent en Pocket Query som en `.zip` fil

### 2. Importer i OpenSAK
1. Start OpenSAK med `python run.py`
2. Klik **Importer GPX / PQ zip** i menulinjen
3. Vælg din `.zip` fil og klik **Importer**

### 3. Sæt dit centerpunkt
1. Gå til **Funktioner → Indstillinger**
2. Indtast din hjemkoordinat (breddegrad / længdegrad)
3. Vælg foretrukken kortapp (Google Maps eller OpenStreetMap)

### 4. Filtrer og find caches
- **Hurtigfilter** — dropdown øverst i vinduet
- **Avanceret filter** — klik 🔍 **Filter** i toolbar (Ctrl+F)
  - Generelt, Datoer og ~70 Groundspeak attributter
  - Gem filterprofiler til genbrug

---

## Opdater fundne caches fra "My Finds"

1. Hent din **"My Finds"** Pocket Query fra geocaching.com
2. Opret en ny database kaldet "Mine Fund" i OpenSAK
3. Importer My Finds ZIP filen i den database
4. Skift til den database du vil opdatere
5. Gå til **Funktioner → Opdater fund fra reference database**

---

## Opdater til nyeste version

```bash
cd ~/opensak
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

git pull origin main
pip install -r requirements.txt
python run.py
```

---

## Rapporter fejl

Brug [GitHub Issues](https://github.com/AgreeDK/opensak/issues) og inkludér:
- Din platform (Linux/Windows/macOS + version)
- Python version: `python3 --version`
- Fejlbesked fra terminalen

---

## Projektstruktur

```
opensak/
├── run.py                              # Start programmet herfra
├── requirements.txt
├── src/opensak/
│   ├── app.py
│   ├── config.py
│   ├── db/
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── manager.py
│   │   └── found_updater.py
│   ├── importer/
│   ├── filters/
│   │   └── engine.py                   # 18 filtertyper med AND/OR logik
│   └── gui/
│       ├── mainwindow.py
│       ├── cache_table.py
│       ├── cache_detail.py
│       ├── map_widget.py
│       ├── settings.py
│       └── dialogs/
│           ├── filter_dialog.py        # Avanceret filter (3 faner)
│           ├── import_dialog.py
│           ├── waypoint_dialog.py
│           ├── column_dialog.py
│           ├── database_dialog.py
│           ├── found_dialog.py
│           └── settings_dialog.py
└── tests/
```

---

## Køreplan

- [ ] GPS device export (Garmin og andre)
- [ ] HTML/PDF rapporter og statistik
- [ ] Sprogfiler (engelsk, tysk m.fl.)
- [ ] Favorite points (kræver Geocaching.com API)
- [ ] Windows installer (.exe)
- [ ] Linux AppImage

---

## Licens

MIT License — se [LICENSE](LICENSE) filen for detaljer.

---

## Tak til

- [OpenStreetMap](https://www.openstreetmap.org) for kortdata
- [Leaflet.js](https://leafletjs.com) for kortbiblioteket
- [PySide6 / Qt](https://www.qt.io) for GUI frameworket
- [SQLAlchemy](https://www.sqlalchemy.org) for databaselaget
- Alle der har testet og givet feedback!
