"""Read-only ownership evidence for the reconstructed Astrub cat story.

The story producer owns presentation receipts. Combat admission uses the
existing durable dungeon room group and exact native books; a quest marker,
map number or matching creature reference alone never admits an ally.
"""

MAP_ID = 312
QUEST_ID = 5568
ROUTE_KEY = "legacy-map-312-18736-713"
DEFINITION_ID = 1000312
START_SCHEMA = "wakemu.astrub-cat-story.v1"


def start_key(instance_id):
    return f"astrub-cat-story:{instance_id}:start"


def callback_key(instance_id, event_id):
    return f"astrub-cat-story:{instance_id}:callback:{event_id}"


def _state(db, character_id):
    row = db.execute(
        "SELECT state FROM character_achievement_progress WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    return None if row is None else row["state"]


def _receipt(db, character_id, key):
    row = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, key),
    ).fetchone()
    return None if row is None else row["payload"]


def _references(room):
    monsters = room.get("monsters")
    if not isinstance(monsters, list):
        raise ValueError("Astrub story room has no frozen native roster")
    refs = []
    for member in monsters:
        reference, count = member.get("ref_id"), member.get("count")
        if (
            type(reference) is not int
            or reference <= 0
            or type(count) is not int
            or not 1 <= count <= 127
        ):
            raise ValueError("Astrub story room has malformed native roster")
        refs.extend([reference] * count)
    return tuple(sorted(refs))


def context(db, character, *, allow_finished=False):
    """Read the owned story scope without acquiring gameplay locks.

    Nonstory visits return None. A character participating in this quest must
    retain the exact owned dungeon, pinned configuration and active membership.
    The enclosing travel or combat transaction owns any required row locks.
    """
    if (
        not isinstance(character, dict)
        or character.get("map_id") != MAP_ID
        or type(character.get("instance_id")) is not int
        or character["instance_id"] <= 0
    ):
        return None
    if any(
        type(character.get(key)) is not int or character[key] <= 0
        for key in ("id", "account_id")
    ):
        raise ValueError("Astrub story scope has no owned character")
    state = _state(db, character["id"])
    if not isinstance(state, dict):
        return None
    running, completed, objectives = (
        set(state.get(key, ())) for key in ("running", "completed", "objectives")
    )
    if (
        (QUEST_ID not in running and not (allow_finished and QUEST_ID in completed))
        or 11510 not in objectives
        or (11515 in objectives and not allow_finished)
    ):
        return None
    instance_id = character["instance_id"]
    receipt = _receipt(db, character["id"], start_key(instance_id))
    if (QUEST_ID not in running or 11515 in objectives) and receipt is None:
        # Finished-story polling may resume an already introduced instance's
        # ending. A completed quest alone does not enroll an ordinary revisit
        # into that story or impose its frozen presentation roster on the run.
        return None
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if run is None:
        raise ValueError("Astrub story has no owned dungeon instance")
    if run.get("context_route_key") != ROUTE_KEY:
        return None
    if (
        run.get("instance_id") != instance_id
        or run.get("status")
        not in (("active", "completed") if allow_finished else ("active",))
        or type(run.get("context_policy_version")) is not int
        or run["context_policy_version"] < 4
        or (run.get("template_id"), run.get("definition_id"), run.get("start_map_id"))
        != (DEFINITION_ID, DEFINITION_ID, MAP_ID)
        or (
            run.get("entry_map_id"),
            run.get("entry_object_id"),
            run.get("entry_destination_id"),
        )
        != (527, 18736, 713)
    ):
        raise ValueError("Astrub story dungeon differs from its pinned route")
    member = db.execute(
        "SELECT m.* FROM dungeon_instance_members m JOIN characters c "
        "ON c.id=m.character_id WHERE m.instance_id=%s AND m.character_id=%s "
        "AND c.account_id=%s",
        (instance_id, character["id"], character["account_id"]),
    ).fetchone()
    if (
        member is None
        or member.get("status") != "active"
        or member.get("party_id") != run.get("party_id")
        or member.get("instance_id") != instance_id
        or member.get("character_id") != character["id"]
    ):
        raise ValueError("Astrub story character is not an active owned party member")
    progress = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if (
        progress is None
        or progress.get("instance_id") != instance_id
        or progress.get("party_id") != run.get("party_id")
        or progress.get("status")
        not in (("active", "completed") if allow_finished else ("active",))
        or type(progress.get("current_room")) is not int
        or progress["current_room"] not in (1, 2, 3)
    ):
        raise ValueError("Astrub story lost its owned room progression")
    configuration = db.execute(
        "SELECT configuration FROM dungeon_runtime_configurations "
        "WHERE route_key=%s AND policy_version=%s",
        (ROUTE_KEY, run["context_policy_version"]),
    ).fetchone()
    config = None if configuration is None else configuration["configuration"]
    if (
        not isinstance(config, dict)
        or config.get("topology", {}).get("asset_map_id") != MAP_ID
        or config.get("compiled_plan", {}).get("asset_map_id") != MAP_ID
        or config.get("compiled_plan", {}).get("definition_id") != DEFINITION_ID
        or config.get("route", {}).get("key") != ROUTE_KEY
    ):
        raise ValueError("Astrub story pinned configuration changed map identity")
    from wakfu_server.combat_mission_allies import DECLARATIONS, POLICY

    expected = DECLARATIONS[POLICY]["rooms"]
    rooms = progress.get("rooms")
    if (
        not isinstance(rooms, list)
        or len(rooms) != 3
        or [row.get("order") for row in rooms] != [1, 2, 3]
        or any(_references(room) != expected[room["order"]] for room in rooms)
    ):
        raise ValueError(
            "Astrub story frozen encounter roster differs from its reviewed rooms"
        )
    return dict(
        instance=instance_id,
        run=run,
        progress=progress,
        state=state,
        room=progress["current_room"],
        configuration=config,
        receipt=receipt,
    )


