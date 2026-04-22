"""
tests/test_importer_loc.py — Tests for import_loc() in src/opensak/importer/__init__.py

Covers .loc file parsing, DB upsert, warnings, error paths, and the
progress_cb callback in import_gpx().
"""

import pytest
from pathlib import Path

from opensak.db.database import init_db, make_session
from opensak.db.models import Cache
from opensak.importer import import_loc, import_gpx

# db_session and make_cache fixtures come from conftest.py


# ── Synthetic .loc content ────────────────────────────────────────────────────

def _make_loc(waypoints: list[dict]) -> str:
    """Build a minimal .loc XML string from a list of waypoint dicts."""
    wpts = ""
    for wp in waypoints:
        wpts += f"""
  <waypoint>
    <name id="{wp['gc_code']}">{wp.get('name', wp['gc_code'])}</name>
    <coord lat="{wp['lat']}" lon="{wp['lon']}"/>
  </waypoint>"""
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<loc version="1.0">{wpts}\n</loc>'


SAMPLE_LOC = _make_loc([
    {"gc_code": "GC11111", "name": "Forest Cache", "lat": "55.100", "lon": "12.100"},
    {"gc_code": "GC22222", "name": "City Cache",   "lat": "55.200", "lon": "12.200"},
])

SINGLE_LOC = _make_loc([
    {"gc_code": "GC33333", "name": "Single Cache", "lat": "56.000", "lon": "10.000"},
])

INVALID_XML = "not xml at all <<<"

MISSING_COORD_LOC = """\
<?xml version="1.0" encoding="UTF-8"?>
<loc version="1.0">
  <waypoint>
    <name id="GC44444">No Coord Cache</name>
  </waypoint>
</loc>
"""

NON_GC_LOC = """\
<?xml version="1.0" encoding="UTF-8"?>
<loc version="1.0">
  <waypoint>
    <name id="TR99999">Non-GC Waypoint</name>
    <coord lat="55.0" lon="12.0"/>
  </waypoint>
</loc>
"""


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def loc_file(tmp_path):
    """Write SAMPLE_LOC to a temp file and return its path."""
    p = tmp_path / "test.loc"
    p.write_text(SAMPLE_LOC, encoding="utf-8")
    return p


# ── import_loc — basic import ─────────────────────────────────────────────────

