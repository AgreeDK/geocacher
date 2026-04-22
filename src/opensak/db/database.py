"""
database.py — Database engine, session factory, and initialisation helpers.

Usage
-----
    from opensak.db.database import init_db, get_session

    init_db()                    # create tables if they don't exist
    with get_session() as session:
        caches = session.query(Cache).all()
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from opensak.db.models import Base


# ── Engine factory ────────────────────────────────────────────────────────────

def _make_engine(db_path: Path) -> Engine:
    """Create a SQLAlchemy engine for a SQLite file at *db_path*."""
    # Ensure parent directory exists (pathlib — cross-platform safe)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"sqlite:///{db_path}"
    engine = create_engine(
        url,
        echo=False,          # set True to log all SQL (useful for debugging)
        future=True,
        connect_args={"check_same_thread": False},
    )
    return engine


@event.listens_for(Engine, "connect")
def _enable_wal_and_fk(dbapi_connection, _connection_record) -> None:
    """
    Enable WAL journal mode (better concurrency) and foreign key enforcement
    every time a new SQLite connection is opened.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── Module-level singletons (initialised lazily) ─────────────────────────────

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_migrated_paths: set = set()  # undgår at køre migrationer to gange på samme DB


def init_db(db_path: Path | None = None) -> Engine:
    """
    Initialise the database: create all tables if they don't exist.

    Parameters
    ----------
    db_path : Path, optional
        Override the default database location.  If omitted the path from
        ``opensak.config.get_db_path()`` is used.

    Returns
    -------
    Engine
        The SQLAlchemy engine (useful for tests that want to inspect it).
    """
    global _engine, _SessionLocal

    if db_path is None:
        # Brug aktiv database fra manager hvis tilgængelig,
        # ellers fald tilbage til standard stien (bruges af tests)
        try:
            from opensak.db.manager import get_db_manager
            manager = get_db_manager()
            if manager.active_path:
                db_path = manager.active_path
            else:
                from opensak.config import get_db_path
                db_path = get_db_path()
        except Exception:
            from opensak.config import get_db_path
            db_path = get_db_path()

    _engine = _make_engine(db_path)
    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,  # keep objects usable after session closes
    )

    # Create all tables that don't exist yet (safe to call multiple times)
    Base.metadata.create_all(_engine)

    # Kør schema-migrationer for eksisterende databaser (kun én gang per DB-sti)
    if db_path not in _migrated_paths:
        _run_migrations(_engine)
        _migrated_paths.add(db_path)

    return _engine


# ── Schema migrationer ────────────────────────────────────────────────────────

def _run_migrations(engine: Engine) -> None:
    """
    Kør inkrementelle schema-migrationer på en eksisterende database.

    Hver migration tjekker om kolonnen/tabellen allerede findes og springer
    over hvis ja — så er det sikkert at kalde ved hver opstart.
    """
    with engine.connect() as conn:
        # ── Migration 1: Tilføj is_corrected til user_notes ──────────────────
        existing = [
            row[1]
            for row in conn.execute(text("PRAGMA table_info(user_notes)")).fetchall()
        ]
        if "is_corrected" not in existing:
            conn.execute(text(
                "ALTER TABLE user_notes ADD COLUMN is_corrected BOOLEAN NOT NULL DEFAULT 0"
            ))
            conn.commit()
            print("Migration: tilføjede user_notes.is_corrected")

        # ── Migration 2: Udvid waypoints unique constraint ────────────────────
        # Den gamle constraint (cache_id, prefix) fejler når GSAK eksporterer
        # flere waypoints med samme prefix (f.eks. "WP") for samme cache.
        # Ny constraint: (cache_id, prefix, name) — tillader flere WP-waypoints
        # så længe de har forskellige navne.
        idx_rows = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='waypoints'"
        )).fetchall()
        idx_names = [r[0] for r in idx_rows]

        if "uq_waypoint_cache_prefix_name" not in idx_names:
            # SQLite understøtter ikke DROP CONSTRAINT — vi recreater tabellen
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("""
                CREATE TABLE waypoints_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_id    INTEGER NOT NULL REFERENCES caches(id),
                    prefix      TEXT,
                    wp_type     TEXT,
                    name        TEXT,
                    description TEXT,
                    comment     TEXT,
                    latitude    REAL,
                    longitude   REAL,
                    UNIQUE(cache_id, prefix, name)
                )
            """))
            conn.execute(text(
                "INSERT INTO waypoints_new "
                "SELECT id, cache_id, prefix, wp_type, name, description, comment, latitude, longitude "
                "FROM waypoints"
            ))
            conn.execute(text("DROP TABLE waypoints"))
            conn.execute(text("ALTER TABLE waypoints_new RENAME TO waypoints"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_waypoints_cache_id ON waypoints (cache_id)"
            ))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
            print("Migration: opdaterede waypoints unique constraint til (cache_id, prefix, name)")

        # ── Migration 3: Add county column to caches ──────────────────────
        existing_caches = [
            row[1]
            for row in conn.execute(text("PRAGMA table_info(caches)")).fetchall()
        ]
        if "county" not in existing_caches:
            conn.execute(text(
                "ALTER TABLE caches ADD COLUMN county VARCHAR(64)"
            ))
            conn.commit()
            print("Migration: added caches.county")


def get_engine() -> Engine:
    """Return the current engine, raising if init_db() hasn't been called."""
    if _engine is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context-manager that yields a SQLAlchemy Session and handles
    commit / rollback automatically.

    Example
    -------
        with get_session() as session:
            session.add(some_object)
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() first.")

    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def make_session():
    """Return a bare Session — caller handles commit/rollback/close."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() first.")
    return _SessionLocal()


# ── Health-check helper ───────────────────────────────────────────────────────

def db_health_check() -> dict:
    """
    Return a dict with basic stats about the current database.
    Useful for the startup banner and diagnostics.
    """
    from opensak.db.models import Cache, Log, Waypoint

    with get_session() as s:
        return {
            "caches": s.query(Cache).count(),
            "logs": s.query(Log).count(),
            "waypoints": s.query(Waypoint).count(),
        }
