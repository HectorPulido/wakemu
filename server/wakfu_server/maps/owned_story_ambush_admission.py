"""One-use server queue authority preserves an authored ambush starting pose.

Ordinary attacks still approach their target. Only a pinned owned formation
that the server queued after actual readiness receipts can retain its distance.
"""

SCHEMA = "owned-story-ambush-admission-v1"


def issue(state, selected, policy, group, attack_body):
    from wakfu_server import owned_story_controller as controller

    character = state.character
    if (
        not getattr(state, "generation", None)
        or getattr(state, "account_id", None) != character["account_id"]
        or type(attack_body) is not bytes
        or state.pending_guardian_attack != attack_body
    ):
        raise ValueError("Owned ambush queue lacks its authenticated selected session")
    state.owned_story_ambush_admission = dict(
        schema=SCHEMA,
        account_id=state.account_id,
        generation=state.generation,
        owner=character["id"],
        pose={key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")},
        profile_sha256=controller._digest(selected),
        group_id=group["group_id"],
        room_order=policy["room_order"],
        ready_steps=tuple(policy["requires"]),
        attack_body=attack_body,
    )


def consume(session):
    """Called after actual target resolution, before ordinary approach movement."""
    from wakfu_server import (
        dungeon_runtime,
        owned_story_auto_start,
        owned_story_controller as controller,
    )

    state, store = session.state, session.runtime.STORE
    ticket = getattr(state, "owned_story_ambush_admission", None)
    state.owned_story_ambush_admission = None
    character = state.character
    if (
        isinstance(ticket, dict)
        and ticket.get("schema") == SCHEMA
        and ticket.get("account_id") == state.account_id
        and ticket.get("generation") == state.generation
        and ticket.get("owner") == character["id"]
    ):
        # Movement may invalidate a genuine one-use ticket before admission.
        # Its next idle poll must observe readiness again, even after rejection.
        state.connection.owned_story_auto_frontier = None
    if not character.get("instance_id"):
        return False
    with store.connection() as db:
        if not controller.recognizes_instance(db, character["instance_id"]):
            return False
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, character["instance_id"]
        )
        selected = controller.policy(configuration)
        if selected is None or selected.get("automatic_room_start") is None:
            return False
        group = state.selected_group
        row = db.execute(
            "SELECT r.group_id,r.asset_map_id,r.room_order,g.members,g.status "
            "FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
            "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
            "WHERE r.instance_id=%s AND r.group_id=%s",
            (character["instance_id"], group["key"][2]),
        ).fetchone()
        if row is None:
            return False
        policy = owned_story_auto_start.requirements(selected, row["room_order"])
        if policy is None:
            return False
        selected, completed = controller._scope(db, store, character)
        expected_pose = {
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        }
        if (
            not isinstance(ticket, dict)
            or ticket.get("schema") != SCHEMA
            or ticket.get("account_id") != state.account_id
            or ticket.get("generation") != state.generation
            or ticket.get("owner") != character["id"]
            or ticket.get("profile_sha256") != controller._digest(selected)
            or ticket.get("pose") != expected_pose
            or ticket.get("attack_body") != state.body
            or ticket.get("room_order") != row["room_order"]
            or ticket.get("group_id") != row["group_id"]
            or ticket.get("ready_steps") != tuple(policy["requires"])
            or not set(policy["requires"]) <= completed
            or row["status"] != "available"
            or row["asset_map_id"] != selected["map_id"]
            or tuple(group["key"])
            != (selected["map_id"], character["instance_id"], row["group_id"])
            or tuple(row["members"]) != tuple(group["members"])
            or not row["members"]
        ):
            raise ValueError(
                "Owned ambush requires its issued native group and ready pose"
            )
        rooms = [
            room
            for room in configuration["topology"]["rooms"]
            if room["order"] == row["room_order"]
        ]
        if len(rooms) != 1 or tuple(
            character[key] for key in ("x", "y", "z")
        ) not in set(map(tuple, rooms[0]["cells"])):
            raise ValueError(
                "Owned ambush starting pose left its native encounter room"
            )
    return True
