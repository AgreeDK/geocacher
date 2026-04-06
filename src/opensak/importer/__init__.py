"""
src/opensak/importer/__init__.py — GPX + LOC importer for OpenSAK.

Supports:
- Single .gpx files (Groundspeak/Pocket Query format, GPX 1.0)
- Pocket Query .zip files (main GPX + companion -wpts.gpx file)
- .loc files (basic geocaching format with coordinates only)
- Duplicate handling: upserts existing caches by gc_code
- Windows \r\n line endings handled transparently by lxml
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import time
from lxml import etree
from sqlalchemy.orm import Session
import tempfile

from opensak.db.models import Attribute, Cache, Log, Trackable, UserNote, Waypoint


# ── XML namespace map used by Groundspeak Pocket Queries ─────────────────────
# Primary namespace map — uses /1/0/1 (newer PQ files)
NS = {
    "gpx": "http://www.topografix.com/GPX/1/0",
    "gs":  "http://www.groundspeak.com/cache/1/0/1",
}

# Older PQ files (including My Finds) use /1/0 without the trailing /1
_GS_NAMESPACES = [
    "http://www.groundspeak.com/cache/1/0/1",
    "http://www.groundspeak.com/cache/1/0",
]


def _make_ns(gs_uri: str) -> dict:
    """Return a namespace dict with the given Groundspeak URI."""
    return {"gpx": "http://www.topografix.com/GPX/1/0", "gs": gs_uri}


def _text(element, xpath: str, ns: dict = NS) -> Optional[str]:
    """Return stripped text of first XPath match, or None."""
    nodes = element.xpath(xpath, namespaces=ns)
    if nodes:
        val = nodes[0] if isinstance(nodes[0], str) else nodes[0].text
        return val.strip() if val and val.strip() else None
    return None


def _float(element, xpath: str, ns: dict = NS) -> Optional[float]:
    """Return float of first XPath match, or None."""
    val = _text(element, xpath, ns)
    try:
        return float(val) if val is not None else None
    except ValueError:
        return None


def _bool_attr(element, xpath: str, ns: dict = NS) -> bool:
    """Return bool from an attribute value like 'True'/'False'."""
    nodes = element.xpath(xpath, namespaces=ns)
    if nodes:
        return str(nodes[0]).strip().lower() == "true"
    return False


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime strings from GPX files into UTC datetimes."""
    if not raw:
        return None
    raw = raw.strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ── Waypoint (extra) parser ───────────────────────────────────────────────────

def _parse_extra_waypoints(tree) -> dict[str, list[dict]]:
    """
    Parse a -wpts.gpx companion file.

    Returns a dict keyed by GC code (derived from waypoint name prefix rules):
      - Waypoint names like '04BDQBF' → GC prefix is 'GC' + name[2:]  → 'GCBDQBF'
      - But Groundspeak actually stores the parent GC code in <desc> or we
        derive it from the numeric prefix + remaining chars.

    In practice the companion file does NOT embed the parent GC code directly.
    The link is: wpt <n> characters from position 2 onward == gc_code chars
    from position 2 onward.  E.g. '04BDQBF'[2:] == 'BDQBF', parent == 'GC??BDQBF'
    — but the exact digits differ.

    The reliable approach: build a lookup by the suffix (chars [2:]) and match
    against caches in the DB after import.  We store the raw name here and
    resolve during DB write.
    """
    result: dict[str, list[dict]] = {}  # keyed by wpt_suffix (name[2:])

    root = tree.getroot()
    # Strip default namespace for plain XPath
    ns = {"gpx": root.nsmap.get(None, "http://www.topografix.com/GPX/1/0")}

    for wpt in root.findall("{%s}wpt" % ns["gpx"]):
        name_el = wpt.find("{%s}n" % ns["gpx"])
        name = name_el.text.strip() if name_el is not None and name_el.text else ""
        if len(name) < 3:
            continue

        suffix = name[2:]   # e.g. 'BDQBF' from '04BDQBF'

        desc_el = wpt.find("{%s}desc" % ns["gpx"])
        cmt_el  = wpt.find("{%s}cmt" % ns["gpx"])
        type_el = wpt.find("{%s}type" % ns["gpx"])

        wp_type_raw = type_el.text.strip() if type_el is not None and type_el.text else ""
        wp_type = wp_type_raw.split("|")[-1] if "|" in wp_type_raw else wp_type_raw

        entry = {
            "prefix":      name[:2],
            "name":        name,
            "wp_type":     wp_type,
            "description": desc_el.text.strip() if desc_el is not None and desc_el.text else None,
            "comment":     cmt_el.text.strip()  if cmt_el  is not None and cmt_el.text  else None,
            "latitude":    float(wpt.get("lat")) if wpt.get("lat") else None,
            "longitude":   float(wpt.get("lon")) if wpt.get("lon") else None,
        }
        result.setdefault(suffix, []).append(entry)

    return result


