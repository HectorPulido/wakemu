"""Verified client monster references, without implied official spawn locations."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import math
import struct
from pathlib import Path

CATALOG = protocol_catalog.load(DATA_ROOT / "monsters.json")
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


def owned_instance(ref, level, actor_id, *, map_id, x, y, z, team=1, instance_id=0):
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
        or type(instance_id) is not int
        or not 0 <= instance_id < 2**63
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
    from wakfu_server.combat.combat_actor_snapshot import native_npc_creation_values

    # Native ffC curves feed ffx characteristic bounds before entering combat.
    # Keep statistics() as raw source data, but never publish an unbounded WP
    # value (for example the native Ogrest curve is 25 and the WP ceiling is 20).
    resources = native_npc_creation_values(ref, level)
    return dict(
        id=actor_id,
        ref=ref,
        breed=ref,
        level=level,
        effective_level=level,
        map_id=map_id,
        instance_id=instance_id,
        x=x,
        y=y,
        z=z,
        team=team,
        hp=resources[1]["current"],
        max_hp=resources[1]["maximum"],
        ap=resources[2]["current"],
        mp=resources[3]["current"],
        wp=resources[4]["current"],
        initiative=stats["INIT"],
        sprite_id=monster["sprite_id"],
    )


def native_abilities(ref, level):
    """Native csd/bPD ownership and bPO maximum-level clamp; CSR is loot."""
    record = reference(ref)
    statistics(ref, level)  # Validate requested actor level against this reference.
    from wakfu_server.combat_native_spell_casting import catalog

    casting = catalog()

    def spell_level(ability):
        definition = casting.get(str(ability["spell_id"]))
        if definition is None:
            raise ValueError("Missing native NPC spell definition")
        maximum = definition.get("maximum_level")
        if type(maximum) is not int or not 1 <= maximum <= 32767:
            raise ValueError("Missing native NPC spell maximum level")
        requested = (
            level if ability["level_parameter"] == -1 else ability["level_parameter"]
        )
        # bPD.a resolves -1 first; bPO(bPK,short,long,eGj) then applies
        # (short)Math.min(requested,bPK.Fq()). Zero/negative values are not raised.
        return min(requested, maximum)

    return [
        dict(
            spell_id=ability["spell_id"],
            level_parameter=ability["level_parameter"],
            spell_level=spell_level(ability),
        )
        for ability in record["native_abilities"]
    ]
