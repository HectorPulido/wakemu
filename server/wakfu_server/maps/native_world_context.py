"""Installed original WorldInfoManager flags, independent of combat category."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

WORLD_FLAGS_SHA256 = "513a0beed1653fc93d249767fba093604a84c3805d918ce44eaf6a9b24158851"


@lru_cache(maxsize=1)
def battleground_worlds():
    payload = Path(__file__).with_name("native_world_battlegrounds.json").read_bytes()
    if hashlib.sha256(payload).hexdigest() != WORLD_FLAGS_SHA256:
        raise ValueError("Conflicting native world battleground definition")
    value = json.loads(payload)
    worlds = value["worlds"]
    if (
        value.get("schema") != "native.eNo.eII.n.eGj.arM.WorldInfoManager.mP.eyc.v1"
        or not isinstance(worlds, dict)
        or len(worlds) != value["source"]["world_count"]
        or any(
            not identity.isdecimal() or type(flag) is not bool
            for identity, flag in worlds.items()
        )
        or sum(worlds.values()) != value["source"]["battleground_count"]
    ):
        raise ValueError("Invalid native world battleground definition")
    return frozenset(int(identity) for identity, flag in worlds.items() if flag)


def is_battleground(instance_id):
    """eNo: actual eGj.arM world lookup; missing native world info is false."""
    if type(instance_id) is not int or not -(1 << 63) <= instance_id < (1 << 63):
        raise ValueError("Missing native caster world instance identity")
    return instance_id in battleground_worlds()