# ── Main cache parser ─────────────────────────────────────────────────────────

def _parse_wpt(wpt_el) -> Optional[dict]:
    """
    Parse a single <wpt> element from a Pocket Query GPX file.
    Returns a dict of fields ready to construct/update a Cache, or None on error.
    """
    try:
        lat = float(wpt_el.get("lat"))
        lon = float(wpt_el.get("lon"))
    except (TypeError, ValueError):
        return None

    # GC code: <n> in newer PQ files, <n> in older format
    gc_code = (
        _text(wpt_el, "gpx:name", NS) or
        _text(wpt_el, "gpx:n", NS)
    )
    if not gc_code or not gc_code.startswith("GC"):
        return None

    # Cache type from <type>Geocache|Traditional Cache</type>
    type_raw = _text(wpt_el, "gpx:type", NS) or ""
    cache_type_full = type_raw.split("|")[-1].strip() if "|" in type_raw else type_raw

    hidden_raw = _text(wpt_el, "gpx:time", NS)

    # ── Groundspeak extension block ───────────────────────────────────────────
    # Detect which Groundspeak namespace this file actually uses (/1/0 or /1/0/1)
    gs_cache = None
    active_ns = NS  # default
    for gs_uri in _GS_NAMESPACES:
        gs_cache = wpt_el.find(f"{{{gs_uri}}}cache")
        if gs_cache is not None:
            active_ns = _make_ns(gs_uri)
            break

    gs_id        = gs_cache.get("id")                    if gs_cache is not None else None
    available    = _bool_attr(gs_cache, "@available")    if gs_cache is not None else True
    archived     = _bool_attr(gs_cache, "@archived")     if gs_cache is not None else False

    name         = _text(gs_cache, "gs:name",              active_ns) or _text(wpt_el, "gpx:urlname", NS) or gc_code
    placed_by    = _text(gs_cache, "gs:placed_by",         active_ns)
    owner        = _text(gs_cache, "gs:owner",             active_ns)
    owner_id     = gs_cache.find("gs:owner", active_ns).get("id") if gs_cache is not None and gs_cache.find("gs:owner", active_ns) is not None else None
    cache_type   = _text(gs_cache, "gs:type",              active_ns) or cache_type_full
    container    = _text(gs_cache, "gs:container",         active_ns)
    difficulty   = _float(gs_cache, "gs:difficulty",       active_ns)
    terrain      = _float(gs_cache, "gs:terrain",          active_ns)
    country      = _text(gs_cache, "gs:country",           active_ns)
    state        = _text(gs_cache, "gs:state",             active_ns)
    short_desc   = _text(gs_cache, "gs:short_description", active_ns)
    long_desc    = _text(gs_cache, "gs:long_description",  active_ns)
    hints        = _text(gs_cache, "gs:encoded_hints",     active_ns)

    short_html = False
    long_html  = False
    if gs_cache is not None:
        sd_el = gs_cache.find("gs:short_description", active_ns)
        ld_el = gs_cache.find("gs:long_description",  active_ns)
        if sd_el is not None:
            short_html = (sd_el.get("html", "False").lower() == "true")
        if ld_el is not None:
            long_html  = (ld_el.get("html", "False").lower() == "true")

    # ── Attributes ────────────────────────────────────────────────────────────
    attributes = []
    if gs_cache is not None:
        for attr_el in gs_cache.findall("gs:attributes/gs:attribute", active_ns):
            try:
                attr_id = int(attr_el.get("id", 0))
                is_on   = attr_el.get("inc", "1") == "1"
                attr_name = attr_el.text.strip() if attr_el.text else ""
                attributes.append({"attribute_id": attr_id, "name": attr_name, "is_on": is_on})
            except (ValueError, AttributeError):
                continue

    # ── Logs ─────────────────────────────────────────────────────────────────
    logs = []
    if gs_cache is not None:
        for log_el in gs_cache.findall("gs:logs/gs:log", active_ns):
            log_id   = log_el.get("id")
            log_type = _text(log_el, "gs:type",   active_ns)
            log_date = _parse_datetime(_text(log_el, "gs:date", active_ns))
            finder   = _text(log_el, "gs:finder", active_ns)
            finder_el = log_el.find("gs:finder", active_ns)
            finder_id = finder_el.get("id") if finder_el is not None else None
            text_el  = log_el.find("gs:text", active_ns)
            log_text = text_el.text.strip() if text_el is not None and text_el.text else None
            encoded  = (text_el.get("encoded", "False").lower() == "true") if text_el is not None else False

            if log_type:
                logs.append({
                    "log_id":       log_id,
                    "log_type":     log_type,
                    "log_date":     log_date,
                    "finder":       finder,
                    "finder_id":    finder_id,
                    "text":         log_text,
                    "text_encoded": encoded,
                })

    # ── Trackables ────────────────────────────────────────────────────────────
    trackables = []
    if gs_cache is not None:
        for tb_el in gs_cache.findall("gs:travelbugs/gs:travelbug", active_ns):
            trackables.append({
                "ref":  tb_el.get("ref"),
                "name": _text(tb_el, "gs:name", NS),
            })

    return {
        "gc_code":           gc_code,
        "name":              name,
        "cache_type":        cache_type,
        "container":         container,
        "latitude":          lat,
        "longitude":         lon,
        "difficulty":        difficulty,
        "terrain":           terrain,
        "placed_by":         placed_by,
        "owner_id":          owner_id,
        "hidden_date":       _parse_datetime(hidden_raw),
        "available":         available,
        "archived":          archived,
        "country":           country,
        "state":             state,
        "short_description": short_desc,
        "short_desc_html":   short_html,
        "long_description":  long_desc,
        "long_desc_html":    long_html,
        "encoded_hints":     hints,
        "attributes":        attributes,
        "logs":              logs,
        "trackables":        trackables,
    }


