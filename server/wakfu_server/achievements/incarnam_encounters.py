"""Owned Incarnam tutorial Wodents and their authoritative fight outcomes."""
import secrets
import struct

MAP_ID = 1361
BREED = 5525
ACTION = 1254
POSITIONS = {1: (12, -18, -16), 2: (12, -54, -10)}


def scene_owner(character):
    from wakfu_server.intro_cinematic import private_instance_id

    return (
        character.get("map_id") == MAP_ID
        and type(character.get("id")) is int
        and character.get("instance_id") == private_instance_id(character["id"])
    )


def return_bootstrap(character, packets, *, abandoned):
    """Keep the loaded tutorial world and its Lua scene on normal fight exit.

    The native client's first Wodent outro uses particles created by the entry
    scenario. Sending a world transition at fight return reloads Lua and loses
    those particles. The official same-instance return does not send one.
    """
    if type(abandoned) is not bool:
        raise ValueError("Invalid Incarnam fight return state")
    if not abandoned and scene_owner(character):
        return tuple(packet for packet in packets if packet[0] not in (13256, 13974))
    return tuple(packets)


def stage(state):
    running, completed = set(state["running"]), set(state["completed"])
    if 5135 in running:
        return 1
    if 5135 in completed and 5139 not in completed:
        return 2
    return None


def ensure_spawn(store, groups, character):
    """Publish at most one owned Wodent for this private scene and quest stage."""
    if not scene_owner(character):
        return None
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_monster_world import spawn_group
    from . import storage

    with groups.lock, store.connection() as db:
        state = storage.load_locked(db, character["id"])
        step = stage(state)
        if step is None:
            return None
        if (
            step == 2
            and db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (character["id"], "incarnam-final-fight:won"),
            ).fetchone()
        ):
            return None
        for group in groups.available(MAP_ID, character["instance_id"]):
            for member in group["members"]:
                if member.get("ref") != BREED or member.get("id", 0) >= 0:
                    continue
                receipt = db.execute(
                    "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (character["id"], f"incarnam-wodent:{-member['id']}"),
                ).fetchone()
                expected = {
                    "kind": "incarnam_wodent",
                    "owner": character["id"],
                    "actor_id": member["id"],
                    "stage": step,
                }
                if receipt and receipt["payload"] == expected:
                    # Repair only this owner's available scripted group if generic
                    # ecology moved it or merged ordinary monsters into its roster.
                    expected_position = POSITIONS[step]
                    if (
                        len(group["members"]) != 1
                        or tuple(member[k] for k in ("x", "y", "z"))
                        != expected_position
                    ):
                        from psycopg.types.json import Jsonb

                        key = group["key"]
                        db.execute(
                            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                            ("monster-population:" + ":".join(map(str, key[:2])),),
                        )
                        restored = dict(
                            member,
                            x=expected_position[0],
                            y=expected_position[1],
                            z=expected_position[2],
                        )
                        changed = db.execute(
                            "UPDATE combat_groups SET members=%s WHERE map_id=%s AND instance_id=%s "
                            "AND group_id=%s AND status='available' AND members=%s RETURNING group_id",
                            (Jsonb([restored]), *key, Jsonb(group["members"])),
                        ).fetchone()
                        if not changed:
                            raise ValueError("Incarnam actor changed during repair")
                        db.execute(
                            "DELETE FROM combat_group_members WHERE map_id=%s AND instance_id=%s "
                            "AND group_id=%s AND monster_id<>%s",
                            (*key, member["id"]),
                        )
                        return 12608, spawn_group([restored], group_id=key[2])
                    return None
        actor_id = -allocate_block(db, 1)
        x, y, z = POSITIONS[step]
        actor = owned_instance(
            BREED,
            1,
            actor_id,
            map_id=MAP_ID,
            instance_id=character["instance_id"],
            x=x,
            y=y,
            z=z,
        )
        receipt = {
            "kind": "incarnam_wodent",
            "owner": character["id"],
            "actor_id": actor_id,
            "stage": step,
        }
        if not storage.record_event(
            db, character["id"], f"incarnam-wodent:{-actor_id}", receipt
        ):
            raise ValueError("Incarnam encounter receipt already exists")
        group_id = secrets.randbits(62) + 1
        groups.register_transaction(
            db, MAP_ID, character["instance_id"], group_id, [actor]
        )
    return 12608, spawn_group([actor], group_id=group_id)


