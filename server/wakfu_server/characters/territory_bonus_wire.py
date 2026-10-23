"""Native permanent protector icons, separate from owned consumable lifetimes.

Characteristic contributions remain in territory_bonuses. Display children use
original zero-value current-stat codecs; no protector stat is applied twice.
"""
from itertools import count
import struct

_ACTIONS = count(1)
# Original state definitions: level1, turn clock−1, realtime−1000.
_STATES = {
    1915: (
        (94088, 166, 36),
        (94089, 162, 33),
        (94331, 2007, None),
        (94332, 2008, None),
    ),
    1916: (
        (94090, 166, 36),
        (94091, 162, 33),
        (94329, 2007, None),
        (94330, 2008, None),
    ),
    1917: (
        (252635, 167, 36),
        (252636, 163, 33),
        (252637, 2007, None),
        (252638, 2008, None),
    ),
}


def _validate(state_id):
    if state_id is not None and (type(state_id) is not int or state_id not in _STATES):
        raise ValueError("Invalid native protector state")


def _records(actor_id, state_id):
    from wakfu_server.combat_state_carrier import state_carrier_payload
    from wakfu_server.combat_stat_effects import owned_effect_payload
    from wakfu_server.combat_running_container import running_container_scope
    from wakfu_server.combat_native_timing_context import native_time_payload

    # Keep the owner in each stable UID; this namespace is disjoint from food
    # state IDs, their bit62 children and bit61 transformation effects.
    if type(actor_id) is not int or not 0 < actor_id < 2**41:
        raise ValueError("Invalid regional icon actor identity")
    # Three low bits reserve a separate UID for every original child.
    carrier_uid = (1 << 58) | (actor_id << 17) | (state_id << 3)
    with running_container_scope(
        {"container_present": True, "container_type": 1}, (state_id << 16) | 1
    ):
        timer = native_time_payload(realtime_remaining=-1000)
        carrier = state_carrier_payload(
            uid=carrier_uid,
            base_uid=carrier_uid,
            caster_id=actor_id,
            target_id=actor_id,
            state_id=state_id,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=-1000,
            timing_payload=timer,
        )
        records = [(carrier_uid, 310, carrier)]
        for index, (reference, generic, stat) in enumerate(_STATES[state_id], 1):
            child_uid = carrier_uid | index
            kwargs = {} if stat is None else dict(stat_id=stat, requested=0)
            child = owned_effect_payload(
                uid=child_uid,
                base_uid=carrier_uid,
                generic_effect=reference,
                caster_id=actor_id,
                target_id=actor_id,
                value=0,
                timing_payload=timer,
                executed=False,
                **kwargs
            )
            if stat is None:
                # Original eXx stores profession0 (all professions) in Add19.
                from wakfu_server.combat_effects import _integer, _varint

                additional = _integer(19, 0)
                child += b"\x42" + _varint(len(additional)) + additional
            records.append((child_uid, generic, child))
    return tuple(records)


def delta(actor_id, previous_state_id, state_id, *, allocate_action=None):
    """Publish exact permanent-state replacement; None removes a prior icon."""
    _validate(previous_state_id)
    _validate(state_id)
    if previous_state_id == state_id:
        return ()
    from wakfu_server.combat_stat_effects import owned_effect_delivery
    from wakfu_server.combat_effect_removal import running_effect_removal

    action = allocate_action or (lambda: next(_ACTIONS))
    packets = []
    if previous_state_id is not None:
        for uid, generic, payload in reversed(_records(actor_id, previous_state_id)):
            packet = running_effect_removal(
                1,
                action(),
                effect_class=generic,
                uid=uid,
                target_id=actor_id,
                running_effect_payload=payload,
                notify_unapplication=True,
            )
            packets.append((13560, struct.pack(">i", -1) + packet[4:]))
    if state_id is not None:
        for uid, generic, payload in _records(actor_id, state_id):
            opcode, packet = owned_effect_delivery(
                1,
                action(),
                native_opcode=12613,
                effect_class=generic,
                uid=uid,
                target_id=actor_id,
                running_effect_payload=payload,
            )
            packets.append((opcode, struct.pack(">i", -1) + packet[4:]))
    return (*packets, (13420, struct.pack(">i", -1))) if packets else ()


def snapshot(actor_id, state_id, *, allocate_action=None):
    """Replay after native actor creation; caller owns the new socket fence."""
    return delta(actor_id, None, state_id, allocate_action=allocate_action)
