"""Installed area root closure, precompiled together with ordinary effects."""
import gzip
import json
from functools import lru_cache
from .paths import DATA_ROOT


@lru_cache(maxsize=1)
def area_effect_catalog():
    with gzip.open(DATA_ROOT / "native-area-effect-trees.json.gz", "rt") as stream:
        return json.load(stream)
