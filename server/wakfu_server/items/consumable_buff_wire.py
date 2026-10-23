"""Owned exploration food-state icons using original retained eZk carriers.

Children are evaluated by the server and its absolute characteristic sheet.
The native execution flag stays false, including on reconnect, so publishing
an icon never executes state children or reapplies bonuses on the client.
World -1 queue framing follows the existing planting_bonus_wire publisher.
"""
from itertools import count
import struct

_ACTIONS = count(1)


def _world(packet):
    # Combat codecs deliberately require a positive fight. Validate their
    # complete payload with 1, then select the independently proven world
    # queue, without broadening the combat identity contract.
    return struct.pack(">i", -1) + packet[4:]


def _entries(character):
    actor_id = character.get("id")
    states = character.get("consumable_states", ())
    if type(actor_id) is not int or not 0 < actor_id < 2**63:
        raise ValueError("Invalid owned consumable state actor")
    if not isinstance(states, (list, tuple)):
        raise ValueError("Invalid owned consumable state collection")
    entries = {}
    state_ids = set()
    uids = set()
    for state in states:
        if not isinstance(state, dict):
            raise ValueError("Invalid owned consumable state")
        uid, identity = state.get("uid"), state.get("state_id")
        level, remaining = state.get("level"), state.get("remaining_ms")
        clock = state.get("clock")
        if (
            type(uid) is not int
            or not 0 < uid < 2**63
            or uid in uids
            or type(identity) is not int
            or not 0 < identity <= 32767
            or identity in state_ids
            or type(level) is not int
            or not 0 < level <= 32767
            or type(remaining) is not int
            or not 0 <= remaining < 2**63
            or clock not in ("wall", "online", "event")
        ):
            raise ValueError("Invalid owned consumable state carrier")
        if clock == "event":
            metadata = state.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError("Invalid native event-state metadata")
            realtime = metadata.get(
                "native_realtime_duration_base",
                state.get("native_realtime_duration_base"),
            )
            if (
                remaining != 0
                or state.get("duration_ms") != 0
                or type(realtime) is not int
                or not -(2**63) <= realtime < 0
            ):
                raise ValueError("Missing native event-state realtime sentinel")
        else:
            realtime = remaining
        state_ids.add(identity)
        uids.add(uid)
        if clock == "event" or remaining:
            display = _display_effects(character, state)
            entries[uid] = (
                identity,
                level,
                realtime,
                clock,
                display[0] if display else None,
                display,
            )
    return actor_id, entries


def _display_effect(state):
    from wakfu_server.consumable_display_metadata import DISPLAY_EFFECT_IDS

    metadata = state.get("metadata", {})
    visual_ids = metadata.get("native_visual_effect_ids", ())
    effects = metadata.get("native_effects", ())
    if isinstance(effects, dict):
        effects = effects.values()
    effects = tuple(effects)

    # Preserve established current-stat displays. For newly admitted families,
    # prefer an original null marker over maximum-characteristic machinery.
    def priority(row):
        if row.get("runner") in ("eWQ", "eWR"):
            return 0
        return 1 if row.get("runner") == "eXE" else 2

    for effect in sorted(effects, key=priority):
        if (
            effect.get("id") in DISPLAY_EFFECT_IDS
            and effect.get("id") not in visual_ids
            and (
                effect.get("runner") == "eXE"
                and effect.get("generic") == 400
                or effect.get("runner") == "eXx"
                and effect.get("generic") in (2001, 2002, 2003, 2004, 2006, 2008)
                or effect.get("runner") in ("eWQ", "eWR", "eWN")
                and _display_stat(effect) is not None
                or (effect.get("runner"), effect.get("generic"))
                in (("eZI", 986), ("eWO", 192))
                and effect.get("id") in state.get("effect_ids", ())
            )
        ):
            return effect
    return None


