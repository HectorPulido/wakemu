"""Renewable native owned quest groups, independent of main-room progression.

The pinned declaration supplies reviewed formation/timing, not original combat
stats or drop odds. Existing event rows retain group/fight provenance; normal
Groups, admission, combat and drop delivery own every actual encounter.
"""
from copy import deepcopy
import json

from psycopg.types.json import Jsonb

SCHEMA = "owned-quest-pool-v1"
PREFIX = "owned-quest-pool:"


def digest(value):
    from wakfu_server.owned_story_controller import _digest

    return _digest(value)


def policies(configuration):
    topology = configuration.get("topology", {})
    rows = topology.get("owned_quest_pools", [])
    if not isinstance(rows, list):
        raise ValueError("Owned quest pools require explicit declarations")
    if not rows:
        return ()
    exploration = topology.get("exploration_geometry", {})
    cells = set(map(tuple, exploration.get("cells", ())))
    edges = {(tuple(a), tuple(b)) for a, b in exploration.get("edges", ())}
    if (
        not cells
        or not edges
        or exploration.get("map_id") != topology.get("asset_map_id")
        or configuration.get("compiled_plan", {}).get("asset_map_id")
        != exploration["map_id"]
    ):
        raise ValueError("Quest pool lacks its pinned original exploration graph")
    ids, result = set(), []
    fields = {
        "schema",
        "id",
        "quest_id",
        "unfinished_objective_id",
        "item_reference",
        "stop_quantity",
        "loot_contract",
        "anchor",
        "bounds",
        "z",
        "monsters",
        "evidence",
    }
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != fields
            or row["schema"] != SCHEMA
            or not isinstance(row["id"], str)
            or not row["id"]
            or len(row["id"]) > 64
            or ":" in row["id"]
            or row["id"] in ids
            or not row["evidence"]
            or not row["loot_contract"]
            or any(
                type(row[k]) is not int or row[k] <= 0
                for k in (
                    "quest_id",
                    "unfinished_objective_id",
                    "item_reference",
                    "stop_quantity",
                )
            )
            or not isinstance(row["anchor"], list)
            or len(row["anchor"]) != 3
            or any(type(n) is not int for n in row["anchor"])
            or not isinstance(row["bounds"], list)
            or len(row["bounds"]) != 4
            or any(type(n) is not int for n in row["bounds"])
            or type(row["z"]) is not int
            or not isinstance(row["monsters"], list)
            or not row["monsters"]
        ):
            raise ValueError("Invalid owned quest pool declaration")
        ids.add(row["id"])
        references = set()
        for member in row["monsters"]:
            if (
                not isinstance(member, dict)
                or set(member) != {"reference", "count"}
                or any(type(member[k]) is not int or member[k] <= 0 for k in member)
                or member["reference"] in references
            ):
                raise ValueError("Quest pool lacks an exact original native roster")
            references.add(member["reference"])
        quantity = sum(member["count"] for member in row["monsters"])
        left, bottom, right, top = row["bounds"]
        available = {
            p
            for p in cells
            if left <= p[0] <= right and bottom <= p[1] <= top and p[2] == row["z"]
        }
        anchor = tuple(row["anchor"])
        if anchor not in available or quantity > 8:
            raise ValueError("Quest pool anchor or roster exceeds native capacity")
        outgoing, incoming = {}, {}
        for a, b in edges:
            if a in available and b in available:
                outgoing.setdefault(a, set()).add(b)
                incoming.setdefault(b, set()).add(a)

        def reached(graph):
            seen, pending = {anchor}, [anchor]
            while pending:
                for cell in graph.get(pending.pop(), set()) - seen:
                    seen.add(cell)
                    pending.append(cell)
            return seen

        connected = reached(outgoing) & reached(incoming)
        if len(connected) < quantity + 8:
            raise ValueError("Quest pool cannot fit an ordinary native encounter")
        result.append(
            dict(
                declaration=deepcopy(row),
                cells=frozenset(connected),
                edges=frozenset(
                    (a, b) for a, b in edges if a in connected and b in connected
                ),
            )
        )
    return tuple(result)


def _key(kind, identity):
    return PREFIX + kind + ":" + str(identity)


def _read(db, owner, key):
    row = db.execute(
        "SELECT signature,payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (owner, key),
    ).fetchone()
    if row is None:
        return None
    if row["signature"] != digest(row["payload"]):
        raise ValueError("Quest pool receipt source changed")
    return row["payload"]


