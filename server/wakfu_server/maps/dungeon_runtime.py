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
        "SELECT catalog_hash FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    config = dungeon_runtime_config.pinned_configuration(
        db,
        run["context_route_key"],
        run["context_policy_version"],
        expected_plan_hash=None if progress is None else progress["catalog_hash"],
    )
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
        "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if progress is None:
        raise ValueError("Dungeon room progression is absent")
    topology = config["topology"]
    matches = [
        room for room in topology["rooms"] if room["order"] == progress["current_room"]
    ]
    if len(matches) != 1 or geometry["map_id"] != topology["asset_map_id"]:
        raise ValueError("Dungeon native room geometry differs from its configuration")
    room = matches[0]
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
    return dungeon_room_spawns.ensure_room_group(
        db,
        groups,
        instance_id,
        asset_map_id=topology["asset_map_id"],
        anchor=room["anchor"],
        geometry=section_geometry,
        select_level=dungeon_runtime_config.level_selector(config),
    )


def initialize_instance(db, session, *, groups, geometry):
    """Freeze the reviewed roster and register the first group before entry commits."""
    run, config = configuration_for_instance(db, session["instance_id"])
    plan = dungeon_runtime_config.plan_from_configuration(config)
    dungeon_progression.initialize_run(db, run["instance_id"], run["party_id"], plan)
    return ensure_current_room(db, groups, run["instance_id"], geometry)


def room_for_position(config, map_id, x, y, z):
    if map_id != config["topology"]["asset_map_id"]:
        raise ValueError("Dungeon position uses another asset map")
    matches = [
        room["order"]
        for room in config["topology"]["rooms"]
        if (x, y, z) in set(map(tuple, room["cells"]))
    ]
    if len(matches) != 1:
        raise ValueError("Dungeon position does not identify one native room")
    return matches[0]
