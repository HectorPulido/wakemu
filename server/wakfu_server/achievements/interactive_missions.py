"""Explicitly configured quest interactions, settled with the owner's journal.

Bindings are reconstructed policy; importing client text alone never enables one.
"""
import struct

from . import mission_progress, storage
from .service import _owner


def binding_exists(store, map_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        return False
    object_id, action, parameter = struct.unpack(">qHH", body)
    with store.connection() as db:
        return (
            db.execute(
                "SELECT 1 FROM quest_interactive_bindings WHERE map_id=%s AND object_id=%s AND action_id=%s AND parameter=%s",
                (map_id, object_id, action, parameter),
            ).fetchone()
            is not None
        )


def _visual(character_id, object_id, script_id):
    """Execute the reviewed generic IE script only in the requesting client."""
    if type(script_id) is not int or not 0 <= script_id < 2**31:
        raise ValueError("Invalid qualified interactive script")
    if not script_id:
        return []
    from wakfu_server.exploration_artifact_actions import _script_packet

    return [_script_packet(character_id, object_id, script_id)]


def interact(store, account_id, generation, location, body, *, loaded, blocked):
    """Apply one configured world action inside the normal authenticated session."""
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server import world_static

    if blocked or not loaded or not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Mission interaction unavailable")
    object_id, action, parameter = struct.unpack(">qHH", body)
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        _guard(db, location["id"])
        row = db.execute(
            "SELECT b.*, d.data FROM quest_interactive_bindings b "
            "JOIN native_quest_metadata_definitions d "
            "ON d.revision=b.revision AND d.definition_id=b.quest_id "
            "WHERE b.map_id=%s AND b.object_id=%s AND b.action_id=%s AND b.parameter=%s",
            (location["map_id"], object_id, action, parameter),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown quest interaction action")
        rule = dict(row)
        character = store.character(account_id, location["id"], db)
        _owner(db, character)
        location = character
        if location.get("instance_id", 0) != 0:
            raise ValueError("Mission interaction requires the configured map instance")
        interaction = world_static.interaction(location, body)
        approaches = rule.get("approach_cells", [])
        if (
            not isinstance(approaches, list)
            or len(approaches) % 3
            or any(type(value) is not int for value in approaches)
        ):
            raise ValueError("Invalid native quest interaction approaches")
        native_approaches = {
            tuple(approaches[i : i + 3]) for i in range(0, len(approaches), 3)
        }
        allowed_position = (
            (location["x"], location["y"], location["z"]) in native_approaches
            if native_approaches
            else abs(location["z"] - rule["z"]) <= 1
            and abs(location["x"] - rule["x"]) + abs(location["y"] - rule["y"])
            <= rule["max_distance"]
        )
        if (
            interaction["type"] != rule["object_type"]
            or any(interaction[k] != rule[k] for k in ("x", "y", "z"))
            or not allowed_position
        ):
            raise ValueError("Mission object is unavailable or out of range")
        before = storage.load_locked(db, character["id"])
        now_ms = int(store.now().timestamp() * 1000)
        native_criterion = rule.get("native_criterion", "")
        if native_criterion:
            from wakfu_server.dungeon_criteria import evaluate
            from wakfu_server.dungeon_achievement_authority import queries_from_state

            if not evaluate(
                store,
                native_criterion,
                character=character,
                now_ms=now_ms,
                queries=queries_from_state(before, now_ms=now_ms),
            ):
                return dict(
                    applied=False,
                    handled=False,
                    packets=[],
                    character=character,
                    completed=[],
                )
        visual = _visual(character["id"], object_id, rule.get("script_id", 0))
        definition = rule["data"]["native"]
        if rule["quest_id"] not in before["running"]:
            return dict(
                applied=False,
                handled=bool(visual),
                packets=visual,
                character=character,
                completed=[],
            )
        try:
            after, intents, added, completed = mission_progress.advance_objective(
                before,
                definition,
                rule["objective_id"],
                character=character,
                store=store,
                now_ms=now_ms,
            )
        except ValueError as error:
            # A readable object remains readable when its objective is locked.
            if (
                not visual
                or str(error) != "Native quest objective prerequisite is not met"
            ):
                raise
            return dict(
                applied=False,
                handled=True,
                packets=visual,
                character=character,
                completed=[],
            )
        if not added:
            return dict(
                applied=False,
                handled=bool(visual),
                packets=visual,
                character=character,
                completed=[],
            )
        # The same native item-payment path is used by other interactive objects.
        # It locks and debits in this transaction; any later failure rolls it back.
        from wakfu_server.native_generic_rewards import _payment

        character, payment_packets, _ = _payment(
            db,
            store,
            character,
            {
                "group_cod": rule["required_item"],
                "group_coe": rule["required_quantity"],
            },
        )
        fact = {
            "kind": "configured_quest_interactive_v1",
            "map_id": rule["map_id"],
            "object_id": object_id,
            "action_id": action,
            "parameter": parameter,
            "quest_id": rule["quest_id"],
            "objective_id": rule["objective_id"],
            "revision": rule["revision"],
        }
        key = f"quest-interactive:{rule['quest_id']}:{rule['objective_id']}"
        if not storage.record_event(db, character["id"], key, fact):
            raise ValueError("Mission interaction receipt exists without progress")
        from . import mission_dependencies

        outcome = mission_dependencies.settle(
            db,
            store,
            character,
            before,
            (after, intents, added, completed),
            {rule["quest_id"]: definition},
            (),
            now_ms=now_ms,
        )
        return dict(
            applied=True,
            handled=True,
            packets=visual + payment_packets + outcome["packets"],
            completed=outcome["completed"],
            character=store.character(account_id, location["id"], db),
        )