def combat_helper_admission(store, character, members):
    """Admit Tristepin only to an owned, already introduced live room group."""
    members = tuple(members)
    with store.connection() as db:
        scope = context(db, character)
        if scope is None:
            return None
        instance_id, room = scope["instance"], scope["room"]
        receipt = scope["receipt"]
        if (
            not isinstance(receipt, dict)
            or receipt.get("schema") != START_SCHEMA
            or receipt.get("owner") != character["id"]
            or receipt.get("instance_id") != instance_id
        ):
            raise ValueError("Astrub combat ally lacks its owned story introduction")
        expected_callback = {1: 23920, 2: 23922, 3: 23924}[room]
        if (
            _receipt(db, character["id"], callback_key(instance_id, expected_callback))
            is None
        ):
            raise ValueError("Finish the pending Astrub story scene before fighting")
        spawned = db.execute(
            "SELECT * FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
            (instance_id, room),
        ).fetchone()
        if spawned is None or spawned.get("asset_map_id") != MAP_ID:
            raise ValueError("Astrub combat ally has no owned room spawn receipt")
        group = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s "
            "AND instance_id=%s AND group_id=%s",
            (MAP_ID, instance_id, spawned["group_id"]),
        ).fetchone()
        if group is None or group.get("status") not in ("available", "fighting"):
            raise ValueError("Astrub combat ally requires the live owned room group")

        def identity(member):
            if (
                not isinstance(member, dict)
                or type(member.get("id")) is not int
                or member["id"] >= 0
                or type(member.get("ref")) is not int
                or member["ref"] <= 0
                or any(type(member.get(k)) is not int for k in ("x", "y", "z"))
                or member.get("map_id") != MAP_ID
                or member.get("instance_id") != instance_id
            ):
                raise ValueError(
                    "Astrub combat member differs from its owned native actor"
                )
            return member["id"], member["ref"], member["x"], member["y"], member["z"]

        actual = tuple(sorted(identity(member) for member in members))
        registered = tuple(sorted(identity(member) for member in group["members"]))
        if actual != registered or len({member[0] for member in actual}) != len(actual):
            raise ValueError(
                "Astrub combat roster differs from the exact owned room group"
            )
    from wakfu_server.combat_mission_allies import admit

    return admit(character, members, room=room)
