"""
tests/test_importer.py — Stage 2: GPX importer tests.

Run with:
    pytest -v tests/test_importer.py
"""

import zipfile
import pytest
from pathlib import Path
from datetime import timezone  # kept for potential future use

from opensak.db.database import init_db, get_session
from opensak.db.models import Cache, Waypoint, Log, Attribute, Trackable
from opensak.importer import import_gpx, import_zip

# ── Synthetic GPX matching real Groundspeak/PQ format ────────────────────────

SAMPLE_GPX = """\
<?xml version="1.0" encoding="utf-8"?>
<gpx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     version="1.0"
     creator="Groundspeak Pocket Query"
     xmlns="http://www.topografix.com/GPX/1/0">
  <n>Test PQ</n>
  <time>2026-03-10T07:22:19Z</time>
  <wpt lat="55.6761" lon="12.5683">
    <time>2024-06-01T00:00:00</time>
    <n>GC12345</n>
    <desc>Test Traditional by TestOwner, Traditional Cache (2.0/3.0)</desc>
    <url>https://coord.info/GC12345</url>
    <urlname>Test Traditional</urlname>
    <sym>Geocache</sym>
    <type>Geocache|Traditional Cache</type>
    <groundspeak:cache id="9999" archived="False" available="True"
        xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
      <groundspeak:name>Test Traditional</groundspeak:name>
      <groundspeak:placed_by>TestOwner</groundspeak:placed_by>
      <groundspeak:owner id="12345">TestOwner</groundspeak:owner>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Small</groundspeak:container>
      <groundspeak:attributes>
        <groundspeak:attribute id="6" inc="1">Recommended for kids</groundspeak:attribute>
        <groundspeak:attribute id="24" inc="0">Wheelchair accessible</groundspeak:attribute>
      </groundspeak:attributes>
      <groundspeak:difficulty>2.0</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>Denmark</groundspeak:country>
      <groundspeak:state>Zealand</groundspeak:state>
      <groundspeak:county>Copenhagen</groundspeak:county>
      <groundspeak:short_description html="False">A short description.</groundspeak:short_description>
      <groundspeak:long_description html="True">&lt;p&gt;A longer description.&lt;/p&gt;</groundspeak:long_description>
      <groundspeak:encoded_hints>Under a rock.</groundspeak:encoded_hints>
      <groundspeak:logs>
        <groundspeak:log id="111">
          <groundspeak:date>2026-01-15T10:30:00Z</groundspeak:date>
          <groundspeak:type>Found it</groundspeak:type>
          <groundspeak:finder id="999">Tester</groundspeak:finder>
          <groundspeak:text encoded="False">TFTC! Great hide.</groundspeak:text>
        </groundspeak:log>
        <groundspeak:log id="112">
          <groundspeak:date>2025-12-01T09:00:00Z</groundspeak:date>
          <groundspeak:type>Didn't find it</groundspeak:type>
          <groundspeak:finder id="888">Searcher</groundspeak:finder>
          <groundspeak:text encoded="False">Could not find it.</groundspeak:text>
        </groundspeak:log>
      </groundspeak:logs>
    </groundspeak:cache>
  </wpt>
  <wpt lat="56.1234" lon="10.5678">
    <time>2023-03-15T00:00:00</time>
    <n>GC99999</n>
    <desc>Mystery Cache by Puzzler, Unknown Cache (4.0/2.5)</desc>
    <url>https://coord.info/GC99999</url>
    <urlname>Mystery Cache</urlname>
    <sym>Geocache</sym>
    <type>Geocache|Unknown Cache</type>
    <groundspeak:cache id="8888" archived="False" available="True"
        xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
      <groundspeak:name>Mystery Cache</groundspeak:name>
      <groundspeak:placed_by>Puzzler</groundspeak:placed_by>
      <groundspeak:owner id="54321">Puzzler</groundspeak:owner>
      <groundspeak:type>Unknown Cache</groundspeak:type>
      <groundspeak:container>Micro</groundspeak:container>
      <groundspeak:attributes/>
      <groundspeak:difficulty>4.0</groundspeak:difficulty>
      <groundspeak:terrain>2.5</groundspeak:terrain>
      <groundspeak:country>Denmark</groundspeak:country>
      <groundspeak:state>Region Midtjylland</groundspeak:state>
      <groundspeak:county>Aarhus</groundspeak:county>
      <groundspeak:short_description html="False"></groundspeak:short_description>
      <groundspeak:long_description html="False">Solve the puzzle first.</groundspeak:long_description>
      <groundspeak:encoded_hints>Check the tree.</groundspeak:encoded_hints>
      <groundspeak:logs/>
    </groundspeak:cache>
  </wpt>
</gpx>
"""

SAMPLE_WPTS_GPX = """\
<?xml version="1.0" encoding="utf-8"?>
<gpx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     version="1.0"
     creator="Groundspeak, Inc."
     xmlns="http://www.topografix.com/GPX/1/0">
  <n>Waypoints for Cache Listings</n>
  <wpt lat="55.6762" lon="12.5680">
    <n>PK2345</n>
    <desc>Parking Area</desc>
    <sym>Parking Area</sym>
    <type>Waypoint|Parking Area</type>
    <cmt>Park here and walk 200m south.</cmt>
  </wpt>
</gpx>
"""

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("data") / "test_importer.db"
    init_db(db_path=db_path)
    return db_path


@pytest.fixture
def gpx_file(tmp_path) -> Path:
    f = tmp_path / "test.gpx"
    f.write_text(SAMPLE_GPX, encoding="utf-8")
    return f


@pytest.fixture
def wpts_file(tmp_path) -> Path:
    f = tmp_path / "test-wpts.gpx"
    f.write_text(SAMPLE_WPTS_GPX, encoding="utf-8")
    return f