def _write(db, owner, key, payload):
    db.execute(
        "INSERT INTO character_achievement_events(character_id,event_key,signature,payload) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT(character_id,event_key) DO NOTHING",
        (owner, key, digest(payload), Jsonb(payload)),
    )
    if _read(db, owner, key) != payload:
        raise ValueError("Conflicting owned quest pool replay")


def _owner(db, instance_id):
    rows = db.execute(
        "SELECT c.id,c.account_id,c.map_id,c.instance_id "
        "FROM dungeon_instance_members m JOIN characters c ON c.id=m.character_id "
        "JOIN dungeon_instances i ON i.instance_id=m.instance_id "
        "WHERE m.instance_id=%s AND m.status='active' AND i.status='active' ORDER BY c.id",
        (instance_id,),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Quest pool requires one actual owned instance member")
    return rows[0]


def _eligible(db, owner, declaration):
    from wakfu_server.achievements import storage
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    state = storage.load_locked(db, owner)
    authority = queries_from_state(state)
    quantity = db.execute(
        "SELECT COALESCE(SUM(quantity),0) AS quantity FROM inventory_items "
        "WHERE character_id=%s AND reference=%s",
        (owner, declaration["item_reference"]),
    ).fetchone()["quantity"]
    return (
        authority["IsAchievementRunning"](declaration["quest_id"])
        and not authority["IsAchievementObjectiveComplete"](
            declaration["unfinished_objective_id"]
        )
        and quantity < declaration["stop_quantity"]
    )


def _configuration(db, instance_id):
    from wakfu_server import dungeon_runtime

    return dungeon_runtime.configuration_for_instance(db, instance_id)[1]


def group_receipt(db, group_key, *, configuration=None):
    map_id, instance_id, group_id = group_key
    if instance_id <= 0:
        return None
    config = _configuration(db, instance_id) if configuration is None else configuration
    declared = policies(config)
    if not declared:
        return None
    owner = _owner(db, instance_id)
    receipt = _read(db, owner["id"], _key("group", f"{instance_id}:{group_id}"))
    if receipt is None:
        return None
    selected = next(
        (p for p in declared if p["declaration"]["id"] == receipt.get("pool_id")), None
    )
    if (
        selected is None
        or receipt.get("schema") != SCHEMA
        or receipt.get("scope") != "owned_quest_pool"
        or receipt.get("owner_id") != owner["id"]
        or receipt.get("instance_id") != instance_id
        or receipt.get("group_id") != group_id
        or receipt.get("map_id") != map_id
        or map_id != config["topology"]["asset_map_id"]
        or receipt.get("profile_sha256") != digest(selected["declaration"])
        or receipt.get("route_key") != config["route"]["key"]
        or receipt.get("policy_version") != config["version"]
    ):
        raise ValueError("Quest pool group differs from its frozen owned source")
    group = db.execute(
        "SELECT members,status FROM combat_groups "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        group_key,
    ).fetchone()
    if group is None or group["members"] != receipt["members"]:
        raise ValueError("Quest pool lost its original registered group")
    return dict(receipt=receipt, selected=selected, owner=owner, group=group)


def ensure(db, groups, instance_id, configuration, geometry):
    declared = policies(configuration)
    if not declared:
        return ()
    owner = _owner(db, instance_id)
    map_id = configuration["topology"]["asset_map_id"]
    if owner["instance_id"] != instance_id or owner["map_id"] != map_id:
        return ()  # The normal transition has not committed its destination yet.
    actual_cells = set(map(tuple, geometry["cells"]))
    actual_edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    if geometry["map_id"] != map_id:
        raise ValueError("Quest pool uses another native map")
    # Use the same owner-first lock as ordinary actor/session writers, then
    # serialize the head before allocating a fresh registered generation.
    db.execute("SELECT id FROM characters WHERE id=%s FOR UPDATE", (owner["id"],))
    result = []
    for selected in declared:
        declaration = selected["declaration"]
        if (
            not selected["cells"] <= actual_cells
            or not selected["edges"] <= actual_edges
        ):
            raise ValueError("Quest pool differs from the actual native terrain")
        head_key = _key("head", f"{instance_id}:{declaration['id']}")
        head = _read(db, owner["id"], head_key)
        if head is not None:
            found = group_receipt(
                db, (map_id, instance_id, head["group_id"]), configuration=configuration
            )
            if found["selected"]["declaration"]["id"] != declaration["id"]:
                raise ValueError("Quest pool head belongs to another declared pool")
            if found["group"]["status"] != "defeated":
                continue  # Loss, abort and reconnect reuse their genuine group.
        if not _eligible(db, owner["id"], declaration):
            continue
        from wakfu_server import monsters, dungeon_encounters, npc_actor_identity

        generation = 1 if head is None else head["generation"] + 1
        group_id = db.execute(
            "SELECT nextval('dungeon_room_group_ids') AS id"
        ).fetchone()["id"]
        roster = []
        for member in declaration["monsters"]:
            native = monsters.reference(member["reference"])
            roster.append(
                dict(
                    ref_id=native["ref"],
                    count=member["count"],
                    min_level=native["min_level"],
                    max_level=native["max_level"],
                )
            )
        section = dict(
            geometry, cells=tuple(selected["cells"]), edges=tuple(selected["edges"])
        )
        members = dungeon_encounters.roster_members(
            instance_id,
            roster,
            asset_map_id=map_id,
            anchor=declaration["anchor"],
            geometry=section,
            group_id=group_id,
            select_level=lambda native, _row: native["min_level"],
            player_slots=6,
            actor_id_base=npc_actor_identity.allocate_block(db, 128),
        )
        groups.register_transaction(db, map_id, instance_id, group_id, members)
        # Read back the canonical registered members, including any source-owned aliases.
        members = db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s "
            "AND instance_id=%s AND group_id=%s",
            (map_id, instance_id, group_id),
        ).fetchone()["members"]
        receipt = dict(
            schema=SCHEMA,
            scope="owned_quest_pool",
            pool_id=declaration["id"],
            owner_id=owner["id"],
            map_id=map_id,
            instance_id=instance_id,
            group_id=group_id,
            generation=generation,
            profile_sha256=digest(declaration),
            route_key=configuration["route"]["key"],
            policy_version=configuration["version"],
            members=members,
        )
        _write(db, owner["id"], _key("group", f"{instance_id}:{group_id}"), receipt)
        current = dict(group_id=group_id, generation=generation)
        if head is None:
            _write(db, owner["id"], head_key, current)
        else:
            changed = db.execute(
                "UPDATE character_achievement_events SET signature=%s,payload=%s "
                "WHERE character_id=%s AND event_key=%s AND signature=%s",
                (digest(current), Jsonb(current), owner["id"], head_key, digest(head)),
            )
            if changed.rowcount != 1:
                raise ValueError("Concurrent quest pool generation changed")
        result.append(dict(receipt, status="available", replay=False))
    return tuple(result)


