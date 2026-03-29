#!/usr/bin/env python3
"""
run.py — Start OpenSAK from the repo root.

Usage:
    python run.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from opensak.app import main

if __name__ == "__main__":
    main()
