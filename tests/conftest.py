"""
tests/conftest.py — Shared fixtures for OpenSAK tests.
"""

import pytest
from opensak.db.database import init_db, make_session
from opensak.db.models import Cache


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    """Create a fresh SQLite DB in a temp directory for a test module."""
    db_path = tmp_path_factory.mktemp("data") / "test.db"
    init_db(db_path=db_path)
    return db_path


@pytest.fixture
def db_session(tmp_path):
    """Fresh isolated DB + bare Session for each test. Caller must commit."""
    db_path = tmp_path / "test.db"
    init_db(db_path=db_path)
    session = make_session()
    yield session
    session.close()


@pytest.fixture
def make_cache():
    """Return a factory that builds Cache instances with sensible defaults."""
    def _factory(gc_code: str = "GC12345", **kwargs) -> Cache:
        defaults = dict(
            name="Test Cache",
            cache_type="Traditional Cache",
            latitude=55.0,
            longitude=12.0,
        )
        defaults.update(kwargs)
        return Cache(gc_code=gc_code, **defaults)
    return _factory