def available(db, map_id, instance_id):
    if instance_id <= 0:
        return ()
    # The ordinary owned map path stays cheap when no pool receipt exists.
    rows = db.execute(
        "SELECT e.signature,e.payload FROM character_achievement_events e "
        "JOIN dungeon_instance_members m ON m.character_id=e.character_id "
        "WHERE m.instance_id=%s AND m.status='active' AND e.event_key LIKE %s",
        (instance_id, _key("head", str(instance_id)) + ":%"),
    ).fetchall()
    result = []
    for row in rows:
        if row["signature"] != digest(row["payload"]):
            raise ValueError("Quest pool head source changed")
        found = group_receipt(db, (map_id, instance_id, row["payload"]["group_id"]))
        if found is None:
            raise ValueError("Quest pool head has no actual registered source")
        if found["group"]["status"] == "available":
            result.append(
                dict(
                    key=(map_id, instance_id, found["receipt"]["group_id"]),
                    members=deepcopy(found["receipt"]["members"]),
                )
            )
    return tuple(result)


def combat_cells(db, group_key, configuration, positions):
    found = group_receipt(db, group_key, configuration=configuration)
    if found is None:
        return None
    cells = found["selected"]["cells"]
    if any(tuple(p) not in cells for p in positions):
        raise ValueError("Quest pool combatant is outside its pinned native component")
    return cells


def member_scope(db, character, members, configuration):
    """Recognize only an actual current pool roster before main admission."""
    if not policies(configuration):
        return False
    wanted = {(row["id"], row["ref"]) for row in members}
    if len(wanted) != len(members):
        raise ValueError("Quest pool admission repeats an original actor")
    for group in available(db, character["map_id"], character["instance_id"]):
        if wanted == {(row["id"], row["ref"]) for row in group["members"]}:
            return True
    return False


