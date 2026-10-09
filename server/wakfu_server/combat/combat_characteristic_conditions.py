"""Native eJy.tt aliases shared by current, maximum and percentage predicates."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_aliases():
    return protocol_catalog.load(DATA_ROOT / "characteristic-condition-aliases.json")[
        "aliases"
    ]


def canonical_aliases():
    return {alias: row["name"] for alias, row in native_aliases().items()}


def characteristic_ids():
    return {row["name"]: row["id"] for row in native_aliases().values()}
