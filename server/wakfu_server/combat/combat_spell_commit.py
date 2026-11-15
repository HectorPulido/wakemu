"""Prepare every cast presentation packet before committing its preview.

Call on the owning session thread. No network sends occur here; caller sends
returned packets and handles death/results after accepting the new fight.
"""

import struct
import time
from .combat_spell_transaction import SpellTransaction
from .combat_wire import actor_state
from .combat_geometry_snapshot import source_snapshot


def _movement_lesson_presentation(fight, opcode, payload, *, source_fight=None):
    """Accept only the movement lesson's server-produced marker and notice."""
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if not isinstance(contract, dict) or not isinstance(payload, bytes):
        return False
    previous = getattr(
        source_fight if source_fight is not None else fight,
        "rii_movement_lesson_contract",
        None,
    )
    if not isinstance(previous, dict) or previous.get("owner") != contract.get("owner"):
        return False
    if opcode == 12226 and len(payload) == struct.calcsize(">iiihqBB"):
        fight_id, x, y, z, owner, icon, added = struct.unpack(">iiihqBB", payload)
        marker = contract.get("marker") if added == 1 else previous.get("marker")
        return (
            fight_id == fight.id
            and owner == contract.get("owner")
            and isinstance(marker, (list, tuple))
            and tuple(marker) == (x, y, z)
            and (x, y, z) in fight.walkable
            and icon == 0
            and added in (0, 1)
        )
    if opcode == 349:
        from wakfu_server.ecology_feedback import information

        marker = contract.get("marker")
        if isinstance(marker, list) and len(marker) == 3:
            return (opcode, payload) == information(
                f"Movement lesson: move the sack to cell ({marker[0]}, {marker[1]})."
            )
    return False


def _states_lesson_presentation(fight, opcode, payload, *, source_fight):
    contract = getattr(fight, "rii_states_lesson_contract", None)
    previous = getattr(source_fight, "rii_states_lesson_contract", None)
    if not isinstance(contract, dict) or not isinstance(previous, dict):
        return False
    hits = contract.get("hits")
    if (
        type(hits) is not int
        or hits not in (1, 2, 3)
        or type(previous.get("hits")) is not int
        or hits != previous["hits"] + 1
        or contract.get("owner") != previous.get("owner")
    ):
        return False
    if opcode == 12226 and isinstance(payload, bytes) and len(payload) == 24:
        fight_id, x, y, z, owner, icon, added = struct.unpack(">iiihqBB", payload)
        if added == 0 and hits in (1, 2):
            marker = previous.get("green" if hits == 1 else "red")
            expected_icon = hits - 1
        elif added == 1 and hits == 1:
            marker = contract.get("red")
            expected_icon = hits
        else:
            return False
        return (
            fight_id == fight.id
            and owner == contract["owner"]
            and isinstance(marker, (list, tuple))
            and tuple(marker) == (x, y, z)
            and (x, y, z) in fight.walkable
            and icon == expected_icon
        )
    if opcode == 349:
        from wakfu_server.ecology_feedback import information
        from wakfu_server.achievements.rii_states_contract import MESSAGES

        return (opcode, payload) == information(MESSAGES[hits])
    return False


def _distance_lesson_presentation(fight, opcode, payload, *, source_fight):
    """Accept only the distance lesson's own guide notice inside a cast."""
    contract = getattr(fight, "rii_distance_lesson_contract", None)
    previous = getattr(source_fight, "rii_distance_lesson_contract", None)
    if (
        opcode != 349
        or not isinstance(contract, dict)
        or not isinstance(previous, dict)
    ):
        return False
    hits = contract.get("hits")
    # The distance lesson qualifies inside the live fight, so preview and live
    # contracts are the same object here; the count has already advanced.
    if (
        type(hits) is not int
        or type(previous.get("hits")) is not int
        or hits not in (previous["hits"], previous["hits"] + 1)
        or contract.get("owner") != previous.get("owner")
        or contract.get("target") != previous.get("target")
    ):
        return False
    from wakfu_server.ecology_feedback import information
    from wakfu_server.achievements.rii_distance_contract import hint

    message = hint(hits)
    return message is not None and (opcode, payload) == information(message)


def commit_spell_transaction(
    runtime, transaction, *, stats_serializer, diagnostic=None
):
    def stage(name, started, **details):
        if diagnostic is not None:
            diagnostic(
                phase=name,
                elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                fight_id=runtime.fight.id,
                action_id=transaction.action_id,
                **details,
            )

    if not isinstance(transaction, SpellTransaction) or not callable(stats_serializer):
        raise ValueError("Missing prepared spell transaction or serializer")
    if runtime.awaiting_ack is not None or runtime.pending:
        raise ValueError("Previous combat action is not synchronized")
    if transaction.action_id != runtime.action_id + 1:
        raise ValueError("Prepared spell action sequence is stale")
    from .combat_owned_native_spell_entry import owns_entry_commit

    owned_entry = owns_entry_commit(runtime, transaction, stats_serializer)
    started = time.monotonic()
    if transaction.fight.id != runtime.fight.id or (
        not owned_entry and source_snapshot(runtime.fight) != transaction.source_state
    ):
        raise ValueError("Combat changed after preparing the spell")
    stage("validate_source", started)
    expected = struct.pack(">iii", runtime.fight.id, transaction.action_id, -1)
    for opcode, payload in transaction.packets:
        if opcode == 13420:
            valid = isinstance(payload, bytes) and payload == struct.pack(
                ">i", runtime.fight.id
            )
        elif _movement_lesson_presentation(
            transaction.fight, opcode, payload, source_fight=runtime.fight
        ):
            valid = True
        elif _states_lesson_presentation(
            transaction.fight, opcode, payload, source_fight=runtime.fight
        ):
            valid = True
        elif _distance_lesson_presentation(
            transaction.fight, opcode, payload, source_fight=runtime.fight
        ):
            valid = True
        else:
            valid = isinstance(payload, bytes) and payload[:12] == expected
        if not valid:
            raise ValueError("Effect packet belongs to another combat action")
    packets = list(transaction.packets)
    packets.append(runtime._flush())
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(transaction.fight)
    for actor in transaction.fight.actors.values():
        # Native final-death delivery still needs the client's registered QK
        # byte. Publishing an already retired obstacle=-1 first prevents
        # QI.g(QK) from clearing its former slot and occupied cells.
        if actor.id in hidden:
            continue
        started = time.monotonic()
        stats = stats_serializer(actor, transaction.fight)
        stage("serialize_actor", started, actor_id=actor.id)
        packets.append(
            (12873, actor_state(12873, transaction.fight.id, actor.id, stats))
        )
    packets.append(runtime._flush())
    # Serialization callbacks cannot invalidate the original source silently.
    started = time.monotonic()
    if not owned_entry and source_snapshot(runtime.fight) != transaction.source_state:
        raise ValueError("Combat changed while serializing the spell")
    stage("revalidate_source", started)
    from .combat_owned_spell_delivery import validated_spell_delivery

    with validated_spell_delivery(runtime, transaction):
        return runtime.prepare_fight_delivery(
            packets,
            transaction.fight,
            action_id=transaction.action_id,
            operation="commit_spell_transaction",
        )
