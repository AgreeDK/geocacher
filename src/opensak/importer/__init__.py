"""
src/opensak/importer/gpx.py — GPX importer for OpenSAK.

Supports:
- Single .gpx files (Groundspeak/Pocket Query format, GPX 1.0)
- Pocket Query .zip files (main GPX + companion -wpts.gpx file)
- Duplicate handling: upserts existing caches by gc_code
- Windows \r\n line endings handled transparently by lxml
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lxml import etree
from sqlalchemy.orm import Session

from opensak.db.models import Attribute, Cache, Log, Trackable, UserNote, Waypoint

# ── XML namespace map used by Groundspeak Pocket Queries ─────────────────────
NS = {
    "gpx": "http://www.topografix.com/GPX/1/0",
    "gs":  "http://www.groundspeak.com/cache/1/0/1",
}


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
    The link is: wpt <name> characters from position 2 onward == gc_code chars
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

    # GC code: <name> in newer PQ files, <n> in older format
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
    gs_cache = wpt_el.find("gs:cache", NS)
    if gs_cache is None:
        # Try without namespace prefix (some files omit it)
        gs_cache = wpt_el.find(
            "{http://www.groundspeak.com/cache/1/0/1}cache"
        )

    gs_id        = gs_cache.get("id")           if gs_cache is not None else None
    available    = _bool_attr(gs_cache, "@available") if gs_cache is not None else True
    archived     = _bool_attr(gs_cache, "@archived")  if gs_cache is not None else False

    name         = _text(gs_cache, "gs:name",              NS) or _text(wpt_el, "gpx:urlname", NS) or gc_code
    placed_by    = _text(gs_cache, "gs:placed_by",         NS)
    owner        = _text(gs_cache, "gs:owner",             NS)
    owner_id     = gs_cache.find("gs:owner", NS).get("id") if gs_cache is not None and gs_cache.find("gs:owner", NS) is not None else None
    cache_type   = _text(gs_cache, "gs:type",              NS) or cache_type_full
    container    = _text(gs_cache, "gs:container",         NS)
    difficulty   = _float(gs_cache, "gs:difficulty",       NS)
    terrain      = _float(gs_cache, "gs:terrain",          NS)
    country      = _text(gs_cache, "gs:country",           NS)
    state        = _text(gs_cache, "gs:state",             NS)
    short_desc   = _text(gs_cache, "gs:short_description", NS)
    long_desc    = _text(gs_cache, "gs:long_description",  NS)
    hints        = _text(gs_cache, "gs:encoded_hints",     NS)

    short_html = False
    long_html  = False
    if gs_cache is not None:
        sd_el = gs_cache.find("gs:short_description", NS)
        ld_el = gs_cache.find("gs:long_description",  NS)
        if sd_el is not None:
            short_html = (sd_el.get("html", "False").lower() == "true")
        if ld_el is not None:
            long_html  = (ld_el.get("html", "False").lower() == "true")

    # ── Attributes ────────────────────────────────────────────────────────────
    attributes = []
    if gs_cache is not None:
        for attr_el in gs_cache.findall("gs:attributes/gs:attribute", NS):
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
        for log_el in gs_cache.findall("gs:logs/gs:log", NS):
            log_id   = log_el.get("id")
            log_type = _text(log_el, "gs:type",   NS)
            log_date = _parse_datetime(_text(log_el, "gs:date", NS))
            finder   = _text(log_el, "gs:finder", NS)
            finder_el = log_el.find("gs:finder", NS)
            finder_id = finder_el.get("id") if finder_el is not None else None
            text_el  = log_el.find("gs:text", NS)
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
        for tb_el in gs_cache.findall("gs:travelbugs/gs:travelbug", NS):
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
    for lg in data.get("logs", []):
        session.add(Log(
            cache=cache,
            log_id=lg["log_id"],
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
    """Summary of a GPX import operation."""

    def __init__(self):
        self.created:   int = 0
        self.updated:   int = 0
        self.skipped:   int = 0
        self.waypoints: int = 0
        self.errors:    list[str] = []

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
        if self.errors:
            lines.append(f"  Errors         : {len(self.errors)}")
            for e in self.errors[:5]:
                lines.append(f"    - {e}")
        return "\n".join(lines)


def import_gpx(
    gpx_path: Path,
    session: Session,
    wpts_path: Optional[Path] = None,
) -> ImportResult:
    """
    Import a single GPX file into the database.

    Parameters
    ----------
    gpx_path  : Path to the main .gpx file
    session   : Active SQLAlchemy session
    wpts_path : Optional path to companion -wpts.gpx file
    """
    result = ImportResult()
    source = gpx_path.name

    # Parse main GPX
    try:
        tree = etree.parse(str(gpx_path))
    except etree.XMLSyntaxError as e:
        result.errors.append(f"XML parse error in {gpx_path.name}: {e}")
        return result

    root = tree.getroot()
    # Determine namespace (some files use default ns, some explicit)
    ns_uri = root.nsmap.get(None, "http://www.topografix.com/GPX/1/0")
    wpt_tag = f"{{{ns_uri}}}wpt"

    for wpt_el in root.iter(wpt_tag):
        try:
            data = _parse_wpt(wpt_el)
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
            result.errors.append(f"DB error for {data.get('gc_code', '?')}: {e}")
            result.skipped += 1

    # Flush so child records get cache_id before waypoint linking
    session.flush()

    # Parse and link companion waypoints file
    if wpts_path and wpts_path.exists():
        try:
            wpts_tree = etree.parse(str(wpts_path))
            extra = _parse_extra_waypoints(wpts_tree)
            result.waypoints = _link_extra_waypoints(session, extra)
        except Exception as e:
            result.errors.append(f"Waypoints file error: {e}")

    return result


def import_zip(zip_path: Path, session: Session) -> ImportResult:
    """
    Import a Pocket Query .zip file.

    The zip contains:
      - <name>.gpx          — main cache file
      - <name>-wpts.gpx     — companion waypoints file (optional)
    """
    result = ImportResult()

    if not zipfile.is_zipfile(zip_path):
        result.errors.append(f"{zip_path.name} is not a valid zip file")
        return result

    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        # Find the main GPX (the one without '-wpts' in the name)
        gpx_files  = [f for f in tmp.glob("*.gpx") if "-wpts" not in f.name]
        wpts_files = [f for f in tmp.glob("*-wpts.gpx")]

        if not gpx_files:
            result.errors.append("No .gpx file found in zip")
            return result

        gpx_path  = gpx_files[0]
        wpts_path = wpts_files[0] if wpts_files else None

        result = import_gpx(gpx_path, session, wpts_path=wpts_path)

    return result
