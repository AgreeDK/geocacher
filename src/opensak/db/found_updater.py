"""
src/opensak/db/found_updater.py — Opdater 'fundet' status i aktiv database
baseret på en reference database (f.eks. 'Mine Fund').

Workflow:
1. Brugeren har en 'Mine Fund' database med alle fundne caches
2. Brugeren kører opdatering mod en anden database (f.eks. 'Sjælland')
3. Alle caches der findes i begge databaser markeres som fundet
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from opensak.db.database import get_session
from opensak.db.models import Cache
from opensak.utils.types import GcCode


@dataclass
class UpdateResult:
    """Resultat af en fund-opdatering."""
    updated:   int = 0       # caches markeret som fundet
    already:   int = 0       # var allerede markeret som fundet
    not_found: int = 0       # i reference DB men ikke i aktiv DB
    errors:    list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"  Opdateret til fundet : {self.updated}\n"
            f"  Allerede fundet      : {self.already}\n"
            f"  Ikke i denne DB      : {self.not_found}"
        )


def get_found_gc_codes(reference_db_path: Path) -> set[GcCode]:
    """
    Hent alle GC koder fra reference databasen.
    Returnerer et set af GC koder.
    """
    url = f"sqlite:///{reference_db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT gc_code FROM caches")).fetchall()
            return {row[0] for row in rows if row[0]}
    except Exception as e:
        raise RuntimeError(f"Kunne ikke læse reference database: {e}")
    finally:
        engine.dispose()


def update_found_from_reference(reference_db_path: Path) -> UpdateResult:
    """
    Opdater 'found' status i den aktive database baseret på
    GC koder fra reference databasen.

    Parameters
    ----------
    reference_db_path : Path til reference databasen (f.eks. Mine Fund)

    Returns
    -------
    UpdateResult med statistik over opdateringen
    """
    result = UpdateResult()

    # Hent alle GC koder fra reference databasen
    try:
        found_codes = get_found_gc_codes(reference_db_path)
    except RuntimeError as e:
        result.errors.append(str(e))
        return result

    if not found_codes:
        result.errors.append("Ingen caches fundet i reference databasen")
        return result

    # Opdater aktiv database
    with get_session() as session:
        # Hent alle caches i aktiv database der matcher
        all_caches = session.query(Cache).all()

        for cache in all_caches:
            if cache.gc_code in found_codes:
                if cache.found:
                    result.already += 1
                else:
                    cache.found = True
                    result.updated += 1
            # Vi tæller ikke not_found her da de fleste PQ databaser
            # kun har et udsnit af alle fundne caches

        # Tæl hvor mange GC koder i reference DB ikke er i aktiv DB
        active_codes = {c.gc_code for c in all_caches}
        result.not_found = len(found_codes - active_codes)

    return result
