"""Native eJy.tt aliases shared by current, maximum and percentage predicates."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_aliases():
    published = protocol_catalog.load(
        DATA_ROOT / "characteristic-condition-aliases.json"
    )["aliases"]
    aliases = dict(published)
    # Original eJy.tt explicitly maps case-insensitive "contrôle" to LEADERSHIP.
    # The installed alias export omitted that spelling; reuse its actual native
    # target entry without modifying the cached catalog or inventing a PC ID.
    leadership = aliases.get("LEADERSHIP")
    if (
        not isinstance(leadership, dict)
        or leadership.get("name") != "LEADERSHIP"
        or type(leadership.get("id")) is not int
        or leadership["id"] <= 0
    ):
        raise ValueError("Missing native LEADERSHIP alias authority")
    accented = aliases.get("CONTRÔLE")
    if accented is not None and accented != leadership:
        raise ValueError("Conflicting native contrôle characteristic alias")
    aliases["CONTRÔLE"] = dict(leadership)
    return aliases


def canonical_aliases():
    return {alias: row["name"] for alias, row in native_aliases().items()}


def characteristic_ids():
    return {row["name"]: row["id"] for row in native_aliases().values()}
