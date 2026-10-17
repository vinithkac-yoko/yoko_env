"""Lets the tests import the helpers that sit next to them (tests/toy.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
