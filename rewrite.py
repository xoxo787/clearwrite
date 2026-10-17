#!/usr/bin/env python3
"""Uninstalled source checkout entry point; resolves relative to this file."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from clearwrite.cli import main
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] if len(sys.argv) > 1 else ["serve", "--open"]))
