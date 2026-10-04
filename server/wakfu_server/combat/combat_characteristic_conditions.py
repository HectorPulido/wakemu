"""Native eJy.tt aliases shared by current, maximum and percentage predicates."""
import json
from functools import lru_cache
from .paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_aliases():
    return json.loads(
        (DATA_ROOT / "characteristic-condition-aliases.json").read_text()
    )["aliases"]


def canonical_aliases():
    return {alias: row["name"] for alias, row in native_aliases().items()}


def characteristic_ids():
    return {row["name"]: row["id"] for row in native_aliases().values()}