# ── Extra waypoint parser (GSAK single-file GPX) ─────────────────────────────

_KNOWN_PREFIXES = {
    # Groundspeak standard
    "PK": "Parking Area",
    "TH": "Trailhead",
    "S1": "Stage", "S2": "Stage", "S3": "Stage", "S4": "Stage",
    "S5": "Stage", "S6": "Stage", "S7": "Stage", "S8": "Stage", "S9": "Stage",
    "FN": "Final Location",
    "RF": "Reference Point",
    "WP": "Waypoint",
    "SB": "Stages of a Multicache",
    "CM": "Custom",
    "CP": "Custom",
    "PP": "Physical Stage",
    "VX": "Virtual Stage",
    "QA": "Question to Answer",
    # GSAK-specifikke og udvidede prefixes
    "LC": "Listed Coordinates",
    "LB": "Listed By",
    "LA": "Listed Area",
    "PA": "Parking Area",
    "PG": "Parking",
    "PT": "Point",
    "PN": "Point",
    "PB": "Point",
    "RP": "Reference Point",
    "ST": "Stage",
    "SP": "Stage Point",
    "AA": "Additional Waypoint",
    "UL": "Additional Waypoint",
    "TE": "Additional Waypoint",
    "FK": "Additional Waypoint",
    # Øvrige fra brugerfil
    "BR": "Reference Point",
    "UA": "Additional Waypoint",
    "TW": "Additional Waypoint",
    "TU": "Additional Waypoint",
    "TO": "Additional Waypoint",
    "SX": "Stage",
    "SS": "Stage",
    "SM": "Stage",
    "SH": "Stage",
    "SE": "Stage",
}

# Single-bogstavs prefixes (GSAK bruger T + suffix, V + suffix osv.)
_KNOWN_SINGLE_PREFIXES = {
    "T": "Trailhead",
    "V": "Virtual Stage",
    "P": "Parking Area",
    "S": "Stage",
    "F": "Final Location",
    "R": "Reference Point",
}


