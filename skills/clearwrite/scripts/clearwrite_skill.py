#!/usr/bin/env python3
"""Self-contained skill entrypoint. No dependence on upstream repo layout."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from clearwrite.cli import main
if __name__=='__main__':
    raise SystemExit(main())
