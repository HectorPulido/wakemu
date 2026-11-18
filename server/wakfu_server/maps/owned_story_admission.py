"""Qualify optional native stage presentations and allies from actual owned groups."""

from wakfu_server import owned_story_controller as controller


def scene_actor_rows(db, store, character):
    """Resolve authentic native models with no combat or dialogue registration."""
    selected, completed = controller._scope(db, store, character)
    return _project_scene_actor_rows(character, selected, completed)


def _project_scene_actor_rows(character, selected, completed):
    from wakfu_server import owned_story_mechanics, owned_story_npcs, monsters
    from wakfu_server.combat_geometry import published_geometry

    native = owned_story_mechanics.sources(selected)
    rows, slots, roles = [], set(), set()
    for actor in native.get("scene_actors", ()):
        if (
            set(actor)
            != {
                "slot",
                "role",
                "reference",
                "level",
                "position",
                "direction",
                "requires",
                "until",
                "native_prototype_sha256",
            }
            or type(actor["slot"]) is not int
            or not 0 < actor["slot"] < 1024
            or actor["slot"] in slots
            or actor["role"] in roles
            or not isinstance(actor["role"], str)
            or not actor["role"]
            or not isinstance(actor["requires"], list)
            or not isinstance(actor["until"], list)
            or not set(actor["requires"] + actor["until"])
            <= {step["id"] for step in selected["steps"]}
        ):
            raise ValueError("Native scene actor lacks its qualified lifecycle")
        slots.add(actor["slot"])
        roles.add(actor["role"])
        prototype = monsters.reference(actor["reference"])
        if (
            controller._digest(prototype) != actor["native_prototype_sha256"]
            or actor["level"] != prototype["min_level"]
            or tuple(actor["position"])
            not in published_geometry(selected["map_id"]).cells
        ):
            raise ValueError(
                "Render-only model differs from its actual native prototype"
            )
        if not set(actor["requires"]) <= completed or set(actor["until"]) & completed:
            continue
        rows.append(
            dict(
                actor_id=owned_story_npcs.actor_id(
                    character["instance_id"], actor["slot"]
                ),
                reference_id=actor["reference"],
                map_id=selected["map_id"],
                instance_id=character["instance_id"],
                owner_id=character["id"],
                **dict(zip(("x", "y", "z"), actor["position"])),
                direction=actor["direction"],
                level=actor["level"],
                visual_id=prototype["sprite_id"],
                name_es=prototype["name"],
                source_sha256=actor["native_prototype_sha256"],
                native_action_ids=[],
                role=actor["role"],
            )
        )
    return rows


def scene_actor_packets(db, store, character):
    selected, completed = controller._scope(db, store, character)
    return project_scene_actor_packets(character, selected, completed)


def project_scene_actor_packets(character, selected, completed):
    """Render from an already authorized owner snapshot without position checks."""
    from wakfu_server import owned_story_actor_operations

    return [
        owned_story_actor_operations.spawn(row, character=character, selected=selected)
        for row in _project_scene_actor_rows(character, selected, completed)
    ]


def prepare(store, character, members):
    return _prepare(store, character, members, kind="room_admission")


def observe_room_available(store, character):
    """Observe an actual spawned group without starting combat or adding allies."""
    return _prepare(store, character, None, kind="room_available")["packets"]


def _prepare(store, character, members, *, kind):
    from wakfu_server import dungeon_runtime, owned_story_mechanics

    members = None if members is None else tuple(members)
    with store.connection() as db:
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, character["instance_id"]
        )
        selected = controller.policy(configuration)
        if selected is None:
            return dict(packets=[], mission_allies=None)
        if kind == "room_admission" and configuration["topology"].get(
            "owned_quest_pools"
        ):
            from wakfu_server import owned_quest_pools

            if owned_quest_pools.member_scope(db, character, members, configuration):
                return dict(packets=[], mission_allies=None)
        if (
            kind == "room_admission"
            and selected.get("automatic_room_start") is not None
        ):
            from wakfu_server import owned_story_auto_start

            current = db.execute(
                "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
                (character["instance_id"],),
            ).fetchone()
            if current is None or current["status"] != "active":
                raise ValueError("Owned ambush lacks its durable active room")
            automatic = owned_story_auto_start.requirements(
                selected, current["current_room"]
            )
            selected, completed = controller._scope(db, store, character)
            if automatic is not None and not set(automatic["requires"]) <= completed:
                raise ValueError(
                    "Owned ambush is waiting for its authentic story prerequisites"
                )
        native = owned_story_mechanics.sources(selected)
        if not (kind == "room_admission" and native.get("combat_helpers")) and not any(
            step["kind"] == kind for step in selected["steps"]
        ):
            return dict(packets=[], mission_allies=None)
        selected, completed = controller._scope(db, store, character)
        from wakfu_server import owned_story_refresh

        if owned_story_refresh.pending(db, store, character) is not None:
            if kind == "room_available":
                return dict(packets=[], mission_allies=None)
            raise ValueError("The owned stage is restoring its native map context")
        progress = db.execute(
            "SELECT current_room,status FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (character["instance_id"],),
        ).fetchone()
        if progress is None or progress["status"] != "active":
            raise ValueError("Owned stage admission lacks active room progression")
        room = progress["current_room"]
        original = db.execute(
            "SELECT g.members,g.status,r.asset_map_id FROM dungeon_room_spawn_receipts r "
            "JOIN combat_groups g ON g.instance_id=r.instance_id "
            "AND g.map_id=r.asset_map_id AND g.group_id=r.group_id "
            "WHERE r.instance_id=%s AND r.room_order=%s FOR UPDATE OF g",
            (character["instance_id"], room),
        ).fetchone()

        def identity(member):
            if (
                type(member.get("id")) is not int
                or member["id"] >= 0
                or type(member.get("ref")) is not int
                or member["ref"] <= 0
                or member.get("map_id") != selected["map_id"]
                or member.get("instance_id") != character["instance_id"]
                or any(type(member.get(key)) is not int for key in ("x", "y", "z"))
            ):
                raise ValueError(
                    "Owned stage actor escaped its original physical group"
                )
            return tuple(member[key] for key in ("id", "ref", "x", "y", "z"))

        if members is None:
            members = () if original is None else tuple(original["members"])
        actual = tuple(sorted(identity(member) for member in members))
        if (
            original is None
            or original["asset_map_id"] != selected["map_id"]
            or original["status"] not in ("available", "fighting")
            or actual
            != tuple(sorted(identity(member) for member in original["members"]))
            or len({row[0] for row in actual}) != len(actual)
        ):
            raise ValueError(
                "Owned stage admission differs from its durable live group"
            )
        helper_policy = native.get("combat_helpers", {}).get(str(room))
        admission = None
        if kind == "room_admission" and helper_policy is not None:
            from wakfu_server.combat_mission_allies import admit

            admission = admit(character, members, policy=helper_policy, room=room)
        required_steps = [
            step
            for step in selected["steps"]
            if step["kind"] == kind and step["reference"] == room
        ]
        if any(not set(step["requires"]) <= completed for step in required_steps):
            if kind == "room_available":
                return dict(packets=[], mission_allies=None)
            raise ValueError(
                "Owned stage is waiting for its authentic story prerequisites"
            )
        result = controller._settle(
            db,
            store,
            character,
            selected,
            completed,
            kind=kind,
            reference=room,
            evidence=dict(
                room_order=room, original_actor_ids=[row[0] for row in actual]
            ),
            apply_effects=owned_story_mechanics.executor(selected),
        )
    return dict(packets=result["packets"], mission_allies=admission)
