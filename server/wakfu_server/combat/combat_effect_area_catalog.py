"""Installed area root closure, precompiled together with ordinary effects."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def area_effect_catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("native-area-effect-trees.json")

    return protocol_catalog.load(DATA_ROOT / "native-area-effect-trees.json")
