#!/usr/bin/env python3
"""Atalho para a CLI do projeto."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forti_report.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