class TestImportLocBasic:
    def test_creates_correct_number_of_caches(self, loc_file, db_session):
        result = import_loc(loc_file, db_session)
        db_session.commit()
        assert result.created == 2
        assert result.total == 2

    def test_gc_codes_stored(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        codes = {c.gc_code for c in db_session.query(Cache).all()}
        assert "GC11111" in codes
        assert "GC22222" in codes

    def test_cache_name_stored(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        cache = db_session.query(Cache).filter_by(gc_code="GC11111").first()
        assert cache.name == "Forest Cache"

    def test_coordinates_stored(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        cache = db_session.query(Cache).filter_by(gc_code="GC11111").first()
        assert cache.latitude == pytest.approx(55.1, rel=1e-4)
        assert cache.longitude == pytest.approx(12.1, rel=1e-4)

    def test_default_cache_type_is_traditional(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        cache = db_session.query(Cache).filter_by(gc_code="GC11111").first()
        assert cache.cache_type == "Traditional Cache"

    def test_warning_about_limited_data(self, loc_file, db_session):
        result = import_loc(loc_file, db_session)
        assert len(result.warnings) > 0
        warning_text = " ".join(result.warnings).lower()
        assert "loc" in warning_text or "gpx" in warning_text

    def test_source_file_recorded(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        cache = db_session.query(Cache).filter_by(gc_code="GC11111").first()
        assert cache.source_file == loc_file.name

    def test_single_waypoint(self, tmp_path, db_session):
        p = tmp_path / "single.loc"
        p.write_text(SINGLE_LOC, encoding="utf-8")
        result = import_loc(p, db_session)
        db_session.commit()
        assert result.created == 1


# ── import_loc — edge cases ───────────────────────────────────────────────────

class TestImportLocEdgeCases:
    def test_invalid_xml_returns_error(self, tmp_path, db_session):
        p = tmp_path / "bad.loc"
        p.write_text(INVALID_XML, encoding="utf-8")
        result = import_loc(p, db_session)
        assert len(result.errors) > 0
        assert result.created == 0

    def test_missing_coord_element_skipped(self, tmp_path, db_session):
        p = tmp_path / "no_coord.loc"
        p.write_text(MISSING_COORD_LOC, encoding="utf-8")
        result = import_loc(p, db_session)
        db_session.commit()
        assert result.created == 0
        assert result.skipped == 1

    def test_non_gc_id_skipped(self, tmp_path, db_session):
        p = tmp_path / "non_gc.loc"
        p.write_text(NON_GC_LOC, encoding="utf-8")
        result = import_loc(p, db_session)
        db_session.commit()
        assert result.created == 0
        assert result.skipped == 1

    def test_empty_loc_file(self, tmp_path, db_session):
        p = tmp_path / "empty.loc"
        p.write_text('<?xml version="1.0"?><loc version="1.0"></loc>', encoding="utf-8")
        result = import_loc(p, db_session)
        assert result.created == 0
        assert len(result.errors) == 0


# ── import_loc — upsert behaviour ────────────────────────────────────────────

class TestImportLocUpsert:
    def test_reimport_does_not_duplicate(self, loc_file, db_session):
        import_loc(loc_file, db_session)
        db_session.commit()
        result2 = import_loc(loc_file, db_session)
        db_session.commit()

        assert result2.updated == 2
        assert result2.created == 0
        total = db_session.query(Cache).count()
        assert total == 2

    def test_reimport_updates_name(self, tmp_path, db_session):
        original = _make_loc([{"gc_code": "GC55555", "name": "Old Name", "lat": "55.0", "lon": "12.0"}])
        updated  = _make_loc([{"gc_code": "GC55555", "name": "New Name", "lat": "55.0", "lon": "12.0"}])

        p = tmp_path / "cache.loc"
        p.write_text(original)
        import_loc(p, db_session)
        db_session.commit()

        p.write_text(updated)
        import_loc(p, db_session)
        db_session.commit()

        cache = db_session.query(Cache).filter_by(gc_code="GC55555").first()
        assert cache.name == "New Name"


# ── import_gpx — progress_cb ─────────────────────────────────────────────────

MINIMAL_GPX = """\
<?xml version="1.0" encoding="utf-8"?>
<gpx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     version="1.0"
     creator="Groundspeak Pocket Query"
     xmlns="http://www.topografix.com/GPX/1/0">
  <wpt lat="55.6761" lon="12.5683">
    <time>2024-06-01T00:00:00</time>
    <n>GC77777</n>
    <desc>Progress Test Cache</desc>
    <urlname>Progress Test Cache</urlname>
    <type>Geocache|Traditional Cache</type>
    <groundspeak:cache id="7777" archived="False" available="True"
        xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
      <groundspeak:name>Progress Test Cache</groundspeak:name>
      <groundspeak:placed_by>Tester</groundspeak:placed_by>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Small</groundspeak:container>
      <groundspeak:difficulty>1.0</groundspeak:difficulty>
      <groundspeak:terrain>1.0</groundspeak:terrain>
    </groundspeak:cache>
  </wpt>
</gpx>
"""


class TestImportGpxProgressCallback:
    def test_callback_called_at_least_once(self, tmp_path):
        db_path = tmp_path / "progress.db"
        init_db(db_path=db_path)
        gpx_file = tmp_path / "test.gpx"
        gpx_file.write_text(MINIMAL_GPX, encoding="utf-8")

        calls = []
        import_gpx(gpx_file, progress_cb=lambda n: calls.append(n))

        assert len(calls) > 0

    def test_callback_receives_count(self, tmp_path):
        db_path = tmp_path / "progress2.db"
        init_db(db_path=db_path)
        gpx_file = tmp_path / "test2.gpx"
        gpx_file.write_text(MINIMAL_GPX, encoding="utf-8")

        calls = []
        import_gpx(gpx_file, progress_cb=lambda n: calls.append(n))

        positive_calls = [c for c in calls if c > 0]
        assert len(positive_calls) >= 1

    def test_no_callback_does_not_raise(self, tmp_path):
        db_path = tmp_path / "no_cb.db"
        init_db(db_path=db_path)
        gpx_file = tmp_path / "test3.gpx"
        gpx_file.write_text(MINIMAL_GPX, encoding="utf-8")

        result = import_gpx(gpx_file, progress_cb=None)
        assert result.created == 1