def _parse_extra_wpt(wpt_el) -> Optional[dict]:
    """Parse a non-GC <wpt> as an extra waypoint (parking, stage, etc.)."""
    try:
        lat = float(wpt_el.get("lat"))
        lon = float(wpt_el.get("lon"))
    except (TypeError, ValueError):
        return None

    raw_name = (
        _text(wpt_el, "gpx:name", NS) or
        _text(wpt_el, "gpx:n",    NS) or ""
    )
    if len(raw_name) < 2:
        return None

    # Forsøg 2-bogstavs prefix først, derefter 1-bogstavs med tal (P0, P1, 01, 02 osv.)
    if len(raw_name) >= 3 and raw_name[:2].upper() in _KNOWN_PREFIXES:
        # Kendt 2-bogstavs prefix: PK, FN, TH osv.
        prefix = raw_name[:2].upper()
        suffix = raw_name[2:]
        wp_type_fallback = _KNOWN_PREFIXES[prefix]
    elif raw_name[0].upper() in _KNOWN_SINGLE_PREFIXES and len(raw_name) >= 2:
        # Single bogstav + suffix: T27A2JF, V363R36 osv.
        # Men kun hvis andet tegn ikke er et tal (P0, P1 håndteres nedenfor)
        if not raw_name[1].isdigit():
            prefix = raw_name[0].upper()
            suffix = raw_name[1:]
            wp_type_fallback = _KNOWN_SINGLE_PREFIXES[prefix]
        else:
            # Bogstav + tal prefix: P0, P1, P2, T0, T1, R0, R1 osv.
            # Brug type-feltet til at bestemme wp_type
            prefix = raw_name[:2].upper()
            suffix = raw_name[2:]
            # Map første bogstav til type via single-prefix map
            wp_type_fallback = _KNOWN_SINGLE_PREFIXES.get(raw_name[0].upper(), "Waypoint")
    elif raw_name[:2].isdigit() and len(raw_name) >= 3:
        # Rent numerisk prefix: 01, 02, 03 osv. — brug type-feltet
        prefix = raw_name[:2]
        suffix = raw_name[2:]
        wp_type_fallback = "Waypoint"
    else:
        # Ukendt prefix-format — tjek om type-feltet angiver et gyldigt waypoint-type
        # Eksempler: 'JJ28J63' type='Waypoint|Final Location'
        # Suffix er altid de sidste 6 tegn (Groundspeak standard)
        type_raw_check = _text(wpt_el, "gpx:type", NS) or ""
        if "|" in type_raw_check and type_raw_check.startswith("Waypoint"):
            # Acceptér som waypoint med generisk prefix
            prefix = raw_name[:2].upper()
            suffix = raw_name[-6:] if len(raw_name) >= 6 else raw_name
            wp_type_fallback = type_raw_check.split("|")[-1].strip()
        else:
            return None

    type_raw = _text(wpt_el, "gpx:type", NS) or ""
    if "|" in type_raw:
        wp_type = type_raw.split("|")[-1].strip()
    elif type_raw:
        wp_type = type_raw
    else:
        wp_type = wp_type_fallback

    desc    = _text(wpt_el, "gpx:desc",    NS)
    comment = _text(wpt_el, "gpx:cmt",     NS)
    name    = _text(wpt_el, "gpx:urlname", NS) or desc or raw_name

    return {
        "prefix":      prefix,
        "suffix":      suffix,
        "wp_type":     wp_type,
        "name":        name,
        "description": desc,
        "comment":     comment,
        "latitude":    lat,
        "longitude":   lon,
    }