def _display_effects(character, state):
    """Expand only ordinary, directly retained native contribution roots.

    Reactive/delayed control trees and transformation HMI nodes keep their
    separate qualification. A single display keeps its established codec/UID.
    """
    from wakfu_server.consumable_display_metadata import DISPLAY_EFFECT_IDS
    from wakfu_server.consumable_criteria import evaluate

    primary = _display_effect(state)
    metadata = state.get("metadata", {})
    definitions = metadata.get("native_effects", {})
    if not isinstance(definitions, dict):
        return () if primary is None else (primary,)
    visual_ids = metadata.get("native_visual_effect_ids", ())
    candidates = []
    has_subscription = False
    for identity in state.get("effect_ids", ()):
        effect = definitions.get(str(identity))
        if not isinstance(effect, dict):
            continue
        runner, generic = effect.get("runner"), effect.get("generic")
        native = effect.get("native_metadata", {})
        supported = (
            runner in ("eWQ", "eWR", "eWN")
            and _display_stat(effect) is not None
            or runner == "eXx"
            and generic in (2001, 2002, 2003, 2004, 2006, 2008)
        )
        subscription = (
            runner == "eYg"
            and generic == 330
            and identity in metadata.get("combat_only_effect_ids", ())
            and effect.get("subscription") is True
            and effect.get("event_execution_count") == -1
            and effect.get("event_execution_count_per_level") == 0
            and isinstance(effect.get("children"), list)
            and effect["children"]
            and all(str(child) in definitions for child in effect["children"])
            and native.get("target_masks")
            in (
                [None, None, None, None, None, [1001], None],
                [None, None, None, None, None, [1026], None],
            )
            and effect.get("timing")
            == dict(
                cxq=False, delay=[0, False, 0, False], duration=[-1, False, 0, False]
            )
            and native.get("native_target_selector", {}).get("class") == "fcE"
            and native["native_target_selector"].get("mask") in (1, 2)
        )
        if (
            identity in DISPLAY_EFFECT_IDS
            and identity not in visual_ids
            and subscription
        ):
            # The original retained eYg wrapper renders its native child tree.
            # Its PL carries the real counter; never serialize a bare heal or
            # execute subscription children while publishing the world icon.
            candidates.append(effect)
            has_subscription = True
        elif (
            identity in DISPLAY_EFFECT_IDS
            and identity not in visual_ids
            and supported
            and effect.get("subscription") is False
            and effect.get("children") == []
            and native.get("target_masks") == [None] * 7
            and native.get("native_target_selector", {}).get("class") == "fcE"
            and native["native_target_selector"].get("mask") in (1, 2)
        ):
            candidates.append(effect)
    if len(candidates) <= 1 and not has_subscription:
        return () if primary is None else (primary,)
    selected = tuple(
        effect
        for effect in candidates
        if evaluate(effect.get("criteria", ""), character)
    )
    if selected:
        return selected
    # A native condition can select a harmless marker instead (for example
    # the original alternate battleground branch). Do not display false rows.
    if primary is not None and evaluate(primary.get("criteria", ""), character):
        return (primary,)
    return ()


def _display_stat(effect):
    stat = effect.get("stat_id")
    if type(stat) is int and 0 <= stat <= 255:
        return stat
    values = effect.get("values", ())
    if (
        effect.get("runner") == "eWQ"
        and effect.get("generic") == 39
        and isinstance(values, (list, tuple))
        and len(values) >= 3
        and type(values[2]) is int
        and 0 <= values[2] <= 255
    ):
        # Original dynamic class39 reads its characteristic from parameter2.
        return values[2]
    return None


def _payload(actor_id, uid, entry):
    from wakfu_server.combat_state_carrier import state_carrier_payload
    from wakfu_server.combat_running_container import running_container_scope
    from wakfu_server.combat_native_timing_context import native_time_payload

    identity, level, remaining = entry[:3]
    # bPG.c can resolve a carrier's state, but bPG.z groups visible icons
    # through Qe.bbe/PL. Without original PL1 the retained carrier is invisible.
    # Use its actual state as the display container; do not execute children.
    with running_container_scope(
        {"container_present": True, "container_type": 1},
        (identity << 16) | level,
    ):
        return state_carrier_payload(
            uid=uid,
            base_uid=uid,
            caster_id=actor_id,
            target_id=actor_id,
            state_id=identity,
            level=level,
            native_turn_clock=-1,
            native_realtime_remaining=remaining,
            timing_payload=native_time_payload(realtime_remaining=remaining),
        )


def _child(actor_id, uid, entry, *, effect=None, child_uid=None):
    from wakfu_server.combat_stat_effects import owned_effect_payload
    from wakfu_server.combat_running_container import running_container_scope
    from wakfu_server.combat_native_timing_context import native_time_payload
    from wakfu_server.combat_effects import _integer, _varint

    effect = entry[4] if effect is None else effect
    if effect is None:
        return None
    if uid >= 2**62:
        raise ValueError("Consumable carrier UID overlaps display-child namespace")
    child_uid = uid | (1 << 62) if child_uid is None else child_uid
    identity, level, remaining = entry[:3]
    kwargs = {}
    stat = _display_stat(effect)
    if effect["runner"] in ("eWQ", "eWR"):
        kwargs.update(stat_id=stat, requested=0)
    with running_container_scope(
        {"container_present": True, "container_type": 1},
        (identity << 16) | level,
    ):
        payload = owned_effect_payload(
            uid=child_uid,
            base_uid=uid,
            generic_effect=effect["id"],
            caster_id=actor_id,
            target_id=actor_id,
            value=0,
            timing_payload=native_time_payload(realtime_remaining=remaining),
            executed=False,
            **kwargs,
        )
    if effect["runner"] == "eWN":
        # eWN has a distinct codec: previous current-value adjustment and two
        # rollback flags. Its zero display delta must not reuse stat12/25.
        additional = _integer(10, 0) + _integer(31, 0) + _integer(32, 0)
        payload += b"\x42" + _varint(len(additional)) + additional
    elif effect["runner"] in ("eZI", "eWO"):
        # Original maximum percentage/reduction runners own different rollback
        # fields. Zero value and disabled current flags retain only the icon.
        additional = _integer(35, 0)
        if effect["runner"] == "eWO":
            additional = _integer(34, 0) + additional
        payload += b"\x42" + _varint(len(additional)) + additional
    elif effect["runner"] == "eXx":
        # The registered prototype owns modifier kind/characteristic. Only
        # profession ID is serialized; eXx reads optional native parameter1.
        values = effect.get("values", ())
        profession = values[1] if len(values) > 1 else 0
        if type(profession) is not int or not 0 <= profession < 2**31:
            raise ValueError("Invalid native display-child profession")
        additional = _integer(19, profession)
        payload += b"\x42" + _varint(len(additional)) + additional
    return child_uid, effect["generic"], payload