def bind(db, group_key, character_id, fight_id, *, player_team=0):
    if _read(db, character_id, _key("group", f"{group_key[1]}:{group_key[2]}")) is None:
        return None
    found = group_receipt(db, group_key)
    if found is None:
        return None
    if (
        found["owner"]["id"] != character_id
        or found["owner"]["map_id"] != group_key[0]
        or found["owner"]["instance_id"] != group_key[1]
        or not _eligible(db, character_id, found["selected"]["declaration"])
    ):
        raise ValueError(
            "Quest pool no longer belongs to a running unfinished assignment"
        )
    participants = db.execute(
        "SELECT character_id,team FROM combat_fight_participants "
        "WHERE fight_id=%s ORDER BY character_id",
        (fight_id,),
    ).fetchall()
    if participants != [dict(character_id=character_id, team=player_team)]:
        raise ValueError("Quest pool requires its one real fight participant")
    payload = dict(found["receipt"], fight_id=fight_id, player_team=player_team)
    _write(db, character_id, _key("fight", fight_id), payload)
    return payload


def bound_fight(db, fight_id, character_id):
    """A pool battle never becomes a main-room admission/victory event."""
    proof = _read(db, character_id, _key("fight", fight_id))
    if proof is None:
        return None
    found = group_receipt(
        db, (proof["map_id"], proof["instance_id"], proof["group_id"])
    )
    if (
        found is None
        or proof
        != dict(found["receipt"], fight_id=fight_id, player_team=proof["player_team"])
        or found["owner"]["id"] != character_id
    ):
        raise ValueError("Quest pool fight lost its admitted original group")
    return dict(found, proof=proof)


def loot_basis(db, fight_id, character_id, *, fight=None, original_monsters=None):
    found = bound_fight(db, fight_id, character_id)
    if found is None:
        return None
    proof = found["proof"]
    from wakfu_server.achievements.owned_quest_encounters import qualified_roster

    selected = dict(
        quest_id=found["selected"]["declaration"]["quest_id"],
        roster=found["selected"]["declaration"]["monsters"],
    )
    members = proof["members"]
    earned_key = _key("earned", fight_id)
    earned = _read(db, character_id, earned_key)
    if fight is not None:
        deaths = {
            event.get("actor_id")
            for event in fight.events
            if event.get("kind") == "death"
        }
        operator_victory = False
        if not {m["id"] for m in members} <= deaths:
            from wakfu_server.combat_test_commands import administrative_victory

            owner = found.get("owner")
            if isinstance(owner, dict) and type(owner.get("account_id")) is int:
                operator_victory = administrative_victory(
                    fight, account_id=owner["account_id"], character_id=character_id
                )
        if (
            fight.id != fight_id
            or fight.phase != "finished"
            or fight.winner != proof["player_team"]
            or not qualified_roster(fight, members, selected)
            or (not {m["id"] for m in members} <= deaths and not operator_victory)
            or original_monsters is None
            or {(m["id"], m["ref"]) for m in original_monsters}
            != {(m["id"], m["ref"]) for m in members}
        ):
            raise ValueError("Quest pool loot lacks its genuine original-enemy victory")
        if earned is None:
            eligible = _eligible(db, character_id, found["selected"]["declaration"])
            earned = dict(
                fight_id=fight_id,
                profile_sha256=proof["profile_sha256"],
                group_id=proof["group_id"],
                eligible=eligible,
                winner_team=fight.winner,
                victory_source=(
                    "administrative_original_enemy_victory"
                    if operator_victory
                    else "native_original_enemy_deaths"
                ),
            )
            _write(db, character_id, earned_key, earned)
    if (
        earned is None
        or earned.get("fight_id") != fight_id
        or earned.get("profile_sha256") != proof["profile_sha256"]
        or earned.get("group_id") != proof["group_id"]
        or earned.get("winner_team") != proof["player_team"]
    ):
        raise ValueError("Quest pool lacks its frozen earned loot authority")
    return dict(
        proof=proof,
        declaration=found["selected"]["declaration"],
        eligible=earned["eligible"],
    )


def refresh_after_finish(session, group_key):
    state, runtime = session.state, session.runtime
    if group_key[1] <= 0:
        return
    with runtime.STORE.connection() as db:
        if (
            _read(
                db,
                state.character["id"],
                _key("group", f"{group_key[1]}:{group_key[2]}"),
            )
            is None
        ):
            return  # Ordinary owned fights never load a pool configuration.
        found = group_receipt(db, group_key)
        if found is None:
            return
        from wakfu_server import dungeon_runtime
        from wakfu_server.combat_terrain import map_geometry

        configuration = _configuration(db, group_key[1])
        ensure(
            db,
            runtime.COMBAT_GROUPS,
            group_key[1],
            configuration,
            map_geometry(group_key[0]),
        )