def prepare(db, character, body, group):
    """Accept the native attack action only for the owner's current tutorial."""
    if not scene_owner(character) or len(body) != 16:
        return None
    target, action = struct.unpack(">qq", body)
    if target >= 0 or action != ACTION:
        return None
    members = group.get("members", ())
    if (
        len(members) != 1
        or members[0].get("id") != target
        or members[0].get("ref") != BREED
    ):
        return None
    from . import storage

    state = storage.load_locked(db, character["id"])
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"incarnam-wodent:{-target}"),
    ).fetchone()
    if not row:
        return None
    receipt = row["payload"]
    current = stage(state)
    if receipt != {
        "kind": "incarnam_wodent",
        "owner": character["id"],
        "actor_id": target,
        "stage": current,
    } or (current == 2 and 5139 not in state["running"]):
        raise ValueError("Incarnam tutorial encounter is not active")
    actor = members[0]
    from wakfu_server.objectives.environmental_monster_actions import (
        native_action_response,
    )

    return {
        "target_id": target,
        "position": (actor["x"], actor["y"], actor["z"]),
        "action_id": action,
        "group_key": group.get("key"),
        "authority": "official_incarnam_capture",
        "source_sha256": None,
        "native_response": native_action_response(target, character["id"], action),
        "incarnam_stage": current,
    }


def settle(db, store, fight, members, monsters):
    """Only the owned player's victorious, committed encounter advances quests."""
    if fight.phase != "finished" or fight.winner not in (0, 1):
        return {}
    if len(monsters) != 1 or monsters[0].get("ref") != BREED:
        return {}
    target = monsters[0].get("id")
    if type(target) is not int or target >= 0 or target not in fight.actors:
        return {}
    from . import incarnam_tutorial, storage

    result = {}
    for member in members:
        identity, account = member.get("character_id"), member.get("account_id")
        actor = fight.actors.get(identity)
        if (
            actor is None
            or member.get("withdrawn")
            or not member.get("session_generation")
            or actor.team != fight.winner
            or fight.actors[target].team == actor.team
        ):
            continue
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (identity, f"incarnam-wodent:{-target}"),
        ).fetchone()
        if not row:
            continue
        receipt = row["payload"]
        step = receipt.get("stage")
        if receipt != {
            "kind": "incarnam_wodent",
            "owner": identity,
            "actor_id": target,
            "stage": step,
        } or step not in (1, 2):
            continue
        participant = db.execute(
            "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
            "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
            "AND p.character_id=%s AND p.account_id=%s",
            (fight.id, identity, account),
        ).fetchone()
        if (
            not participant
            or participant["status"] != "finished"
            or participant["fight_kind"] != "pve"
            or participant["team"] != actor.team
        ):
            continue
        store.lock_character(db, account, member["session_generation"], identity)
        character = store.character(account, identity, db)
        if not scene_owner(character):
            continue
        if step == 1:
            packets = incarnam_tutorial.settle(
                db, store, character, event="first_wodent_victory", token=str(fight.id)
            )
            result.setdefault(account, []).extend(packets)
        else:
            state = storage.load_locked(db, identity)
            if 5139 in state["running"]:
                storage.record_event(
                    db,
                    identity,
                    "incarnam-final-fight:won",
                    {"kind": "incarnam_final_victory"},
                )
    return result


def pending_final(db, character):
    if not scene_owner(character):
        return False
    from . import storage

    state = storage.load_locked(db, character["id"])
    return (
        5139 in state["running"]
        and db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], "incarnam-final-fight:won"),
        ).fetchone()
        is not None
    )


