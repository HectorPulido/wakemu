"""Frozen opt-in excavation rules; no source is inferred from item parameters."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def rules():
    return json.loads(Path(__file__).with_suffix(".json").read_text())["rules"]


def scene_enabled(map_id):
    return any(
        r.get("enabled") is True and r["ground_authority"]["map_id"] == map_id
        for r in rules()
    )


def by_key(key):
    found = [r for r in rules() if r["key"] == key and r.get("enabled") is True]
    if len(found) != 1:
        raise ValueError("Excavation rule is not uniquely enabled")
    return found[0]
