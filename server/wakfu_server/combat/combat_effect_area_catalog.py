"""Installed area root closure, precompiled together with ordinary effects."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def area_effect_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-area-effect-trees.json")