class CombatGuides:
    """Session-local native guide cues after accepted fight actions."""

    def __init__(self, fight_id, owner_id, stage):
        if type(fight_id) is not int or fight_id <= 0 or stage not in (1, 2):
            raise ValueError("Invalid Incarnam combat guide context")
        self.fight_id, self.owner_id, self.stage = fight_id, owner_id, stage
        self._seen = set()

    def observe(self, fight, actor_id, action):
        if (
            fight.id != self.fight_id
            or actor_id != self.owner_id
            or fight.phase == "finished"
        ):
            return []
        from wakfu_server.intro_cinematic import scenario_event

        packets = []
        if action == "move" and "move" not in self._seen:
            self._seen.add("move")
            packets.append(scenario_event(22514 if self.stage == 1 else 22528, 2500))
        if action == "end_turn" and self.stage == 1 and "turn" not in self._seen:
            self._seen.add("turn")
            packets.append(scenario_event(22515, 2500, fight.id))
        actor = fight.actors.get(actor_id)
        if action == "cast" and actor is not None and actor.ap < 3:
            packets.append(scenario_event(22529, 2500, 10 if self.stage == 1 else 50))
        return packets


def recover_guides(db, character, fight):
    """Restore guide context from the owned monster receipt after reconnect."""
    if not scene_owner(character) or fight.phase == "finished":
        return None
    targets = [
        identity for identity in fight.actors if type(identity) is int and identity < 0
    ]
    if not targets:
        return None
    rows = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=ANY(%s)",
        (character["id"], [f"incarnam-wodent:{-target}" for target in targets]),
    ).fetchall()
    matching = [
        row["payload"]
        for row in rows
        if isinstance(row.get("payload"), dict)
        and row["payload"].get("kind") == "incarnam_wodent"
        and row["payload"].get("owner") == character["id"]
        and row["payload"].get("actor_id") in targets
        and row["payload"].get("stage") in (1, 2)
    ]
    if len(matching) != 1:
        return None
    return CombatGuides(fight.id, character["id"], matching[0]["stage"])


def arena_policy(db, character, monsters, geometry):
    """Pin owned tutorial fights to the captured floor, preserving world positions.

    Ordinary procedural relocation can choose a different vertically overlapping
    surface on Incarnam. The captured fights were both on a single corridor.
    """
    if not scene_owner(character) or len(monsters) != 1:
        return None
    monster = monsters[0]
    target = monster.get("id")
    if monster.get("ref") != BREED or type(target) is not int or target >= 0:
        return None
    row = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"incarnam-wodent:{-target}"),
    ).fetchone()
    if not row or not isinstance(row["payload"], dict):
        return None
    stage = row["payload"].get("stage")
    if row["payload"] != {
        "kind": "incarnam_wodent",
        "owner": character["id"],
        "actor_id": target,
        "stage": stage,
    } or stage not in (1, 2):
        return None
    low, high, height = (-20, -9, -16) if stage == 1 else (-57, -47, -10)
    cells = {
        tuple(cell)
        for cell in geometry["cells"]
        if 9 <= cell[0] <= 15 and low <= cell[1] <= high and cell[2] == height
    }
    player = tuple(character[k] for k in ("x", "y", "z"))
    target_pos = tuple(monster[k] for k in ("x", "y", "z"))
    if player not in cells or target_pos not in cells:
        raise ValueError("Approach the Wodent on the tutorial floor to start combat")
    edges = [
        (tuple(a), tuple(b))
        for a, b in geometry["edges"]
        if tuple(a) in cells and tuple(b) in cells
    ]
    reachable, queue = {player}, [player]
    adjacency = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
    while queue:
        for cell in adjacency.get(queue.pop(), ()):
            if cell not in reachable:
                reachable.add(cell)
                queue.append(cell)
    if target_pos not in reachable:
        raise ValueError("Tutorial fight participants are not on a connected floor")
    return {
        "allowed_cells": reachable,
        "relocate_monsters": False,
        "ordinary_npc_placement": False,
    }