def _apply(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_state_carrier import state_carrier_application

    return 12613, _world(
        state_carrier_application(
            1,
            allocate_action(),
            uid=uid,
            target_id=actor_id,
            running_effect_payload=_payload(actor_id, uid, entry),
        )
    )


def _children(actor_id, uid, entry):
    effects = entry[5] if len(entry) > 5 else (() if entry[4] is None else (entry[4],))
    children = []
    for index, effect in enumerate(effects):
        identity = None
        if index:
            if (
                not 0 < uid < 2**40
                or type(effect.get("id")) is not int
                or not 0 < effect["id"] < 2**20
            ):
                raise ValueError(
                    "Consumable display child exceeds native UID namespace"
                )
            identity = (1 << 60) | (uid << 20) | effect["id"]
        children.append(_child(actor_id, uid, entry, effect=effect, child_uid=identity))
    return tuple(children)


def _apply_child(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_stat_effects import owned_effect_delivery

    packets = []
    for child_uid, effect_class, payload in _children(actor_id, uid, entry):
        opcode, packet = owned_effect_delivery(
            1,
            allocate_action(),
            native_opcode=12613,
            effect_class=effect_class,
            uid=child_uid,
            target_id=actor_id,
            running_effect_payload=payload,
        )
        packets.append((opcode, _world(packet)))
    return tuple(packets)


def _remove_child(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_effect_removal import running_effect_removal

    return tuple(
        (
            13560,
            _world(
                running_effect_removal(
                    1,
                    allocate_action(),
                    effect_class=effect_class,
                    uid=child_uid,
                    target_id=actor_id,
                    running_effect_payload=payload,
                    notify_unapplication=True,
                )
            ),
        )
        for child_uid, effect_class, payload in reversed(
            _children(actor_id, uid, entry)
        )
    )


def _remove(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_effect_removal import running_effect_removal

    return 13560, _world(
        running_effect_removal(
            1,
            allocate_action(),
            effect_class=310,
            uid=uid,
            target_id=actor_id,
            running_effect_payload=_payload(actor_id, uid, entry),
        )
    )


def _flush(packets):
    return (*packets, (13420, struct.pack(">i", -1))) if packets else ()


def snapshot(character, *, allocate_action=None):
    """Rehydrate after actor creation; caller owns actor-generation fencing."""
    actor_id, entries = _entries(character)
    allocate_action = allocate_action or (lambda: next(_ACTIONS))
    packets = []
    for uid, entry in sorted(entries.items()):
        packets.append(_apply(actor_id, uid, entry, allocate_action))
        packets.extend(_apply_child(actor_id, uid, entry, allocate_action))
    from wakfu_server.consumable_visual_wire import snapshot as visual_snapshot

    packets.extend(visual_snapshot(character, allocate_action=allocate_action))
    return _flush(packets)


def delta(previous, character, *, allocate_action=None):
    """Publish removals/replacements once; ordinary clock decay is not a delta.

    The durable upsert retains a state's UID. A renewed duration therefore
    removes that carrier before installing the refreshed one with the same UID.
    Advance the caller's previous snapshot only after the flush is delivered.
    """
    old_actor, before = _entries(previous)
    actor_id, after = _entries(character)
    if old_actor != actor_id:
        raise ValueError("Consumable state delta belongs to another actor")
    allocate_action = allocate_action or (lambda: next(_ACTIONS))
    replaced = {
        uid
        for uid in before.keys() & after.keys()
        if (
            before[uid][:2] != after[uid][:2]
            or before[uid][3] != after[uid][3]
            or tuple(effect["id"] for effect in before[uid][5])
            != tuple(effect["id"] for effect in after[uid][5])
            or (after[uid][3] == "event" and before[uid][2] != after[uid][2])
            or after[uid][2] > before[uid][2]
        )
    }
    from wakfu_server.consumable_visual_wire import changes as visual_changes

    packets = list(
        visual_changes(
            previous,
            character,
            allocate_action=allocate_action,
            phase="remove",
        )
    )
    for uid in sorted((before.keys() - after.keys()) | replaced):
        packets.extend(_remove_child(actor_id, uid, before[uid], allocate_action))
        packets.append(_remove(actor_id, uid, before[uid], allocate_action))
    for uid in sorted((after.keys() - before.keys()) | replaced):
        packets.append(_apply(actor_id, uid, after[uid], allocate_action))
        packets.extend(_apply_child(actor_id, uid, after[uid], allocate_action))
    packets.extend(
        visual_changes(
            previous,
            character,
            allocate_action=allocate_action,
            phase="apply",
        )
    )
    return _flush(packets)
