"""Stable catalogue CLI invoked by provisioning; implementation is in scripts."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.prepare_catalog_cache import main

if __name__ == "__main__":
    main()
