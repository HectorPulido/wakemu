"""Additive SQL-owned native Stasis branches, preserving existing NPC effects."""
from functools import lru_cache
import json
import os

from .dungeon_combat_scaling import POLICY

SETTING = "dungeon_combat_scaling_catalog"


def load(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return None
    value = row["value"]
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("policy") != POLICY
    ):
        raise ValueError("Invalid dungeon native scaling supplement")
    effects = value.get("effects")
    if not isinstance(effects, dict) or not effects:
        raise ValueError("Missing dungeon native scaling effects")
    for reference, effect in effects.items():
        if not reference.isdecimal() or effect.get("effect_class") not in (
            16,
            330,
            430,
        ):
            raise ValueError("Dungeon supplement contains an unsupported effect")
        if any(str(child) not in effects for child in effect.get("children", [])):
            raise ValueError("Dungeon supplement has an incomplete native closure")
    return value


@lru_cache(maxsize=1)
def current():
    """Optional before migration; runtime activation follows normal process load."""
    if not os.environ.get("WAKFU_DATABASE_URL"):
        return None
    from wakfu_server import native_catalog

    with native_catalog._database().connection() as db:
        return load(db)


def merge(effects, supplement=None):
    """Add original native references; conflicting existing effects are rejected."""
    document = current() if supplement is None else supplement
    if document is None:
        return effects
    merged = dict(effects)
    for reference, row in document["effects"].items():
        existing = merged.get(reference)
        if existing is not None:
            # Native exports can additionally carry sampled level arrays. The
            # exact retained/targeting/parameter source contract must agree.
            for key, expected in row.items():
                if json.dumps(existing.get(key), sort_keys=True) != json.dumps(
                    expected, sort_keys=True
                ):
                    raise ValueError(
                        "Dungeon supplement conflicts with an existing native effect"
                    )
        else:
            merged[reference] = row
    return merged
