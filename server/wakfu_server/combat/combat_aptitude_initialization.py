"""Owned conditional aptitude roots, using the native eQr container.

eQr.aZY returns 36; eVs.A computes an int32 bonus identity shifted by 16
with the low byte of its allocated points. These are not spell containers.
Flat aptitude characteristics are already installed in actor snapshots and
must not be applied twice here.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from copy import deepcopy
from functools import lru_cache

from wakfu_server import aptitudes
from wakfu_server.paths import DATA_ROOT
from .combat_effect_dispatch import EffectInvocation

CONDITIONAL_BONUSES = frozenset((17, 27, 36))


@lru_cache(maxsize=1)
def effect_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-aptitude-effect-closure.json")


def plan(character):
    index = character.get("active_build_index", 0)
    blob = bytes.fromhex(
        character.get("builds", {}).get(index, {}).get("aptitudes", "")
    )
    if not blob:
        return ()
    allocations = aptitudes.validate(character, blob)["allocations"]
    effects = effect_catalog()["effects"]
    result = []
    for bonus, points in allocations.items():
        if bonus not in CONDITIONAL_BONUSES or not points:
            continue
        root = aptitudes.EFFECTS[bonus]["effect"]
        pending, seen = [root], set()
        while pending:
            reference = pending.pop()
            if reference in seen:
                continue
            seen.add(reference)
            row = effects.get(str(reference))
            if row is None:
                raise ValueError("Missing native aptitude effect closure")
            pending.extend(row["children"])
        identity = ((bonus << 16) + (points & 255)) & 0xFFFFFFFF
        if identity >= 0x80000000:
            identity -= 0x100000000
        result.append((bonus, points, root, identity))
    return tuple(result)


def initialize_transaction(fight, character, runtime_factory, *, owner_id):
    initial = plan(character)
    if not initial:
        return fight, ()
    actor = fight.actors.get(character["id"])
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != owner_id
        or fight.phase != "active"
    ):
        raise ValueError("Aptitude initialization requires an owned active fighter")
    previous = getattr(fight, "native_class_initializations", {})
    if actor.id not in previous:
        raise ValueError(
            "Owned class initialization must precede aptitude registration"
        )
    if "aptitudes" in previous[actor.id]:
        raise ValueError("Fighter aptitude effects are already initialized")
    preview = deepcopy(fight)
    packets = []
    with preview.effect_resolution():
        for bonus, points, root, identity in initial:
            dispatcher, outbox = runtime_factory(
                preview,
                {
                    "evaluation_level": points,
                    "native_retained_container": {
                        "present": True,
                        "type": 36,
                        "id": identity,
                        "is_spell": False,
                        "native_kind": "aptitude",
                        "level": points,
                    },
                },
            )
            dispatcher.execute(
                EffectInvocation(root, points, actor.id, actor.id, actor.position)
            )
            packets.extend(outbox)
    preview.native_class_initializations[actor.id]["aptitudes"] = initial
    return preview, tuple(packets)
