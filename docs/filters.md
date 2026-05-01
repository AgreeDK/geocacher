# Filter Reference

OpenSAK's filter engine lets you narrow your cache list to exactly what you want. Filters combine with AND or OR logic and can be saved as named profiles for reuse.

---

## Opening the Filter Dialog

Click **View → Set filter…** or press `Ctrl+F`.

---

## AND vs OR logic

By default all active filters are combined with **AND** — a cache must pass every filter to appear in the list.

Switch the mode to **OR** to show caches that pass *at least one* filter. This is useful for broad searches, e.g. "Traditional OR Multi-cache".

Filters can also be **nested**: an outer AND group can contain an inner OR group, letting you express complex conditions like "not found AND (difficulty ≤ 2 OR terrain ≤ 2)".

---

## Filter types

### Cache type

Show only specific cache types. Select one or more from the list.

| Value |
|---|
| Traditional Cache |
| Multi-cache |
| Mystery/Unknown Cache |
| EarthCache |
| Letterbox Hybrid |
| Event Cache |
| CITO Event |
| Mega-Event Cache |
| Wherigo Cache |
| Virtual Cache |
| Webcam Cache |

---

### Container size

Filter by physical container size.

| Value |
|---|
| Nano |
| Micro |
| Small |
| Regular |
| Large |
| Very Large |
| Other |
| Not chosen |
| Virtual |

---

### Difficulty

Show caches within a difficulty range. Values run from **1.0** (easiest) to **5.0** (hardest) in 0.5 steps.

Example: Difficulty 1.0–2.0 shows only easy caches.

Caches with no difficulty set always pass this filter.

---

### Terrain

Show caches within a terrain range. Same 1.0–5.0 scale as difficulty.

---

### Found / Not found

| Filter | Shows |
|---|---|
| Found | Only caches you have marked as found |
| Not found | Only caches you have not found |

---

### Availability

Control which active/inactive states appear:

| Option | What it includes |
|---|---|
| Available | Caches that are active and available |
| Unavailable | Caches temporarily disabled by the owner |
| Archived | Caches permanently archived |

All three can be toggled independently. Default: available only.

---

### Distance

Show only caches within a certain radius of a coordinate. You can also set a minimum distance to exclude caches that are too close.

The reference point defaults to your active home point.

---

### Name

Show caches whose name contains a given text string (case-insensitive, partial match).

Example: `bridge` matches "Old Bridge Cache" and "Bridgetown Mystery".

---

### GC code

Show caches whose GC code contains a given text string (case-insensitive).

Example: `GC1A` matches GC1A2B3 and GC1A999.

---

### Placed by

Show caches placed by owners whose name contains a given text (case-insensitive).

---

### Country / State / County

Show caches located in specific countries, states, or counties. Select one or more values from those present in your database.

---

### Attribute

Show caches that have a specific Groundspeak attribute set. You can filter for attributes that are present (e.g. "Dogs allowed: yes") or explicitly absent ("Dogs allowed: no").

The filter dialog shows the ~70 standard Groundspeak attributes grouped by category on the **Attributes** tab.

---

### Has trackable

Show only caches that currently have at least one trackable logged as in the cache.

---

### Premium / Non-premium

| Filter | Shows |
|---|---|
| Premium | Caches that require a premium Geocaching.com membership |
| Non-premium | Caches that are free to access without a premium membership |

---

## Saving a filter profile

Once you have set up a useful combination, save it so you can reload it in one click:

1. Configure your filters in the filter dialog
2. Click **Save profile**
3. Give it a name (e.g. "Easy day trip" or "Local tradis")
4. Reload it any time from the filter dialog's profile list

Profiles are stored as JSON files in `~/.local/share/opensak/filters/` (Linux/macOS) or `%APPDATA%\opensak\filters\` (Windows).

---

## Clearing filters

Click **View → Clear filter** or use the clear button in the filter dialog to remove all active filters and show the full cache list.

---

## Common filter recipes

| Goal | Filters to combine |
|---|---|
| Unfound traditional caches within 10 km | Not found + Type = Traditional + Distance ≤ 10 km |
| Easy caches for a family trip | Difficulty ≤ 2 + Terrain ≤ 2 + Available |
| Caches with parking nearby | Attribute: Parking available = yes |
| All unfound caches, including archived | Not found + Availability: available + unavailable + archived |
| Caches by a specific owner | Placed by = [owner name] |
| Mystery caches you have not solved yet | Type = Mystery + Not found |
