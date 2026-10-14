"""Owned FSM death registration, distinct from unknown HP0/KO snapshots.

Client eGj.baG reads fcb/fdt/fdy's corpse registry, not the HP field.
Owned damage and verified eZI current-HP updates register adjacent HP0/death
events. Those explicit transitions supply the server corpse registry contract;
raw HP0 alone never does. Events are part of the durable Fight checkpoint.
"""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT


def owned_fighter_guards(fight, actor):
    """Use actual fdy producer when present; retain the older owned domain.

    HP is never used to change an explicitly registered fdy status. Legacy
    actors have no OUT_OF_PLAY producer; unproved HP0 keeps baG unknown.
    """
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_fighter_guards

        return global_fighter_guards(fight, actor.id)
    from .combat_range_conditions import creation_in_play

    in_play = creation_in_play(fight, actor)
    has_death = any(
        event.get("kind") == "death" and event.get("actor_id") == actor.id
        for event in fight.events
    )
    off_play = (
        registered_ordinary_death(fight, actor)
        if has_death and actor.hp == 0
        else False
        if in_play is True
        else None
    )
    return dict(baF=in_play, baG=off_play, baK=False)


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
        damage = previous.get("kind") == "damage"
        percentage_hp = (
            previous.get("kind") == "percentage_hp_update"
            and previous.get("effect_class") == 986
            and type(previous.get("uid")) is int
            and previous["uid"] > 0
            and type(previous.get("hp_before")) is int
            and previous["hp_before"] > 0
            and type(previous.get("maximum")) is int
            and previous["maximum"] >= 0
        )
        kill_minimum = (
            previous.get("kind") == "kill_hp_minimum_update"
            and previous.get("effect_class") == 28
            and type(previous.get("uid")) is int
            and previous["uid"] > 0
            and type(previous.get("hp_before")) is int
            and previous["hp_before"] > 0
            and type(previous.get("minimum")) is int
            and previous["minimum"] == 0
        )
        hp_minimum = (
            previous.get("kind") == "hp_minimum_update"
            and type(previous.get("effect_class")) is int
            and previous["effect_class"] == 830
            and type(previous.get("uid")) is int
            and previous["uid"] > 0
            and type(previous.get("hp_before")) is int
            and previous["hp_before"] > 0
            and type(previous.get("minimum")) is int
            and previous["minimum"] == 0
            and type(previous.get("hp")) is int
            and previous["hp"] == 0
            and type(previous.get("source_id")) is int
            and type(previous.get("target_id")) is int
            and type(previous.get("sequence")) is int
            and type(event.get("sequence")) is int
            and type(event.get("actor_id")) is int
        )
        summon_recall_minimum = (
            previous.get("kind") == "summon_recall_hp_minimum_update"
            and previous.get("effect_class") == 859
            and type(previous.get("uid")) is int
            and previous["uid"] > 0
            and type(previous.get("hp_before")) is int
            and previous["hp_before"] > 0
            and previous.get("minimum") == 0
        )
        if (
            (
                damage
                or percentage_hp
                or kill_minimum
                or hp_minimum
                or summon_recall_minimum
            )
            and previous.get("target_id") == actor.id
            and previous.get("hp") == 0
            and previous.get("source_id") in fight.actors
            and previous.get("sequence", -2) + 1 == event.get("sequence", -1)
        ):
            return True
        raise ValueError("Unverified owned ordinary corpse transition")
    raise ValueError("Ordinary HP0 has no owned corpse registration")


def corpse_gate_bypassed(effect, *, fight=None, invocation=None):
    """Evaluate the original eZR.bcd inputs for a corpse-gated activation.

    A missing value is still unknown. For a captured listener, the original PL
    is carried by ``invocation.native_retained_container``; the triggering
    event's PL is not interchangeable with it. The effect's aZL mask is
    ``target_masks[5]`` and is independent of the event source IDs.
    """
    return _runner_policy(effect, fight=fight, invocation=invocation)


@lru_cache(maxsize=1)
def _policies():
    return protocol_catalog.load(DATA_ROOT / "native-runner-corpse-policy.json")[
        "effects"
    ]


def _runner_policy(effect, *, fight=None, invocation=None):
    row = _policies().get(str(effect["effect_class"]))
    if row is None:
        raise ValueError("Missing native runner corpse policy")
    value = row["bcd_constant"]
    if type(value) is bool:
        return value
    if row["owner"] != "eZR":
        raise ValueError("Missing native runner corpse policy")

    def unknown(reason):
        raise ValueError(
            f"Dynamic native corpse guard requires explicit authority: {reason}"
        )

    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (list, tuple)) or any(
        type(flag) is not int for flag in flags
    ):
        unknown("native eZR definition flags")
    # eZR.bcd first tests eVl.rwL (15).
    if 15 in flags:
        return True

    # eZR.fSe tests its own PL, not the event's source PL. A state-owned
    # listener is always the state container (type 1); a replayed ordinary
    # listener carries the exact PL snapshot captured at registration.
    if invocation is not None and getattr(invocation, "state_uid", None) is not None:
        special_container = False
    else:
        direct = (
            None
            if invocation is None
            else getattr(invocation, "native_retained_container", None)
        )
        if direct is not None:
            if not isinstance(direct, dict) or type(direct.get("present")) is not bool:
                unknown("malformed retained PL context")
            if not direct["present"]:
                special_container = False
            else:
                kind = direct.get("type")
                spell_id = direct.get("spell_id")
                if type(kind) is not int or type(direct.get("is_spell")) is not bool:
                    unknown("incomplete retained PL identity")
                if kind != 25 or direct["is_spell"] is not True:
                    special_container = False
                elif type(spell_id) is int:
                    special_container = spell_id == 2040
                else:
                    unknown("retained spell reference")
        elif fight is not None:
            # Fresh casts bind the current PZ; an unbound identifier is not a
            # null PL. Spell 2040 needs the exact type-25 source before admit.
            if not hasattr(fight, "native_active_spell_id"):
                unknown("actual native PZ context")
            spell_id = fight.native_active_spell_id
            if spell_id is None:
                special_container = False
            elif type(spell_id) is not int:
                unknown("malformed actual native PZ reference")
            elif spell_id != 2040:
                special_container = False
            else:
                descriptor = getattr(fight, "native_active_spell_container", None)
                kind = descriptor.get("type") if isinstance(descriptor, dict) else None
                if type(kind) is not int:
                    unknown("actual native PZ container type")
                special_container = kind == 25
        else:
            unknown("actual native PL context")
    if special_container:
        return True

    # Qe.bbv() delegates to PK.aZL(). The shared effect export stores aZG…aZO
    # in target_masks, so aZL is index 5. A null BitSet is a proven false bit.
    masks = effect.get("target_masks")
    if not isinstance(masks, (list, tuple)) or len(masks) != 7:
        unknown("native eZR definition masks")
    mask = masks[5]
    if mask is None:
        return False
    if not isinstance(mask, (list, tuple, set, frozenset)) or any(
        type(bit) is not int or bit < 0 for bit in mask
    ):
        unknown("malformed native eZR aZL BitSet")
    if 1010 in mask:
        return True
    return False
