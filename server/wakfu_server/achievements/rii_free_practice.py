"""Airyna's native independent potato-sack practice action (1252)."""
import secrets
import struct

ACTOR = -1706442046308339
ACTION = 1252
REF = 2335
LARGE_REF = 5585
KEY = "rii-free-practice-sack:"
KIND = "rii_free_practice_sack"
MENU = 3612
MULTI_MENU = 5195
BASIC_CHOICE = 9126
TWO_ZERO_CHOICE = 12369
THREE_ZERO_CHOICE = 12372
MULTI_CHOICE = 12376
MENU_EXIT = 9113
MULTI_EXIT = 12375

# The native menu labels specify elemental resistance percentages. These are
# the minimum native resistance points that yield each displayed percentage
# with fau's rounded resistance multiplier. Large sacks use the native
# nine-cell profile (physical radius 1).
RESISTANCE_POINTS = {
    0: 0,
    10: 48,
    20: 101,
    30: 160,
    40: 229,
    50: 311,
    60: 411,
    70: 540,
    80: 722,
    90: 1032,
}
PRACTICE_CHOICES = {
    **{
        (MENU, 9126 - percent // 10): (1, percent, REF) for percent in RESISTANCE_POINTS
    },
    **{
        (MULTI_MENU, 12369 + index): (2, percent, REF)
        for index, percent in enumerate((0, 50, 90))
    },
    **{
        (MULTI_MENU, 12372 + index): (3, percent, REF)
        for index, percent in enumerate((0, 50, 90))
    },
    (MULTI_MENU, 13733): (1, 0, LARGE_REF),
}


def begin_menu(character_provider, rows_provider, actor_id, action_id):
    """Open the native practice selection; only qualified variants may start."""
    from wakfu_server import npc_world, npc_protectors
    from wakfu_server.npc_dialogue import DialogueSession, catalog

    if (actor_id, action_id) != (ACTOR, ACTION):
        raise ValueError("Unavailable training action")
    character = character_provider()
    owner = (character["id"], character["account_id"])
    rows = npc_world.validate_placements(rows_provider())
    row = next((r for r in rows if r["actor_id"] == ACTOR), None)
    if (
        row is None
        or row["reference_id"] != 5460
        or row["map_id"] != 1388
        or row["instance_id"] != 0
        or not npc_world.nearby(character, row)
    ):
        raise ValueError("Airyna is unavailable or out of range")
    nodes = catalog()["node_index"]
    for node_id, choices in (
        (MENU, {BASIC_CHOICE, MULTI_CHOICE, MENU_EXIT}),
        (MULTI_MENU, {TWO_ZERO_CHOICE, THREE_ZERO_CHOICE, MULTI_EXIT}),
    ):
        if node_id not in nodes or not choices <= {
            c["id"] for c in nodes[node_id]["choices"]
        }:
            raise ValueError("Native training menu is unavailable")
    kind, speaker = npc_protectors.speaker(row)

    def authorize(speaker_id, node_id):
        current = character_provider()
        latest = next((r for r in rows_provider() if r["actor_id"] == ACTOR), None)
        return (
            speaker_id == speaker
            and node_id in (MENU, MULTI_MENU)
            and latest == row
            and (current.get("id"), current.get("account_id")) == owner
            and npc_world.nearby(current, row)
        )

    graph = {
        **{key: 0 for key in PRACTICE_CHOICES},
        (MENU, MULTI_CHOICE): MULTI_MENU,
        (MENU, MENU_EXIT): 0,
        (MULTI_MENU, MULTI_EXIT): 0,
    }
    session = DialogueSession(
        nodes, graph, authorize_node=lambda node: node["id"] in (MENU, MULTI_MENU)
    )
    session.rii_free_practice_menu = True
    return session, session.open(MENU, speaker, authorize, speaker_type=kind)


def choose_menu(session, request):
    """Return the native response and the selected practice parameters."""
    if not getattr(session, "rii_free_practice_menu", False):
        raise ValueError("No training menu is open")
    node, choice = request["node_id"], request["choice_id"]
    if (node, choice) not in set(PRACTICE_CHOICES) | {
        (MENU, MULTI_CHOICE),
        (MENU, MENU_EXIT),
        (MULTI_MENU, MULTI_EXIT),
    }:
        raise ValueError("Esta modalidad de entrenamiento todavía no está disponible.")
    selected = PRACTICE_CHOICES.get((node, choice))
    params = (
        dict(count=selected[0], resistance_percent=selected[1], reference=selected[2])
        if selected is not None
        else None
    )
    return session.choose(node, choice), params


def payload(owner, actor, *, reference=REF, resistance_percent=0):
    result = {"kind": KIND, "owner": owner, "actor_id": actor, "ref": reference}
    if resistance_percent:
        result["resistance_percent"] = resistance_percent
    return result


def spawn(
    store,
    groups,
    account_id,
    generation,
    character,
    *,
    count=1,
    resistance_percent=0,
    reference=REF
):
    """Create or recover the selected owner-bound practice group."""
    from wakfu_server import npc_world
    from wakfu_server.combat_monster_world import spawn_group
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from . import storage

    if (
        type(count) is not int
        or count not in (1, 2, 3)
        or type(resistance_percent) is not int
        or resistance_percent not in RESISTANCE_POINTS
        or reference not in (REF, LARGE_REF)
        or reference == LARGE_REF
        and (count != 1 or resistance_percent != 0)
    ):
        raise ValueError("Invalid practice sack count")
    if (character.get("map_id"), character.get("instance_id")) != (1388, 0):
        raise ValueError("Practice is unavailable outside the dojo")
    with groups.lock, store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        if any(
            current[k] != character[k] for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Practice position changed")
        row = next(
            (
                r
                for r in npc_world.load_scene(db, 1388, 0)
                if r["actor_id"] == ACTOR and r["reference_id"] == 5460
            ),
            None,
        )
        if row is None or not npc_world.nearby(current, row):
            raise ValueError("Airyna is outside interaction range")
        available = groups.available(1388, 0)
        for group in available:
            members = group["members"]
            if len(members) != count:
                continue
            owned = True
            for actor in members:
                if (
                    actor.get("ref") != reference
                    or actor.get("id", 0) >= 0
                    or actor.get("rii_practice_resistance", 0) != resistance_percent
                ):
                    owned = False
                    break
                receipt = db.execute(
                    "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (current["id"], KEY + str(-actor["id"])),
                ).fetchone()
                if receipt is None or receipt["payload"] != payload(
                    current["id"],
                    actor["id"],
                    reference=reference,
                    resistance_percent=resistance_percent,
                ):
                    owned = False
                    break
            if owned:
                return (12608, spawn_group(members, group_id=group["key"][2])), members[
                    0
                ]
        origin = tuple(current[k] for k in ("x", "y", "z"))
        occupied = {
            tuple(a[k] for k in ("x", "y", "z"))
            for group in available
            for a in group["members"]
        }
        occupied.update(
            tuple(r[k] for k in ("x", "y", "z"))
            for r in npc_world.load_scene(db, 1388, 0)
        )
        geometry = published_geometry(1388)
        if reference == LARGE_REF:
            # A large sack occupies nine cells. Its centre must be two steps
            # from the player, leaving the closest edge adjacent to them.
            candidates = {
                p
                for adjacent in geometry.outgoing.get(origin, ())
                for p in geometry.outgoing.get(adjacent, ())
            }
            occupied.add(origin)
            cells = []
            for x, y, z in sorted(candidates):
                footprint = {
                    (x + dx, y + dy, z) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                }
                if footprint <= geometry.cells and not footprint & occupied:
                    cells.append((x, y, z))
        else:
            # Multi-sack groups need not all occupy cells touching the player.
            # Expand along walkable edges so an NPC or wall beside Airyna does
            # not make the native three-sack choice impossible.
            visited = {origin}
            frontier = {origin}
            cells = []
            for _ in range(3):
                frontier = {
                    p
                    for source in frontier
                    for p in geometry.outgoing.get(source, ())
                    if p not in visited
                }
                visited.update(frontier)
                cells.extend(sorted(p for p in frontier if p not in occupied))
                if len(cells) >= count:
                    break
        if len(cells) < count:
            raise ValueError("Not enough free cells for the training sacks")
        first_id = allocate_block(db, count)
        members = []
        for index, cell in enumerate(cells[:count]):
            actor_id = -(first_id + index)
            actor = owned_instance(
                reference,
                1,
                actor_id,
                map_id=1388,
                instance_id=0,
                x=cell[0],
                y=cell[1],
                z=cell[2],
            )
            if resistance_percent:
                actor["rii_practice_resistance"] = resistance_percent
            if not storage.record_event(
                db,
                current["id"],
                KEY + str(-actor_id),
                payload(
                    current["id"],
                    actor_id,
                    reference=reference,
                    resistance_percent=resistance_percent,
                ),
            ):
                raise ValueError("Duplicate practice encounter")
            members.append(actor)
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(db, 1388, 0, group_id, members)
    return (12608, spawn_group(members, group_id=group_id)), members[0]


def admit(db, owner, monsters):
    """Reject another player's explicitly owned practice sack."""
    for monster in monsters:
        actor = monster.get("id")
        if (
            monster.get("ref") not in (REF, LARGE_REF)
            or type(actor) is not int
            or actor >= 0
        ):
            continue
        rows = db.execute(
            "SELECT character_id,payload FROM character_achievement_events WHERE event_key=%s",
            (KEY + str(-actor),),
        ).fetchall()
        percent = monster.get("rii_practice_resistance", 0)
        if type(percent) is not int or percent not in RESISTANCE_POINTS:
            raise ValueError("Invalid practice resistance")
        valid = [
            row
            for row in rows
            if row["payload"]
            == payload(
                row["character_id"],
                actor,
                reference=monster["ref"],
                resistance_percent=percent,
            )
        ]
        if any(row["character_id"] != owner for row in valid):
            raise ValueError("This training encounter belongs to another player")
        if percent and not valid:
            raise ValueError("Missing authenticated practice resistance")


def start_request(actor):
    return struct.pack(">qiihB", actor["id"], actor["x"], actor["y"], actor["z"], 0)


def retire_used(db, key, *, fight_id, generation, revision):
    """Retire a finished owned dojo encounter behind its exact fight lease."""
    if tuple(key[:2]) != (1388, 0):
        return False
    row = db.execute(
        "SELECT members,status,generation,fight_id,revision FROM combat_groups "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if (
        row is None
        or row["status"] != "fighting"
        or (row["generation"], row["fight_id"], row["revision"])
        != (generation, fight_id, revision)
    ):
        return False
    members = row["members"]
    if not isinstance(members, list) or not members:
        return False
    # Every member must carry an exact authenticated ownership receipt; an
    # ordinary sack or mixed group must never be retired as an owned lesson.
    from .rii_lesson_visibility import group_owners

    owner = None
    for actor in members:
        if (
            not isinstance(actor, dict)
            or actor.get("ref") not in (REF, LARGE_REF, 5466)
            or type(actor.get("id")) is not int
            or actor["id"] >= 0
        ):
            return False
        current_owner = group_owners(db, [{"key": key, "members": [actor]}]).get(key)
        if current_owner is None or (owner is not None and current_owner != owner):
            return False
        owner = current_owner
    return (
        db.execute(
            "DELETE FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s "
            "AND status='fighting' AND generation=%s AND fight_id=%s AND revision=%s",
            (*key, generation, fight_id, revision),
        ).rowcount
        == 1
    )
