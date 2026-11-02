"""Owned-session provider for the original shovel and Door wire requests.

The instance initializer defers encounter spawning for excavation_access until
its source-qualified initial choice is committed in the same transaction.
"""
from contextlib import ExitStack, contextmanager
import hashlib
from wakfu_server import dungeon_excavation, dungeon_ground_outcomes
from wakfu_server import dungeon_rotation, native_catalog


@contextmanager
def owned(store, account_id, generation, character_id, rule, *, in_fight, positions):
    if rule.get("enabled") is not True:
        raise ValueError("Excavation rule is not enabled in this source revision")
    if in_fight:
        raise ValueError("Leave combat before using the excavation mechanism")
    with ExitStack() as ownership, store.connection() as db:
        preflight = db.execute(
            "SELECT c.instance_id FROM characters c JOIN sessions s ON s.account_id=c.account_id "
            "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL "
            "AND s.generation=%s AND s.expires_at>%s",
            (character_id, account_id, generation, store.now()),
        ).fetchone()
        if preflight is None or preflight["instance_id"] <= 0:
            raise ValueError("Excavation requires an owned private dungeon session")
        instance_id = preflight["instance_id"]
        run = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        if run is None or run["status"] != "active":
            raise ValueError("Excavation dungeon progression is unavailable")
        if positions is not None:
            # Same ownership order as settlement; never block behind movement
            # holding the opposite lock order. Failure rolls everything back.
            from wakfu_server.position_buffer import PositionOwnerBusy

            try:
                ownership.enter_context(
                    positions.account_barrier(account_id, blocking=False)
                )
                positions.flush(account_id=account_id)
            except PositionOwnerBusy as error:
                raise ValueError(
                    "Dungeon position is busy; retry this ground action"
                ) from error
        from wakfu_server.inventory_owner import lock_inventory_character
        from wakfu_server.simple_item_actions import _idle

        for sql in (
            "SELECT id FROM accounts WHERE id=%s FOR UPDATE NOWAIT",
            "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE NOWAIT",
        ):
            db.execute(sql, (account_id,)).fetchone()
        db.execute(
            "SELECT id FROM characters WHERE id=%s FOR UPDATE NOWAIT", (character_id,)
        ).fetchone()
        lock_inventory_character(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        _idle(db, character_id, store.now())
        instance = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE NOWAIT",
            (instance_id,),
        ).fetchone()
        member = db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND party_id=%s AND character_id=%s AND status='active' AND session_generation=%s",
            (instance_id, run["party_id"], character_id, generation),
        ).fetchone()
        if (
            member is None
            or instance is None
            or instance["status"] != "active"
            or character.get("instance_id") != instance_id
            or instance["party_id"] != run["party_id"]
        ):
            raise ValueError("Excavation membership or owned location changed")
        from wakfu_server import dungeon_runtime

        _, config = dungeon_runtime.configuration_for_instance(db, instance_id)
        admission = config["topology"].get("excavation_access", {})
        if (
            admission.get("key") != rule["key"]
            or admission.get("rule_sha256") != dungeon_excavation.digest(rule)
            or config["route"]["key"] != rule["route_key"]
            or native_catalog.release() != rule["qualified_native_release"]
        ):
            raise ValueError("Pinned dungeon does not authorize this excavation rule")
        dungeon_rotation.validate(config)
        yield db, character, instance_id, config


def attempt(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    rule,
    in_fight=False,
    positions=None
):
    request = dungeon_ground_outcomes.decode(body)
    from wakfu_server.simple_item_actions import _criterion, _equipped
    from wakfu_server.haven_bag_furniture_knowledge import _rules
    from wakfu_server import consumable_buff_wire

    with owned(
        store,
        account_id,
        generation,
        character_id,
        rule,
        in_fight=in_fight,
        positions=positions,
    ) as (db, character, instance_id, config):
        previous = dict(character)
        item = db.execute(
            "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container AND c.character_id=i.character_id WHERE i.uid=%s AND i.character_id=%s AND c.kind IN (0,1,2,3) FOR UPDATE OF i",
            (request["source_uid"], character_id),
        ).fetchone()
        if (
            item is None
            or item.get("instance_custody_id") not in (None, instance_id)
            or _equipped(character, item["uid"])
        ):
            raise ValueError("The original reusable shovel is not available")
        native = _rules().get(item["reference"], {})
        if (
            native.get("use_action_id") != rule["action_id"]
            or native.get("use_action_class") != "bIg"
            or item["reference"] != rule["item_reference"]
        ):
            raise ValueError("Native shovel action identity changed")
        for expression in (rule["native_use_criterion"], rule["action_criterion"]):
            if not _criterion(
                store, db, account_id, character, expression, character["map_id"]
            ):
                raise ValueError("Original shovel criterion is not satisfied")
        result = dungeon_excavation.attempt_locked(
            store,
            db,
            instance_id=instance_id,
            character=character,
            item=item,
            request=request,
            rule=rule,
        )
        current = store.character(account_id, character_id, db)
        from wakfu_server import dungeon_excavation_runtime

        packets = list(consumable_buff_wire.delta(previous, current))
        packets += list(
            dungeon_excavation_runtime.pending_gate_packets(
                config,
                character_id=character_id,
                key_character_id=result.get("key_character_id"),
            )
        )
        result.update(character=current, instance_id=instance_id, packets=packets)
        return result


def choose(
    store,
    groups,
    account_id,
    generation,
    character_id,
    body,
    *,
    rule,
    in_fight=False,
    positions=None
):
    from wakfu_server import environment_doors, world_static, consumable_buff_wire

    identity, desired = environment_doors.request(body)
    if desired != 0:
        raise ValueError("Native progression gates cannot be closed by a client")
    with owned(
        store,
        account_id,
        generation,
        character_id,
        rule,
        in_fight=in_fight,
        positions=positions,
    ) as (db, character, instance_id, config):
        records = [d for d in rule["door_authority"] if d["source_id"] == identity]
        if len(records) != 1:
            raise ValueError("Only a small native door can choose the initial route")
        door = records[0]
        native = [
            d
            for d in world_static.objects(character["map_id"])
            if d["id"] == identity and d["type"] == "Door"
        ]
        if (
            len(native) != 1
            or hashlib.sha256(bytes.fromhex(native[0]["payload_hex"])).hexdigest()
            != door["payload_sha256"]
            or [character[k] for k in ("x", "y", "z")] not in door["approach_cells"]
        ):
            raise ValueError("Native first-door approach or source publication changed")
        previous = dict(character)
        result = dungeon_excavation.choose_locked(
            store,
            db,
            instance_id=instance_id,
            character_id=character_id,
            config=config,
            source_id=identity,
        )
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server import dungeon_runtime

        group = dungeon_runtime.ensure_current_room(
            db, groups, instance_id, map_geometry(character["map_id"])
        )
        _, selected = dungeon_runtime.configuration_for_instance(db, instance_id)
        from wakfu_server import dungeon_native_flow

        current = store.character(account_id, character_id, db)
        result.update(
            character=current,
            instance_id=instance_id,
            group=group,
            packets=consumable_buff_wire.delta(previous, current),
            scene_packets=dungeon_native_flow.packets(
                selected["topology"],
                map_id=character["map_id"],
                instance_id=instance_id,
                unlocked_room=1,
                completed=False,
            ),
        )
        return result
