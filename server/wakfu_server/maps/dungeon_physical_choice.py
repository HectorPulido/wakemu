"""Commit a source-bound walking choice without relocating its participants.

Only an explicit shared-prefix branch policy opts in. The prefix, source plan
hash and its admitted groups remain immutable; ordinary movement is unchanged.
"""
from contextlib import ExitStack


def frozen_rooms(configuration):
    from wakfu_server.dungeon_entry_paths import frozen_rooms as freeze

    return freeze(configuration)


def commit_movement(
    store,
    positions,
    groups,
    account_id,
    generation,
    character,
    movement,
    authoritative_position,
    *,
    geometry,
    preview_configuration=None,
    unlocked_room=None,
):
    """Return None for non-selector movement, otherwise its committed position.

    The caller validates its ordinary Movement state before this boundary and
    sends path/scene packets only after this function returns. No packet, actor
    relocation or partial path is published while a choice is uncommitted.
    """
    from psycopg.errors import LockNotAvailable
    from psycopg_pool import PoolTimeout
    from wakfu_server.position_buffer import PositionOwnerBusy
    from wakfu_server.position_staged_move import stage_move
    from wakfu_server import dungeon_branches, dungeon_runtime, dungeon_native_flow
    from wakfu_server.dungeon_entry_paths import (
        prelock_combat_owner_nowait,
        lock_members_nowait,
    )

    target = dict(
        movement["end_position"], direction=movement["steps"][-1]["direction"]
    )
    selector = None
    if preview_configuration is not None:
        if (
            preview_configuration["topology"].get("branch_selection_checkpoint") is None
            or preview_configuration["topology"].get("selected_branch") is not None
        ):
            return None
        selector = dungeon_branches.physical_selector(
            preview_configuration["topology"], movement, unlocked_room=unlocked_room
        )
        if selector is None:
            return None  # Unrelated ordinary walking never borrows another connection.
    try:
        # Read-only classification must release its connection before the
        # previous movement checkpoint borrows a slot, including pool size one.
        if preview_configuration is None:
            with store.connection(timeout=0.25) as db:
                _, preview = dungeon_runtime.configuration_for_instance(
                    db, character["instance_id"]
                )
                if (
                    preview["topology"].get("branch_selection_checkpoint") is None
                    or preview["topology"].get("selected_branch") is not None
                ):
                    return None
                frontier = db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (character["instance_id"],),
                ).fetchone()
                if frontier is None:
                    raise ValueError(
                        "Physical native choice has no dungeon progression"
                    )
                selector = dungeon_branches.physical_selector(
                    preview["topology"],
                    movement,
                    unlocked_room=frontier["current_room"],
                )
                if selector is None:
                    return None
        # All classification/catalog work and checkpoint pool waits precede
        # owner/run locks. A raced move is rejected by the clean stage guard.
        prepared_geometry = geometry() if callable(geometry) else geometry
        positions.flush(account_id=account_id)
        with ExitStack() as transaction:
            db = transaction.enter_context(store.connection(timeout=0.25))
            with stage_move(
                positions,
                account_id,
                generation,
                character["id"],
                authoritative_position,
                target,
            ) as staged:
                progress = db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE NOWAIT",
                    (character["instance_id"],),
                ).fetchone()
                instance = db.execute(
                    "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE NOWAIT",
                    (character["instance_id"],),
                ).fetchone()
                if (
                    progress is None
                    or instance is None
                    or instance["status"] != "active"
                    or progress["party_id"] != instance["party_id"]
                ):
                    raise ValueError("Physical native choice lost its active instance")
                lock_members_nowait(db, [character["id"]])
                prelock_combat_owner_nowait(
                    db, account_id, generation, character["id"], store.now()
                )
                from wakfu_server.simple_item_actions import _idle

                _idle(db, character["id"], store.now())
                owned = db.execute(
                    "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s",
                    (character["id"], account_id),
                ).fetchone()
                membership = db.execute(
                    "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND party_id=%s "
                    "AND character_id=%s AND status='active'",
                    (instance["instance_id"], instance["party_id"], character["id"]),
                ).fetchone()
                if (
                    owned is None
                    or membership is None
                    or owned["map_id"] != staged.current["map_id"]
                    or owned["instance_id"] != instance["instance_id"]
                    or staged.current["instance_id"] != instance["instance_id"]
                ):
                    raise ValueError(
                        "Physical native choice actor is not an owned member"
                    )
                pending = db.execute(
                    "SELECT 1 FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending' LIMIT 1",
                    (character["id"],),
                ).fetchone()
                if pending is not None:
                    raise ValueError(
                        "Physical native choice awaits its committed transition"
                    )
                _, config = dungeon_runtime.configuration_for_instance(
                    db, instance["instance_id"]
                )
                topology = config["topology"]
                if (
                    owned["map_id"] != topology["asset_map_id"]
                    or character["map_id"] != owned["map_id"]
                ):
                    raise ValueError("Physical native choice uses another source map")
                selected = dungeon_branches.physical_selector(
                    topology, movement, unlocked_room=progress["current_room"]
                )
                if selected != selector:
                    raise ValueError(
                        "Physical native selector changed during admission"
                    )
                dungeon_native_flow.validate_movement(
                    topology,
                    movement,
                    unlocked_room=progress["current_room"],
                    completed=progress["status"] == "completed",
                )
                if progress.get("branch_key") is not None:
                    # Another member already committed this path. Revalidated
                    # ordinary walking/backtracking needs no second choice or
                    # group hydration, including after the final encounter.
                    return None
                branch = dungeon_branches.select(
                    db,
                    instance["instance_id"],
                    topology,
                    selected,
                    source_kind="physical",
                    expected_catalog_hash=config["compiled_plan"]["document_sha256"],
                    expected_rooms=frozen_rooms(config),
                )
                _, chosen = dungeon_runtime.configuration_for_instance(
                    db, instance["instance_id"]
                )
                if chosen["topology"].get("selected_branch") != branch:
                    raise ValueError(
                        "Physical native choice did not retain its exact source path"
                    )
                dungeon_native_flow.validate_movement(
                    chosen["topology"],
                    movement,
                    unlocked_room=progress["current_room"],
                    completed=progress["status"] == "completed",
                )
                population = db.execute(
                    "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
                    (
                        f"monster-population:{owned['map_id']}:{instance['instance_id']}",
                    ),
                ).fetchone()
                if population is None or population["locked"] is not True:
                    raise ValueError(
                        "Physical native branch population is busy; retry movement"
                    )
                receipt = dungeon_runtime.ensure_current_room(
                    db, groups, instance["instance_id"], prepared_geometry
                )
                if receipt is None:
                    raise ValueError(
                        "Physical native branch lacks its selected encounter group"
                    )
                scene_packets = tuple(
                    dungeon_native_flow.packets(
                        chosen["topology"],
                        map_id=owned["map_id"],
                        instance_id=instance["instance_id"],
                        unlocked_room=progress["current_room"],
                        completed=progress["status"] == "completed",
                    )
                )
                staged.persist(db)
                # Commit SQL choice, new group and durable endpoint together,
                # while the original registry entry still names the shared area.
                current = staged.commit(transaction.close)
                return dict(
                    character=current,
                    branch_key=branch,
                    group_receipt=receipt,
                    instance_id=instance["instance_id"],
                    scene_packets=scene_packets,
                )
    except (LockNotAvailable, PoolTimeout) as error:
        # Translation occurs after the database transaction has unwound. Neither
        # choice nor buffered endpoint was published on the rejected movement.
        raise PositionOwnerBusy(
            "Physical native branch is busy; retry movement"
        ) from error
