"""Coordinate pinned dungeon evidence and durable room groups."""
from wakfu_server import (
    dungeon_progression,
    dungeon_room_spawns,
    dungeon_runtime_config,
)


def configuration_for_instance(db, instance_id):
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if run is None:
        raise ValueError("Dungeon instance is absent")
    progress = db.execute(
        "SELECT catalog_hash,current_room,branch_key,status FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    config = dungeon_runtime_config.pinned_configuration(
        db,
        run["context_route_key"],
        run["context_policy_version"],
        expected_plan_hash=None,
    )
    from wakfu_server import dungeon_entry_paths, dungeon_gate_presentation

    config = dungeon_gate_presentation.project_configuration(config, validated_pin=True)
    config = dungeon_entry_paths.projected_for_instance(db, run, config, progress)
    if config["topology"].get("entry_path_policy") is not None:
        config = dict(
            config,
            topology=dict(
                config["topology"],
                _entry_main_completed=(
                    progress is not None and progress["status"] == "completed"
                ),
            ),
        )
    if (
        config["topology"].get("policy") == "native_shared_arena_sequential_policy"
        and progress is not None
    ):
        config = dict(
            config,
            topology=dict(config["topology"], _current_room=progress["current_room"]),
        )
    if config["topology"].get("branch_routes"):
        choice = db.execute(
            "SELECT branch_key FROM dungeon_room_runs WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()
        config = dict(
            config,
            topology=dict(
                config["topology"],
                selected_branch=None if choice is None else choice["branch_key"],
            ),
        )
    # Entry resolves its destination before initialize_run creates progression.
    # Optional ballots have no state to project until that transaction has
    # initialized the main run; keep the pinned initial configuration intact.
    if (
        config["topology"].get("optional_vote_access") is not None
        and progress is not None
    ):
        from wakfu_server.dungeon_optional_votes import project_configuration

        vote_run = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s", (instance_id,)
        ).fetchone()
        if vote_run is None:
            raise ValueError("Optional vote main run is absent")
        config = project_configuration(db, vote_run, config)
    from wakfu_server import dungeon_optional_continuations

    if dungeon_optional_continuations.scene_enabled(config["topology"]["asset_map_id"]):
        from psycopg import Error as OptionalContinuationDatabaseError

        try:
            with db.transaction():
                config = dungeon_optional_continuations.project_configuration(
                    db, run, config
                )
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OptionalContinuationDatabaseError,
        ) as error:
            # Unqualified side traversal never revokes the required main route.
            config = dict(
                config,
                topology=dict(
                    config["topology"],
                    _optional_continuation_denied_reason=type(error).__name__,
                ),
            )
    from wakfu_server import dungeon_excavation_runtime

    config = dungeon_excavation_runtime.hydrate(db, instance_id, config)
    from wakfu_server import native_scene_start

    config = native_scene_start.project_configuration(db, run, config)
    return run, config


def entry_destination(db, session, native_destination):
    """Use the pinned accessible room anchor only for the explicit local policy.

    Re-entry targets durable current progression, never resets to room one.
    Ordinary strict-native entry keeps its native destination unchanged.
    """
    _, config = configuration_for_instance(db, session["instance_id"])
    topology = config["topology"]
    if topology.get("policy") != "local_accessible_anchor_policy":
        return native_destination
    progress = db.execute(
        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
        (session["instance_id"],),
    ).fetchone()
    order = 1 if progress is None else progress["current_room"]
    rooms = [room for room in topology["rooms"] if room["order"] == order]
    if len(rooms) != 1 or topology["asset_map_id"] != native_destination["map_id"]:
        raise ValueError("Pinned accessible dungeon entry room is absent")
    room = rooms[0]
    anchor = tuple(room["anchor"])
    if anchor not in set(map(tuple, room["cells"])):
        raise ValueError("Pinned dungeon entry anchor is not accessible")
    return dict(map_id=topology["asset_map_id"], **dict(zip(("x", "y", "z"), anchor)))


