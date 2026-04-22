"""
tests/conftest.py — Shared fixtures for OpenSAK tests.
"""

import pytest
from opensak.db.database import init_db


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    """Create a fresh SQLite DB in a temp directory for a test module."""
    db_path = tmp_path_factory.mktemp("data") / "test.db"
    init_db(db_path=db_path)
    return db_path
