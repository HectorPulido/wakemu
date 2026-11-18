"""Compile explicit multi-room story formations on bounded native terrain.

Original stats and spells remain the native monster catalog's responsibility.
This module only reviews species/counts and native arena cells; it never starts
an encounter, advances a room or converts an animation into a combat victory.
"""

from wakfu_server.combat_geometry import reachable

SCHEMA = "owned-story-encounters-v1"


def can_spawn(db, groups, instance_id, configuration, room):
    """A later formation waits for real owned door/puzzle/scene receipts."""
    from wakfu_server import owned_story_controller

    selected = owned_story_controller.policy(configuration)
    if selected is None:
        return True
    required = room.get("requires")
    if (
        not isinstance(required, list)
        or any(not isinstance(step, str) or not step for step in required)
        or len(set(required)) != len(required)
        or not set(required) <= {step["id"] for step in selected["steps"]}
    ):
        raise ValueError("Owned story room has no reviewed spawn prerequisites")
    members = db.execute(
        "SELECT c.id,c.account_id FROM dungeon_instance_members m "
        "JOIN characters c ON c.id=m.character_id "
        "WHERE m.instance_id=%s AND m.status='active' ORDER BY c.id",
        (instance_id,),
    ).fetchall()
    if len(members) != 1:
        raise ValueError("Owned story spawn requires its one durable owner")
    member = members[0]
    character = groups.store.character(member["account_id"], member["id"], db)
    actual, completed = owned_story_controller._scope(db, groups.store, character)
    if owned_story_controller._digest(actual) != owned_story_controller._digest(
        selected
    ):
        raise ValueError("Owned story spawn differs from its pinned profile")
    return set(required) <= completed


def compile_rooms(document, *, geometry, exploration, monster):
    if (
        type(document) is not dict
        or document.get("schema") != SCHEMA
        or not document.get("id")
        or not document.get("provenance")
        or document.get("map_id") != geometry.map_id
        or exploration.get("map_id") != geometry.map_id
        or not exploration.get("topology_sha256")
        or not exploration.get("client_sha256")
        or not isinstance(document.get("rooms"), list)
        or not document["rooms"]
        or type(document.get("sequential_arenas", False)) is not bool
    ):
        raise ValueError("Story encounters lack reviewed native terrain")
    walking = {tuple(point) for point in exploration["cells"]}
    compiled, topology, seen = [], [], set()
    for expected_order, room in enumerate(document["rooms"], 1):
        if (
            type(room) is not dict
            or type(room.get("order")) is not int
            or room["order"] != expected_order
            or type(room.get("physical_room")) is not int
            or room["physical_room"] <= 0
            or not isinstance(room.get("requires"), list)
            or any(not isinstance(step, str) or not step for step in room["requires"])
            or not isinstance(room.get("bounds"), list)
            or len(room["bounds"]) != 4
            or any(type(value) is not int for value in room["bounds"])
            or type(room.get("z")) is not int
            or not isinstance(room.get("arena_seed"), list)
            or len(room["arena_seed"]) != 3
            or any(type(value) is not int for value in room["arena_seed"])
        ):
            raise ValueError("Story room requires explicit ordered arena bounds")
        left, bottom, right, top = room["bounds"]
        if left > right or bottom > top:
            raise ValueError("Story room has reversed arena bounds")
        altitudes = room.get("altitudes", [room["z"]])
        if (
            not isinstance(altitudes, list)
            or not altitudes
            or any(type(value) is not int for value in altitudes)
            or len(set(altitudes)) != len(altitudes)
            or room["z"] not in altitudes
        ):
            raise ValueError("Story room lacks explicit native altitude layers")
        available = {
            point
            for point in geometry.cells
            if left <= point[0] <= right
            and bottom <= point[1] <= top
            and point[2] in altitudes
        }
        seed = tuple(room["arena_seed"])
        if seed not in available:
            raise ValueError("Story arena anchor is outside native combat terrain")
        cells = reachable(seed, available, geometry.outgoing) & reachable(
            seed, available, geometry.incoming
        )
        if not cells <= walking or (
            cells & seen
            and (not document.get("sequential_arenas", False) or not room["requires"])
        ):
            raise ValueError(
                "Story arenas overlap without sequential authority or leave native walking terrain"
            )
        native_roster, references = [], set()
        if not isinstance(room.get("monsters"), list) or not room["monsters"]:
            raise ValueError("Story room has no explicit original formation")
        for entry in room["monsters"]:
            if (
                type(entry) is not dict
                or set(entry)
                not in ({"reference", "count"}, {"reference", "count", "role"})
                or entry.get("role", "monster") not in ("monster", "boss")
                or type(entry["reference"]) is not int
                or entry["reference"] <= 0
                or entry["reference"] in references
                or type(entry["count"]) is not int
                or not 1 <= entry["count"] <= 8
            ):
                raise ValueError("Story species/count declaration is invalid")
            native = monster(entry["reference"])
            box_goal = room.get("encounter_scene", {}).get("box_goals")
            passive_box = (
                isinstance(box_goal, dict)
                and box_goal.get("box_reference") == entry["reference"]
                and len(box_goal.get("goals", ())) == entry["count"]
            )
            from wakfu_server.combat_scene_ball_goals import declared_actor

            passive_ball = declared_actor(
                room.get("encounter_scene"), entry["reference"], entry["count"], native
            )
            if (
                native["ref"] != entry["reference"]
                or (
                    not native["native_abilities"]
                    and not passive_box
                    and not passive_ball
                )
                or not 0 < native["min_level"] <= native["max_level"]
            ):
                raise ValueError("Story actor lacks its native combat definition")
            native_roster.append(
                dict(
                    name=native["name"],
                    ref_id=native["ref"],
                    count=entry["count"],
                    role=entry.get("role", "monster"),
                    native_min_level=native["min_level"],
                    native_max_level=native["max_level"],
                    guide_min_level=None,
                    guide_max_level=None,
                )
            )
            references.add(entry["reference"])
        if len(cells) < sum(row["count"] for row in native_roster) + 8:
            raise ValueError("Story arena has no safe ordinary placement capacity")
        compiled.append(
            dict(order=expected_order, monsters=native_roster, diagnostics=[])
        )
        topology.append(
            dict(
                order=expected_order,
                requires=list(room["requires"]),
                anchor=list(seed),
                cells=[list(point) for point in sorted(cells)],
                encounter_region=dict(
                    schema_version=1,
                    cells=[list(point) for point in sorted(cells)],
                    anchor=list(seed),
                    provenance=document["provenance"],
                ),
            )
        )
        if room.get("encounter_scene") is not None:
            from copy import deepcopy
            from wakfu_server.combat_encounter_scene_policy import prepare_scene

            scene = room["encounter_scene"]
            prepare_scene(
                scene,
                room_cells=cells,
                scope=dict(
                    map_id=geometry.map_id,
                    instance_id=1,
                    group_id=1,
                    room_order=expected_order,
                    policy_version=1,
                    route_key="offline-owned-story-validation",
                    evidence_hashes={},
                ),
            )
            topology[-1]["encounter_scene"] = deepcopy(scene)
        seen.update(cells)
    return compiled, topology