def ensure_current_room(db, groups, instance_id, geometry):
    run, config = configuration_for_instance(db, instance_id)
    progress = db.execute(
        "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if progress is None:
        raise ValueError("Dungeon room progression is absent")
    topology = config["topology"]
    if progress["status"] == "completed":
        if topology.get("entry_path_policy") is not None:
            from wakfu_server import dungeon_postboss_nodes

            return dungeon_postboss_nodes.ensure_groups(db, instance_id, config, groups)
        # A finished main run has no next room to spawn. In particular, a
        # retired final-room formation cannot revoke its earned completion.
        return None
    from wakfu_server import dungeon_resource_obstacles
    import time

    if not dungeon_resource_obstacles.ensure(
        db, instance_id, config, now_ms=int(time.time() * 1000)
    ):
        return None
    from wakfu_server import native_scene_start

    if not native_scene_start.can_spawn(topology):
        return None
    from wakfu_server.dungeon_optional_rooms import require_main_room

    from wakfu_server import dungeon_excavation_runtime

    if dungeon_excavation_runtime.defer_spawn(config):
        return None
    require_main_room(topology, progress["current_room"])
    matches = [
        room for room in topology["rooms"] if room["order"] == progress["current_room"]
    ]
    if len(matches) != 1 or geometry["map_id"] != topology["asset_map_id"]:
        raise ValueError("Dungeon native room geometry differs from its configuration")
    from wakfu_server import dungeon_branches

    room = dungeon_branches.selected_room(topology, progress["current_room"])
    if room is None:
        return None
    room = native_scene_start.scene_room(topology, room)
    cells = set(map(tuple, room["cells"]))
    if not cells.issubset(set(map(tuple, geometry["cells"]))):
        raise ValueError("Frozen room cells are absent from native terrain")
    section_geometry = dict(
        geometry,
        cells=tuple(cells),
        edges=tuple(
            (a, b)
            for a, b in geometry["edges"]
            if tuple(a) in cells and tuple(b) in cells
        ),
    )
    from wakfu_server.combat_encounter_scene_policy import declared_spawn_cells

    scene_spawn_cells = declared_spawn_cells(room.get("encounter_scene", {}))
    return dungeon_room_spawns.ensure_room_group(
        db,
        groups,
        instance_id,
        asset_map_id=topology["asset_map_id"],
        anchor=room["anchor"],
        geometry=section_geometry,
        occupied=scene_spawn_cells,
        fixed_actor_placements=room.get("encounter_scene", {}).get(
            "fixed_actor_placements", ()
        ),
        select_level=dungeon_runtime_config.level_selector(
            config, room_order=progress["current_room"]
        ),
    )


def initialize_instance(db, session, *, groups, geometry, store=None):
    """Freeze the reviewed roster and register the first group before entry commits."""
    run, config = configuration_for_instance(db, session["instance_id"])
    requested = session.get("_requested_entry_path")
    if requested is not None:
        from wakfu_server import dungeon_entry_paths

        progress = db.execute(
            "SELECT branch_key FROM dungeon_room_runs WHERE instance_id=%s",
            (run["instance_id"],),
        ).fetchone()
        if progress is not None and str(progress.get("branch_key") or "").startswith(
            dungeon_entry_paths.HINT_PREFIX
        ):
            source = dungeon_runtime_config.pinned_configuration(
                db, run["context_route_key"], run["context_policy_version"]
            )
            dungeon_entry_paths.select_unfought_path(db, run, source, requested)
            run, config = configuration_for_instance(db, session["instance_id"])
    plan = dungeon_runtime_config.plan_from_configuration(config)
    dungeon_progression.initialize_run(db, run["instance_id"], run["party_id"], plan)
    if config["topology"].get("excavation_access"):
        from wakfu_server import dungeon_excavation_rules, dungeon_excavation_tools

        rule = dungeon_excavation_rules.by_key(
            config["topology"]["excavation_access"]["key"]
        )
        dungeon_excavation_tools.grant_entry(store, db, session, config, rule)
    if config["topology"].get("selected_entry_path") is not None:
        db.execute(
            "UPDATE dungeon_room_runs SET branch_key=%s WHERE instance_id=%s AND branch_key IS NULL",
            ("hint:" + config["topology"]["selected_entry_path"], run["instance_id"]),
        )
    return ensure_current_room(db, groups, run["instance_id"], geometry)


def combat_area_cells(topology, room, geometry=None):
    """Keep real room boundaries; join artificial labels on one native floor.

    Accessible-anchor rooms divide connected native terrain into logical
    encounter stages. Those labels are spawn destinations, not physical walls.
    Only their connected frozen cells may share a fight area. Native doors and
    unselected branches retain the exact selected room boundary.
    """
    from wakfu_server.combat_geometry import coordinate, prepare_geometry

    from wakfu_server import native_scene_start

    room = native_scene_start.scene_room(topology, room)
    cells = frozenset(coordinate(cell) for cell in room["cells"])
    if topology.get("policy") != "local_accessible_anchor_policy":
        return cells
    if topology.get("doors") or topology.get("branch_routes"):
        raise ValueError("Local dungeon area cannot replace native room boundaries")
    if geometry is None:
        from wakfu_server.combat_geometry import published_geometry

        geometry = published_geometry(topology["asset_map_id"])
    geometry = prepare_geometry(geometry)
    if geometry.map_id != topology["asset_map_id"]:
        raise ValueError("Dungeon combat area uses another native map")
    frozen = {
        coordinate(cell)
        for candidate in topology["rooms"]
        for cell in candidate["cells"]
    }
    native = geometry.cells
    if not frozen or not frozen <= native:
        raise ValueError("Frozen dungeon area is absent from native terrain")
    anchor = coordinate(room["anchor"])
    if anchor not in cells:
        raise ValueError("Dungeon combat area lacks its pinned room anchor")
    adjacent = {}
    for start, end in geometry.edges:
        start, end = coordinate(start), coordinate(end)
        if start in frozen and end in frozen:
            adjacent.setdefault(start, set()).add(end)
            adjacent.setdefault(end, set()).add(start)
    pending, connected = [anchor], {anchor}
    while pending:
        for destination in adjacent.get(pending.pop(), ()):
            if destination not in connected:
                connected.add(destination)
                pending.append(destination)
    if not cells <= connected:
        raise ValueError("Pinned dungeon room spans disconnected native areas")
    return frozenset(connected)


def combat_room_cells(db, group_key, player_position, member_positions):
    """Limit an encounter to its pinned native area and durable branch.

    The room spawn receipt is the authority for the selected group. Never
    cross native components or doors to satisfy random arena sizes. Logical
    accessible-anchor labels on the same native floor share their combat area.
    """
    if (
        not isinstance(group_key, tuple)
        or len(group_key) != 3
        or any(type(value) is not int for value in group_key)
    ):
        raise ValueError("Invalid dungeon combat group identity")
    map_id, instance_id, group_id = group_key
    _, config = configuration_for_instance(db, instance_id)
    progress = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if progress is not None and config["topology"].get("entry_path_policy") is not None:
        from wakfu_server import dungeon_postboss_nodes

        postboss_cells = dungeon_postboss_nodes.combat_cells(
            db, group_key, config, progress, [player_position, *member_positions]
        )
        if postboss_cells is not None:
            receipt = dungeon_postboss_nodes.group_receipt(db, group_key)
            room = next(
                room
                for room in config["topology"]["rooms"]
                if room["order"] == receipt["room_order"]
            )
            from wakfu_server.dungeon_encounter_components import require_component

            return require_component(
                config["topology"],
                room,
                postboss_cells,
                player_position,
                member_positions,
            )
    if progress is not None:
        from wakfu_server import dungeon_optional_encounters

        optional_cells = dungeon_optional_encounters.combat_cells(
            db,
            group_key,
            config,
            progress,
            [player_position, *member_positions],
        )
        if optional_cells is not None:
            return optional_cells
    if progress is None or progress["status"] != "active":
        raise ValueError("Dungeon combat requires active room progression")
    receipt = db.execute(
        "SELECT asset_map_id,group_id FROM dungeon_room_spawn_receipts "
        "WHERE instance_id=%s AND room_order=%s",
        (instance_id, progress["current_room"]),
    ).fetchone()
    topology = config["topology"]
    if (
        map_id != topology["asset_map_id"]
        or receipt is None
        or receipt["asset_map_id"] != map_id
        or receipt["group_id"] != group_id
    ):
        raise ValueError("Combat group is not the current dungeon room")
    from wakfu_server import dungeon_branches
    from wakfu_server.combat_geometry import coordinate

    room = dungeon_branches.selected_room(topology, progress["current_room"])
    if room is None:
        raise ValueError("Dungeon combat requires a selected encounter branch")
    cells = combat_area_cells(topology, room)
    participants = [coordinate(player_position)] + [
        coordinate(position) for position in member_positions
    ]
    if not cells or any(position not in cells for position in participants):
        raise ValueError("Dungeon combat participant is outside its pinned room")
    from wakfu_server.dungeon_encounter_components import require_component

    return require_component(topology, room, cells, player_position, member_positions)


def room_for_position(config, map_id, x, y, z, *, current_room=None):
    if map_id != config["topology"]["asset_map_id"]:
        raise ValueError("Dungeon position uses another asset map")
    from wakfu_server.dungeon_optional_continuations import extra_cell_rooms

    continuation_room = extra_cell_rooms(config["topology"]).get((x, y, z))
    if continuation_room is not None:
        return continuation_room
    if config["topology"].get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        cells = dungeon_shared_arena.validate(config["topology"])
        if (x, y, z) not in cells:
            raise ValueError("Position leaves reviewed shared arena")
        return dungeon_shared_arena.stage(
            config["topology"],
            current_room
            if current_room is not None
            else config["topology"].get("_current_room"),
        )
    if config["topology"].get("optional_room_policy") is not None:
        from wakfu_server.dungeon_optional_rooms import cell_rooms

        owner = cell_rooms(config["topology"]).get((x, y, z))
        if owner is not None:
            return owner
    matches = [
        room["order"]
        for room in config["topology"]["rooms"]
        if (x, y, z) in set(map(tuple, room["cells"]))
    ]
    if len(matches) == 1:
        return matches[0]
    from wakfu_server import dungeon_native_flow, generic_transports

    if config["topology"].get("policy") in (
        dungeon_native_flow.TELEPORT_POLICY,
        dungeon_native_flow.MIXED_POLICY,
    ):
        sources = [
            source
            for source in generic_transports._CATALOG
            if source["map_id"] == map_id
            and tuple(source[k] for k in ("x", "y", "z")) == (x, y, z)
        ]
        rooms = {
            dungeon_native_flow.object_room(config["topology"], source)
            for source in sources
        }
        rooms.discard(None)
        if len(rooms) == 1:
            return rooms.pop()
    raise ValueError("Dungeon position does not identify one native room")


def combat_room_scene(db, group_key):
    """Read declarations from the exact pinned room owning this admitted group."""
    map_id, instance_id, group_id = group_key
    _, config = configuration_for_instance(db, instance_id)
    progress = db.execute(
        "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if progress is None or progress["status"] != "active":
        return None
    rows = [
        room
        for room in config["topology"]["rooms"]
        if room["order"] == progress["current_room"]
    ]
    if len(rows) != 1:
        raise ValueError("Encounter scene has no current pinned room")
    from wakfu_server import native_scene_start

    room = native_scene_start.scene_room(config["topology"], rows[0])
    descriptor = room.get("encounter_scene")
    if descriptor is None:
        from wakfu_server.combat_encounter_scene_policy import compatible_room_scene

        descriptor = compatible_room_scene(config, rows[0])
    if descriptor is None:
        return None
    receipt = db.execute(
        "SELECT asset_map_id,group_id FROM dungeon_room_spawn_receipts "
        "WHERE instance_id=%s AND room_order=%s",
        (instance_id, progress["current_room"]),
    ).fetchone()
    if (
        map_id != config["topology"]["asset_map_id"]
        or receipt is None
        or receipt["asset_map_id"] != map_id
        or receipt["group_id"] != group_id
    ):
        raise ValueError("Encounter scene group differs from its pinned room")
    from wakfu_server.combat_encounter_scene_policy import prepare_scene

    return prepare_scene(
        descriptor,
        scope=dict(
            map_id=map_id,
            instance_id=instance_id,
            group_id=group_id,
            room_order=progress["current_room"],
            route_key=config["route"]["key"],
            policy_version=config["version"],
            evidence_hashes=config["evidence_hashes"],
        ),
        room_cells=room["cells"],
    )
