"""Verified client monster references, without implied official spawn locations."""
from .paths import DATA_ROOT
import json
import math
import struct
from pathlib import Path

CATALOG = json.loads((DATA_ROOT / "monsters.json").read_text())
REFERENCES = {monster["ref"]: monster for monster in CATALOG["monsters"]}


def reference(ref):
    if type(ref) is not int or ref not in REFERENCES:
        raise ValueError("Unknown monster reference")
    return REFERENCES[ref]


def _java_double_to_int(value):
    # ffC.b uses d2i, which truncates and saturates; the subsequent iadd wraps.
    if math.isnan(value):
        return 0
    return min(2**31 - 1, max(-(2**31), math.trunc(value)))


def statistics(ref, level):
    monster = reference(ref)
    if (
        type(level) is not int
        or not monster["min_level"] <= level <= monster["max_level"]
        or not 0 <= level < 2**15
    ):
        raise ValueError("Monster level outside its reference range")
    stats = {}
    for name, curve in monster["statistics"].items():
        growth = struct.unpack(">f", struct.pack(">f", curve["per_level"]))[0]
        value = curve["base"] + _java_double_to_int(
            (level - monster["min_level"]) * growth
        )
        stats[name] = ((value + 2**31) % 2**32) - 2**31
    return stats


def owned_instance(ref, level, actor_id, *, map_id, x, y, z, team=1):
    """Construct an explicitly placed local actor; no official population replay.

    World/combat encoders must consume the verified reference and supplied own
    ID. Spell forms are data only until their conditions and casts are validated.
    """
    monster = reference(ref)
    stats = statistics(ref, level)
    if (
        type(actor_id) is not int
        or actor_id == 0
        or not -(2**63) <= actor_id < 2**63
    ):
        raise ValueError("Invalid owned actor ID")
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(team) is not int
        or team not in (0, 1)
    ):
        raise ValueError("Invalid local monster map or team")
    if (
        any(type(v) is not int for v in (x, y, z))
        or not -(2**31) <= x < 2**31
        or not -(2**31) <= y < 2**31
        or not -(2**15) <= z < 2**15
    ):
        raise ValueError("Invalid local monster position")
    if stats["HP"] <= 0 or any(stats[name] < 0 for name in ("AP", "MP", "WP")):
        raise ValueError("Reference cannot initialize a living local fighter")
    return dict(
        id=actor_id,
        ref=ref,
        breed=ref,
        level=level,
        effective_level=level,
        map_id=map_id,
        instance_id=0,
        x=x,
        y=y,
        z=z,
        team=team,
        hp=stats["HP"],
        max_hp=stats["HP"],
        ap=stats["AP"],
        mp=stats["MP"],
        wp=stats["WP"],
        initiative=stats["INIT"],
        sprite_id=monster["sprite_id"],
    )


def native_abilities(ref, level):
    """Native csd ownership and bPD effective levels; CSR is exclusively loot."""
    record = reference(ref)
    statistics(ref, level)  # Validate requested actor level against this reference.
    return [
        dict(
            spell_id=ability["spell_id"],
            level_parameter=ability["level_parameter"],
            spell_level=level
            if ability["level_parameter"] == -1
            else ability["level_parameter"],
        )
        for ability in record["native_abilities"]
    ]
