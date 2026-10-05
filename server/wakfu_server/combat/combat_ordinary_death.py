"""Owned FSM death registration, distinct from unknown HP0/KO snapshots.

Client eGj.baG reads fcb/fdt/fdy's corpse registry, not the HP field.
The local ordinary fight has no KO/revival transition: apply_effect_damage
registers a death event immediately after its HP0 damage event. That explicit
owned transition supplies the server corpse registry contract; raw HP0 alone
never does. The events are already part of the durable Fight checkpoint.
"""
from functools import lru_cache
import json
from .paths import DATA_ROOT


def registered_ordinary_death(fight, actor):
    if actor.hp > 0:
        return False
    if actor.hp != 0 or fight.actors.get(actor.id) is not actor:
        raise ValueError("Invalid owned ordinary death actor")
    events = getattr(fight, "events", None)
    if not isinstance(events, list):
        raise ValueError("Missing owned ordinary death registration")
    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if event.get("kind") != "death" or event.get("actor_id") != actor.id:
            continue
        previous = events[index - 1] if index else {}
        if (
            previous.get("kind") == "damage"
            and previous.get("target_id") == actor.id
            and previous.get("hp") == 0
            and previous.get("source_id") in fight.actors
            and previous.get("sequence", -2) + 1 == event.get("sequence", -1)
        ):
            return True
        raise ValueError("Unverified owned ordinary corpse transition")
    raise ValueError("Ordinary HP0 has no owned corpse registration")


def corpse_gate_bypassed(effect):
    """eZR.i/Qe.k consults virtual bcd; do not treat all groups as base eZR."""
    return _runner_policy(effect)


@lru_cache(maxsize=1)
def _policies():
    return json.loads((DATA_ROOT / "native-runner-corpse-policy.json").read_text())[
        "effects"
    ]


def _runner_policy(effect):
    row = _policies().get(str(effect["effect_class"]))
    if row is None:
        raise ValueError("Missing native runner corpse policy")
    value = row["bcd_constant"]
    if type(value) is bool:
        return value
    # Base eZR.bcd explicitly admits flag15 before its context-dependent
    # fSe/event1010 branches. Absence of flag15 does not attest those branches.
    if row["owner"] == "eZR" and 15 in effect.get("native_effect_flags", ()):
        return True
    raise ValueError("Dynamic native corpse guard requires explicit authority")
