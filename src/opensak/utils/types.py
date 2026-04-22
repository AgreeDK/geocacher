"""
src/opensak/utils/types.py — Core enumerations and type aliases.

Defines shared Enums and TypeAliases used across the codebase so that
function signatures are self-documenting and the type checker can enforce
valid values at call sites (instead of accepting any string).
"""

from enum import Enum, IntEnum, StrEnum, auto
from typing import TypeAlias


# ── Import / log enums ────────────────────────────────────────────────────────

class ImportType(Enum):
    """Supported import file formats."""
    GPX = auto()
    ZIP = auto()


class LogType(IntEnum):
    """Groundspeak cache log types, mapped to their integer IDs."""
    FOUND = 2
    DNF = 3
    NOTE = 4
    ARCHIVE = 5


# ── Coordinate types ──────────────────────────────────────────────────────────

class CoordFormat(StrEnum):
    """
    Supported coordinate display formats.

    Using StrEnum means values still serialise/compare as plain strings
    ("dd", "dmm", "dms"), so existing persisted settings keep working.
    """
    DD  = "dd"   # 55.78750, 12.41667
    DMM = "dmm"  # N55 47.250 E012 25.000
    DMS = "dms"  # N55° 47' 15" E012° 25' 00"


# (lat, lon) in decimal degrees — WGS-84.
Coordinate: TypeAlias = tuple[float, float]

# Geocaching.com cache code (e.g. "GC12ABC"). Aliased for intent, not runtime safety.
GcCode: TypeAlias = str