@pytest.fixture
def zip_file(tmp_path, gpx_file, wpts_file) -> Path:
    z = tmp_path / "test_pq.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(gpx_file,  "test.gpx")
        zf.write(wpts_file, "test-wpts.gpx")
    return z


# ── Basic import tests ────────────────────────────────────────────────────────

def test_import_gpx_returns_result(tmp_db, gpx_file):
    with get_session() as s:
        result = import_gpx(gpx_file, s)
    assert result.total == 2
    assert result.created == 2
    assert result.skipped == 0
    assert result.errors == []


def test_import_gpx_cache_fields(tmp_db, gpx_file):
    """Verify all scalar fields are correctly parsed and stored."""
    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC12345").one()
        assert cache.name == "Test Traditional"
        assert cache.cache_type == "Traditional Cache"
        assert cache.container == "Small"
        assert cache.latitude == pytest.approx(55.6761)
        assert cache.longitude == pytest.approx(12.5683)
        assert cache.difficulty == pytest.approx(2.0)
        assert cache.terrain == pytest.approx(3.0)
        assert cache.placed_by == "TestOwner"
        assert cache.country == "Denmark"
        assert cache.state == "Zealand"
        assert cache.county == "Copenhagen"
        assert cache.encoded_hints == "Under a rock."
        assert cache.available is True
        assert cache.archived is False
        assert cache.short_desc_html is False
        assert cache.long_desc_html is True


def test_import_gpx_logs(tmp_db, gpx_file):
    """Verify logs are imported with correct fields."""
    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC12345").one()
        assert len(cache.logs) == 2
        found_log = next(l for l in cache.logs if l.log_type == "Found it")
        assert found_log.finder == "Tester"
        assert found_log.log_id == "111"
        assert found_log.log_date is not None
        # SQLite stores datetimes without tz info — just verify the values
        assert found_log.log_date.year == 2026
        assert found_log.log_date.month == 1
        assert found_log.log_date.day == 15


def test_import_gpx_attributes(tmp_db, gpx_file):
    """Verify attributes are imported correctly."""
    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC12345").one()
        assert len(cache.attributes) == 2
        kids_attr = next(a for a in cache.attributes if a.attribute_id == 6)
        assert kids_attr.name == "Recommended for kids"
        assert kids_attr.is_on is True
        wheelchair = next(a for a in cache.attributes if a.attribute_id == 24)
        assert wheelchair.is_on is False


def test_import_gpx_second_cache(tmp_db, gpx_file):
    """Verify the second cache (Unknown) is also imported."""
    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC99999").one()
        assert cache.cache_type == "Unknown Cache"
        assert cache.container == "Micro"
        assert cache.difficulty == pytest.approx(4.0)
        assert len(cache.logs) == 0
        assert len(cache.attributes) == 0


# ── Waypoints tests ───────────────────────────────────────────────────────────

def test_import_with_companion_wpts(tmp_db, gpx_file, wpts_file):
    """Verify companion -wpts.gpx waypoints are linked to the correct cache."""
    with get_session() as s:
        result = import_gpx(gpx_file, s, wpts_path=wpts_file)
    assert result.waypoints == 1

    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC12345").one()
        assert len(cache.waypoints) == 1
        wp = cache.waypoints[0]
        assert wp.wp_type == "Parking Area"
        assert wp.prefix == "PK"
        assert wp.latitude == pytest.approx(55.6762)
        assert wp.comment == "Park here and walk 200m south."


# ── ZIP import tests ──────────────────────────────────────────────────────────

def test_import_zip(tmp_db, zip_file):
    """Verify that a PQ zip file is imported correctly end-to-end."""
    # Reset DB for clean test — must delete children before parents (FK constraints)
    with get_session() as s:
        for cache in s.query(Cache).all():
            s.delete(cache)

    with get_session() as s:
        result = import_zip(zip_file, s)

    assert result.total == 2
    assert result.waypoints == 1
    assert result.errors == []


def test_import_zip_invalid(tmp_db, tmp_path):
    """A non-zip file should return an error, not raise an exception."""
    bad = tmp_path / "bad.zip"
    bad.write_text("this is not a zip file")
    with get_session() as s:
        result = import_zip(bad, s)
    assert len(result.errors) > 0


# ── Upsert / duplicate handling ───────────────────────────────────────────────

def test_reimport_updates_not_duplicates(tmp_db, gpx_file):
    """Importing the same file twice should update, not duplicate."""
    with get_session() as s:
        import_gpx(gpx_file, s)

    with get_session() as s:
        import_gpx(gpx_file, s)

    with get_session() as s:
        count = s.query(Cache).filter_by(gc_code="GC12345").count()
        assert count == 1, "Duplicate cache rows created on re-import!"

    with get_session() as s:
        cache = s.query(Cache).filter_by(gc_code="GC12345").one()
        log_count = len(cache.logs)
        assert log_count == 2, f"Expected 2 logs after re-import, got {log_count}"


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_import_empty_gpx(tmp_db, tmp_path):
    """A GPX file with no <wpt> elements should import cleanly with 0 results."""
    empty = tmp_path / "empty.gpx"
    empty.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/0" version="1.0">'
        '<n>Empty</n></gpx>',
        encoding="utf-8",
    )
    with get_session() as s:
        result = import_gpx(empty, s)
    assert result.total == 0
    assert result.errors == []


def test_import_corrupt_gpx(tmp_db, tmp_path):
    """A corrupt XML file should return an error gracefully."""
    bad = tmp_path / "corrupt.gpx"
    bad.write_text("<<<not xml at all>>>", encoding="utf-8")
    with get_session() as s:
        result = import_gpx(bad, s)
    assert len(result.errors) > 0
