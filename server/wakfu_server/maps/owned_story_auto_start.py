"""Queue normal combat admission for explicitly declared owned ambush rooms."""

import struct


def declaration(selected):
    value = selected.get("automatic_room_start")
    if value is None:
        return None
    if value.get("schema") == "owned-room-auto-start-v2":
        if (
            set(value) != {"schema", "rooms"}
            or not isinstance(value["rooms"], list)
            or not value["rooms"]
        ):
            raise ValueError("Owned multi-stage ambush lacks explicit rooms")
        orders = set()
        for row in value["rooms"]:
            checked = declaration(
                dict(
                    selected,
                    automatic_room_start=dict(row, schema="owned-room-auto-start-v1"),
                )
            )
            if checked["room_order"] in orders:
                raise ValueError("Duplicate automatic owned room")
            orders.add(checked["room_order"])
        return value
    if (
        type(value) is not dict
        or set(value) != {"schema", "room_order", "requires", "evidence"}
        or value.get("schema") != "owned-room-auto-start-v1"
        or type(value.get("room_order")) is not int
        or value["room_order"] <= 0
        or not isinstance(value.get("requires"), list)
        or not value["requires"]
        or any(type(step) is not str or not step for step in value["requires"])
        or len(set(value["requires"])) != len(value["requires"])
        or not set(value["requires"]) <= {step["id"] for step in selected["steps"]}
        or not value.get("evidence")
    ):
        raise ValueError("Owned ambush lacks explicit room prerequisites")
    return value


def requirements(selected, room_order):
    value = declaration(selected)
    if value is None:
        return None
    rows = value["rooms"] if value["schema"] == "owned-room-auto-start-v2" else [value]
    return next((row for row in rows if row["room_order"] == room_order), None)


def ready_room_orders(configuration, character):
    """Use the pinned room cells to observe actual exploration readiness."""
    if character["map_id"] != configuration["topology"]["asset_map_id"]:
        return ()
    pose = tuple(character[key] for key in ("x", "y", "z"))
    return tuple(
        room["order"]
        for room in configuration["topology"]["rooms"]
        if pose in set(map(tuple, room["cells"]))
    )


def queue(session, group, *, configuration):
    """Use the actual pinned spawn; the normal attack path still admits battle."""
    from wakfu_server import owned_story_controller as controller

    state, runtime = session.state, session.runtime
    if (
        group is None
        or not state.loaded
        or state.character is None
        or state.fight is not None
        or getattr(state, "combat_session", None) is not None
        or state.spectator_session is not None
        or state.pending_guardian_attack is not None
    ):
        return False
    with runtime.STORE.connection() as db:
        selected, completed = controller._scope(db, runtime.STORE, state.character)
        policy = declaration(selected)
        if policy is None:
            return False
        multiple = policy["schema"] == "owned-room-auto-start-v2"
        row = db.execute(
            "SELECT r.group_id,r.asset_map_id,g.members,g.status,r.room_order FROM dungeon_room_spawn_receipts r "
            "JOIN combat_groups g ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
            + (
                "WHERE r.instance_id=%s AND r.group_id=%s"
                if multiple
                else "WHERE r.instance_id=%s AND r.room_order=%s"
            ),
            (
                state.character["instance_id"],
                group["group_id"] if multiple else policy["room_order"],
            ),
        ).fetchone()
        if row is None or row["status"] != "available":
            return False
        policy = requirements(
            selected, row.get("room_order", None if multiple else policy["room_order"])
        )
        if policy is None or not set(policy["requires"]) <= completed:
            return False
        if policy["room_order"] not in ready_room_orders(
            configuration, state.character
        ):
            return False
        if (
            row["group_id"] != group["group_id"]
            or row["asset_map_id"] != selected["map_id"]
            or tuple(row["members"]) != tuple(group["members"])
            or not row["members"]
        ):
            raise ValueError(
                "Owned automatic attack differs from its durable native group"
            )
        target = row["members"][0]
    state.pending_guardian_attack = struct.pack(
        ">qiihB", target["id"], target["x"], target["y"], target["z"], 0
    )
    from wakfu_server import owned_story_ambush_admission

    owned_story_ambush_admission.issue(
        state,
        selected,
        dict(policy, schema="owned-room-auto-start-v1"),
        group,
        state.pending_guardian_attack,
    )
    return True