def _insert_extra_wpts(session: Session, extra_wpts: list, commit_every: int = 500) -> int:
    """Insert/update extra waypoints.

    Bygger ét suffix→cache_id lookup i RAM for at undgå 11.000 LIKE-queries.
    Committer til disk for hver commit_every caches.
    """
    t0 = time.time()

    # Hent alle gc_codes på én gang og byg suffix→cache_id dict i RAM
    all_caches = session.query(Cache.id, Cache.gc_code).all()
    suffix_to_cache_id: dict[str, int] = {}
    for cache_id, gc_code in all_caches:
        if gc_code and len(gc_code) > 2:
            suffix_to_cache_id[gc_code[2:]] = cache_id

    # Grupper waypoints per suffix
    wpts_by_suffix: dict[str, list] = {}
    for wp in extra_wpts:
        wpts_by_suffix.setdefault(wp["suffix"], []).append(wp)

    count = 0
    batch = 0

    for suffix, wps in wpts_by_suffix.items():
        cache_id = suffix_to_cache_id.get(suffix)
        if cache_id is None:
            continue

        session.query(Waypoint).filter_by(cache_id=cache_id).delete(synchronize_session="fetch")

        for wp in wps:
            session.add(Waypoint(
                cache_id=cache_id,
                prefix=wp["prefix"],
                wp_type=wp["wp_type"],
                name=wp["name"],
                description=wp["description"],
                comment=wp["comment"],
                latitude=wp["latitude"],
                longitude=wp["longitude"],
            ))
            count += 1

        batch += 1
        if batch % commit_every == 0:
            t1 = time.time()
            session.commit()
            session.expunge_all()
    
    t1 = time.time()
    session.commit()
    return count


# ── LOC parser ────────────────────────────────────────────────────────────────

def _parse_loc_waypoint(wpt_el) -> Optional[dict]:
    """
    Parse a single <waypoint> element from a .loc file.

    .loc files only contain GC code, name, and coordinates.
    All other fields are set to None/defaults.
    """
    name_el = wpt_el.find("name")
    if name_el is None:
        return None

    gc_code = name_el.get("id", "").strip()
    if not gc_code.startswith("GC"):
        return None

    # Cache display name is the CDATA text content of <name>
    cache_name = name_el.text.strip() if name_el.text else gc_code

    coord_el = wpt_el.find("coord")
    if coord_el is None:
        return None

    try:
        lat = float(coord_el.get("lat"))
        lon = float(coord_el.get("lon"))
    except (TypeError, ValueError):
        return None

    return {
        "gc_code":           gc_code,
        "name":              cache_name,
        "cache_type":        "Traditional Cache",   # .loc has no type info
        "container":         None,
        "latitude":          lat,
        "longitude":         lon,
        "difficulty":        None,
        "terrain":           None,
        "placed_by":         None,
        "owner_id":          None,
        "hidden_date":       None,
        "available":         True,
        "archived":          False,
        "country":           None,
        "state":             None,
        "short_description": None,
        "short_desc_html":   False,
        "long_description":  None,
        "long_desc_html":    False,
        "encoded_hints":     None,
        "attributes":        [],
        "logs":              [],
        "trackables":        [],
    }


# ── DB upsert ─────────────────────────────────────────────────────────────────

def _upsert_cache(session: Session, data: dict, source_file: str) -> tuple[Cache, bool]:
    """
    Insert or update a Cache row from parsed GPX data.
    Returns (cache_object, created: bool).
    """
    existing = session.query(Cache).filter_by(gc_code=data["gc_code"]).first()
    created  = existing is None

    if created:
        cache = Cache(gc_code=data["gc_code"])
        session.add(cache)
    else:
        cache = existing
        # Clear old child records so they are rebuilt fresh
        session.query(Log).filter_by(cache_id=cache.id).delete()
        session.query(Attribute).filter_by(cache_id=cache.id).delete()
        session.query(Trackable).filter_by(cache_id=cache.id).delete()
        session.query(Waypoint).filter_by(cache_id=cache.id).delete()

    # Scalar fields
    for field in (
        "name", "cache_type", "container", "latitude", "longitude",
        "difficulty", "terrain", "placed_by", "owner_id",
        "hidden_date", "available", "archived",
        "country", "state",
        "short_description", "short_desc_html",
        "long_description",  "long_desc_html",
        "encoded_hints",
    ):
        setattr(cache, field, data.get(field))

    cache.source_file = source_file

    # Attributes
    for a in data.get("attributes", []):
        session.add(Attribute(
            cache=cache,
            attribute_id=a["attribute_id"],
            name=a["name"],
            is_on=a["is_on"],
        ))

    # Logs
    # GSAK bruger dummy log_id '-2' for autogenererede noter (Certitude m.fl.).
    # Disse er ikke unikke på tværs af caches, så vi genererer et unikt ID
    # baseret på cache GC-kode + log indeks når log_id er en kendt dummy-værdi.
    # GSAK bruger negative tal som dummy log IDs (-2, -3 osv.) samt "0" og tom streng.
    # Alle negative log IDs og kendte dummy-værdier får genereret et unikt ID.
    DUMMY_LOG_IDS = {"0", None, ""}
    for idx, lg in enumerate(data.get("logs", [])):
        raw_id = lg["log_id"]
        is_dummy = raw_id in DUMMY_LOG_IDS
        if not is_dummy and raw_id is not None:
            try:
                is_dummy = int(raw_id) < 0
            except (ValueError, TypeError):
                pass
        if is_dummy:
            log_id = f"gen_{data['gc_code']}_{idx}"
        else:
            log_id = raw_id
        session.add(Log(
            cache=cache,
            log_id=log_id,
            log_type=lg["log_type"],
            log_date=lg["log_date"],
            finder=lg["finder"],
            finder_id=lg["finder_id"],
            text=lg["text"],
            text_encoded=lg["text_encoded"],
        ))

    # Trackables
    for tb in data.get("trackables", []):
        session.add(Trackable(cache=cache, ref=tb["ref"], name=tb["name"]))

    return cache, created


