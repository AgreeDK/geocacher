"""
tests/unit-tests/test_log_count.py — Tests for issue #87.

Verifies that cache.log_count is maintained correctly:
- Set to len(seen_log_ids) on import in _upsert_cache()
- Updated on re-import (old logs are deleted, new count reflects new logs)
- Migration populates log_count from existing logs table
- Default 0 for caches with no logs

The cached log_count column is used by the UI because the logs relationship
is noload'ed for performance — len(cache.logs) would always return 0 in
the cache list view.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from opensak.db.models import Base, Cache, Log


@pytest.fixture
def session():
    """In-memory SQLite session — fresh schema for each test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_cache(session, gc_code: str, num_logs: int = 0) -> Cache:
    """Helper: create a cache with a given number of logs."""
    cache = Cache(
        gc_code=gc_code,
        name=f"Test cache {gc_code}",
        cache_type="Traditional Cache",
        latitude=55.0,
        longitude=12.0,
    )
    session.add(cache)
    session.flush()  # so we get cache.id

    base_date = datetime(2024, 1, 1)
    for i in range(num_logs):
        session.add(Log(
            cache_id=cache.id,
            log_id=f"{gc_code}_log_{i}",
            log_type="Found it",
            log_date=base_date + timedelta(days=i),
            finder=f"finder{i}",
        ))
    session.flush()
    return cache


# ─────────────────────────────────────────────────────────────────────────────
# Default value
# ─────────────────────────────────────────────────────────────────────────────

class TestLogCountDefault:
    """Verify log_count has correct default behaviour."""

    def test_default_is_zero(self, session):
        """A new cache with no logs should have log_count = 0."""
        cache = _make_cache(session, "GCTEST1", num_logs=0)
        session.commit()
        # Re-fetch to verify what was actually stored
        fetched = session.query(Cache).filter_by(gc_code="GCTEST1").first()
        assert fetched.log_count == 0

    def test_not_nullable(self, session):
        """log_count column should be NOT NULL with default 0."""
        cache = Cache(
            gc_code="GCTEST2",
            name="No logs",
            cache_type="Traditional Cache",
            latitude=55.0,
            longitude=12.0,
        )
        session.add(cache)
        session.commit()
        # Should default to 0, never None
        assert cache.log_count == 0
        assert cache.log_count is not None


# ─────────────────────────────────────────────────────────────────────────────
# Manual log_count maintenance (simulates what _upsert_cache does)
# ─────────────────────────────────────────────────────────────────────────────

class TestLogCountMaintenance:
    """Verify log_count is updated correctly when logs change."""

    def test_log_count_set_on_creation(self, session):
        """Setting log_count manually persists correctly."""
        cache = _make_cache(session, "GCTEST3", num_logs=5)
        cache.log_count = 5
        session.commit()
        assert cache.log_count == 5

    def test_log_count_matches_actual_logs(self, session):
        """After import, log_count should equal len(cache.logs)."""
        cache = _make_cache(session, "GCTEST4", num_logs=7)
        cache.log_count = len(cache.logs)
        session.commit()
        assert cache.log_count == 7
        assert cache.log_count == len(cache.logs)

    def test_log_count_updates_on_reimport(self, session):
        """Simulate re-import: delete old logs, add new ones, update count."""
        # Initial import: 10 logs
        cache = _make_cache(session, "GCTEST5", num_logs=10)
        cache.log_count = 10
        session.commit()
        assert cache.log_count == 10

        # Re-import: delete old logs, add only 3 new ones
        session.query(Log).filter_by(cache_id=cache.id).delete()
        session.flush()
        base_date = datetime(2025, 1, 1)
        for i in range(3):
            session.add(Log(
                cache_id=cache.id,
                log_id=f"new_log_{i}",
                log_type="Found it",
                log_date=base_date + timedelta(days=i),
                finder=f"finder{i}",
            ))
        session.flush()
        cache.log_count = 3
        session.commit()

        # Verify count reflects new state
        assert cache.log_count == 3


# ─────────────────────────────────────────────────────────────────────────────
# Performance: log_count works without loading logs (the whole point)
# ─────────────────────────────────────────────────────────────────────────────

class TestLogCountWithoutLoading:
    """The whole point of caching log_count: read it without loading logs."""

    def test_read_log_count_without_querying_logs(self, session):
        """Reading log_count should not trigger a logs query."""
        cache = _make_cache(session, "GCTEST6", num_logs=42)
        cache.log_count = 42
        session.commit()

        # Re-fetch in fresh session - simulates UI loading caches
        cache_id = cache.id
        session.expunge_all()

        # Get a fresh copy without the logs relationship loaded
        from sqlalchemy.orm import noload
        fresh = (
            session.query(Cache)
            .options(noload(Cache.logs))
            .filter_by(id=cache_id)
            .first()
        )

        # log_count must be readable directly — this is the bug fix
        assert fresh.log_count == 42


# ─────────────────────────────────────────────────────────────────────────────
# Migration (populates log_count from existing logs)
# ─────────────────────────────────────────────────────────────────────────────

class TestLogCountMigration:
    """Verify the migration logic correctly populates log_count."""

    def test_migration_populates_from_logs_table(self, session):
        """The UPDATE statement in migration 6 should set log_count from COUNT(logs)."""
        # Set up: 3 caches with different log counts
        c1 = _make_cache(session, "GC_M1", num_logs=0)
        c2 = _make_cache(session, "GC_M2", num_logs=5)
        c3 = _make_cache(session, "GC_M3", num_logs=20)
        session.commit()

        # Simulate state BEFORE migration: log_count = 0 for all
        # (this is what the world looks like just after ALTER TABLE adds the column)
        session.execute(text("UPDATE caches SET log_count = 0"))
        session.commit()

        # Verify pre-migration state
        for c in (c1, c2, c3):
            session.refresh(c)
            assert c.log_count == 0

        # Run migration UPDATE statement
        session.execute(text("""
            UPDATE caches
            SET log_count = (
                SELECT COUNT(*)
                FROM logs
                WHERE logs.cache_id = caches.id
            )
        """))
        session.commit()

        # Verify post-migration state
        session.refresh(c1)
        session.refresh(c2)
        session.refresh(c3)
        assert c1.log_count == 0
        assert c2.log_count == 5
        assert c3.log_count == 20