def _link_extra_waypoints(
    session: Session,
    extra: dict[str, list[dict]],
) -> int:
    """
    Match parsed extra waypoints to caches already in the DB and insert them.
    Returns number of waypoints inserted.
    """
    count = 0
    for suffix, wpts in extra.items():
        # Find any cache whose gc_code ends with this suffix
        cache = (
            session.query(Cache)
            .filter(Cache.gc_code.like(f"%{suffix}"))
            .first()
        )
        if cache is None:
            continue

        # Remove stale extra waypoints for this cache (keep DB clean on re-import)
        session.query(Waypoint).filter_by(cache_id=cache.id).delete()

        for wp in wpts:
            session.add(Waypoint(
                cache=cache,
                prefix=wp["prefix"],
                wp_type=wp["wp_type"],
                name=wp["name"],
                description=wp["description"],
                comment=wp["comment"],
                latitude=wp["latitude"],
                longitude=wp["longitude"],
            ))
            count += 1

    return count


# ── Public API ────────────────────────────────────────────────────────────────

class ImportResult:
    """Summary of a GPX/LOC import operation."""

    def __init__(self):
        self.created:   int = 0
        self.updated:   int = 0
        self.skipped:   int = 0
        self.waypoints: int = 0
        self.errors:    list[str] = []
        self.warnings:  list[str] = []

    @property
    def total(self) -> int:
        return self.created + self.updated

    def __str__(self) -> str:
        lines = [
            f"  Caches created : {self.created}",
            f"  Caches updated : {self.updated}",
            f"  Waypoints added: {self.waypoints}",
            f"  Skipped        : {self.skipped}",
        ]
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        if self.errors:
            lines.append(f"  Errors         : {len(self.errors)}")
            for e in self.errors[:5]:
                lines.append(f"    - {e}")
        return "\n".join(lines)


def import_gpx(
    gpx_path: Path,
    session: Session | None = None,
    wpts_path: Optional[Path] = None,
    progress_cb=None,
    batch_size: int = 500
) -> ImportResult:
    """
    Import a single GPX file into the database using streaming for high performance.

    Uses etree.iterparse to handle files of any size without RAM exhaustion.
    The session parameter is kept for compatibility but a new session is managed internally.
    """
    from opensak.db.database import make_session

    result = ImportResult()
    source = gpx_path.name
    db_session = make_session()
    
    extra_wpts: list = []
    processed_count = 0

    try:
        # Stream the XML using iterparse to avoid loading the entire file into RAM
        context = etree.iterparse(
            str(gpx_path), 
            events=("end",), 
            tag=None  
        )

        for event, elem in context:
            # Handle tags regardless of namespace version
            local_tag = etree.QName(elem).localname

            if local_tag == "wpt":
                try:
                    data = _parse_wpt(elem)
                    
                    if data is not None:
                        # Perform Upsert safely (using Query, not exists())
                        _, created = _upsert_cache(db_session, data, source)
                        if created:
                            result.created += 1
                        else:
                            result.updated += 1
                        
                        processed_count += 1
                        if progress_cb:
                            progress_cb(processed_count)
                    else:
                        # Attempt to parse as an additional waypoint
                        extra = _parse_extra_wpt(elem)
                        if extra is not None:
                            extra_wpts.append(extra)
                        else:
                            result.skipped += 1
                            
                    # Batch commit to disk and clear session to save RAM
                    if processed_count % batch_size == 0:
                        db_session.commit()
                        db_session.expunge_all()

                except Exception as e:
                    db_session.rollback()
                    result.errors.append(f"Error in {source}: {e}")
                    result.skipped += 1
                finally:
                    # CRITICAL: Clear the element and its preceding siblings from memory
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

        # Final commit for remaining caches
        db_session.commit()

        # Handle Extra Waypoints (Deduplication and Linking)
        if extra_wpts:
            seen = set()
            unique_wpts = []
            for wp in extra_wpts:
                key = (wp.get("suffix"), wp.get("prefix"), wp.get("name"))
                if key not in seen:
                    seen.add(key)
                    unique_wpts.append(wp)
            
            result.waypoints += _insert_extra_wpts(db_session, unique_wpts)
            db_session.commit()

        # Process companion waypoint files (_wpts.gpx) if present
        if wpts_path and wpts_path.exists():
            try:
                wpts_tree = etree.parse(str(wpts_path))
                extra_data = _parse_extra_waypoints(wpts_tree)
                result.waypoints += _link_extra_waypoints(db_session, extra_data)
                db_session.commit()
            except Exception as e:
                result.errors.append(f"Waypoints file error: {e}")

    except Exception as e:
        db_session.rollback()
        result.errors.append(f"Fatal error importing {source}: {e}")
    finally:
        db_session.close()

    return result

def import_zip(zip_path: Path, session: Session | None = None, progress_cb=None) -> ImportResult:
    """
    High-performance parallel ZIP import.
    
    Strategy: 
    1. Parse XML files in parallel threads (CPU intensive).
    2. Collect all parsed data into memory.
    3. Perform a single, massive batch database write (IO intensive).
    """
    from concurrent.futures import ThreadPoolExecutor
    import zipfile
    import tempfile

    overall_result = ImportResult()

    if not zipfile.is_zipfile(zip_path):
        overall_result.errors.append(f"{zip_path.name} is not a valid zip file")
        return overall_result

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        gpx_files = [f for f in tmp.glob("*.gpx") if "-wpts" not in f.name.lower()]

        # 1. Parallel Parsing
        # We use more threads because lxml is very efficient at releasing the GIL.
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for gpx_path in gpx_files:
                wpts_candidate = tmp / f"{gpx_path.stem}-wpts.gpx"
                # We still pass wpts_path if needed
                futures.append(executor.submit(import_gpx, gpx_path, wpts_path=(wpts_candidate if wpts_candidate.exists() else None)))
            
            for future in futures:
                try:
                    file_result = future.result()
                    # Aggregate results
                    overall_result.created += file_result.created
                    overall_result.updated += file_result.updated
                    overall_result.skipped += file_result.skipped
                    overall_result.waypoints += file_result.waypoints
                    overall_result.errors.extend(file_result.errors)
                except Exception as e:
                    overall_result.errors.append(f"Parse error: {str(e)}")

    return overall_result

def import_loc(loc_path: Path, session: Session) -> ImportResult:
    """
    Import a .loc file into the database.

    .loc files only contain GC code, name, and coordinates.
    A warning is added to the result informing the user about missing data.
    """
    result = ImportResult()
    source = loc_path.name

    result.warnings.append(
        ".loc filer indeholder kun koordinater og navn — "
        "importér en GPX fil for at få fuld cacheinformation"
    )

    try:
        tree = etree.parse(str(loc_path))
    except etree.XMLSyntaxError as e:
        result.errors.append(f"XML parse error i {loc_path.name}: {e}")
        return result

    root = tree.getroot()

    for wpt_el in root.iter("waypoint"):
        try:
            data = _parse_loc_waypoint(wpt_el)
        except Exception as e:
            result.errors.append(f"Parse error: {e}")
            result.skipped += 1
            continue

        if data is None:
            result.skipped += 1
            continue

        try:
            _, created = _upsert_cache(session, data, source)
            if created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as e:
            result.errors.append(f"DB fejl for {data.get('gc_code', '?')}: {e}")
            result.skipped += 1

    return result
