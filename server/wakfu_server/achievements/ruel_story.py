"""Reconstructed server producers for Ruel's Astrub investigation."""
import secrets
import struct

from . import mission_progress, rewards, ruel_hunts, storage, wire
from .service import _owner, drain_rewards

TRACE = (527, -72, 5, 0)
PHORREUR = 4689  # Native level-15 baby Phorreur, scenario visual 102200145.
TRACES = (
    (8453, 527, -74, -75, 0),
    (8454, 527, -43, -98, 0),
    (8455, 527, -41, -105, 0),
    (8455, 1094, -33, -34, 30),
    (8535, 1094, -18, -92, 30),
)

# Native action 323, the "Observe" menu entry, is delivered as ACTIVATE/0.
# The client's own criteria associate these four world objects with the
# ordered trace objectives; the first starts an encounter instead of completing.
TRACE_OBJECTS = {
    (527, 29306): (8452, -72, 5, 0),
    (527, 29314): (8453, -74, -75, 0),
    (527, 29315): (8454, -43, -98, 0),
    (1094, 29364): (8455, -33, -34, 30),
}


def recognizes_trace(map_id, body):
    if not isinstance(body, bytes) or len(body) != 12:
        return False
    identity, action, parameter = struct.unpack(">qHH", body)
    return (map_id, identity) in TRACE_OBJECTS and (action, parameter) == (0, 0)


def interact_trace(
    store, groups, account_id, generation, character, body, *, loaded, blocked
):
    """Authenticate an observed trace; merely walking past it does not count."""
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server import world_static

    if blocked or not loaded or not recognizes_trace(character["map_id"], body):
        raise ValueError("Trace interaction unavailable")
    identity, _, _ = struct.unpack(">qHH", body)
    objective, x, y, z = TRACE_OBJECTS[(character["map_id"], identity)]
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        _guard(db, character["id"])
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        interaction = world_static.interaction(current, body)
        if (
            current.get("instance_id", 0) != 0
            or interaction["type"] != "GenericActivableInteractiveElement"
            or (interaction["x"], interaction["y"], interaction["z"]) != (x, y, z)
            or abs(current["z"] - z) > 1
            or abs(current["x"] - x) + abs(current["y"] - y) > 4
        ):
            raise ValueError("Trace is outside interaction range")
        state = storage.load_locked(db, current["id"])
        previous = {8452: None, 8453: 8452, 8454: 8453, 8455: 8454}[objective]
        if (
            3972 not in state["running"]
            or objective in state["objectives"]
            or (previous is not None and previous not in state["objectives"])
        ):
            return {"packets": [], "scene_packet": None}
    if objective == 8452:
        return {
            "packets": [],
            "scene_packet": spawn_trace_fight(
                store, groups, account_id, generation, current
            ),
        }
    return {
        "packets": visit_trace(
            store, account_id, generation, current, objective=objective
        ),
        "scene_packet": None,
    }


def matching_trace(character):
    for objective, map_id, x, y, z in TRACES:
        if (
            character["map_id"] == map_id
            and character.get("instance_id", 0) == 0
            and character["z"] == z
            and abs(character["x"] - x) + abs(character["y"] - y) <= 1
        ):
            return objective
    return None


def visit_trace(store, account_id, generation, character, *, objective=None):
    """Settle a validated observation or the final arrival at the hideout."""
    if objective is None:
        objective = matching_trace(character)
        if objective != 8535:
            return []
    if objective is None:
        return []
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        state = storage.load_locked(db, current["id"])
        predecessor = {8453: 8452, 8454: 8453, 8455: 8454, 8535: 8455}[objective]
        if (
            3972 not in state["running"]
            or objective in state["objectives"]
            or predecessor not in state["objectives"]
        ):
            return []
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s", (ruel_hunts.SETTING,)
        ).fetchone()
        if not row or not row["value"].get("enabled"):
            return []
        definition = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
            (row["value"]["revision"], 3972),
        ).fetchone()
        if not definition:
            raise ValueError("Missing Ruel trace definition")
        now_ms = int(store.now().timestamp() * 1000)
        after, intents, added, completed = mission_progress.advance_objective(
            state,
            definition["data"]["native"],
            objective,
            character=current,
            store=store,
            now_ms=now_ms,
        )
        if not added:
            return []
        if (
            completed
            and 3973 not in after["running"]
            and 3973 not in after["completed"]
        ):
            after["running"].append(3973)
            after["running"].sort()
            mission_progress.auto_track(after, 3973)
        fact = {
            "kind": "reconstructed_ruel_trace_observation_v1",
            "objective": objective,
            "map_id": character["map_id"],
            "x": character["x"],
            "y": character["y"],
            "z": character["z"],
        }
        if not storage.record_event(db, current["id"], f"ruel-trace:{objective}", fact):
            raise ValueError("Ruel trace receipt exists without progress")
        for quest_id, reward in intents:
            rewards.validate(reward)
            storage.claim_reward(
                db, current["id"], quest_id, "once", reward["d"], reward
            )
        storage.store(db, current["id"], after)
        return wire.changes(
            current["id"], state, after, added, completed, now_ms
        ) + drain_rewards(db, store, current)


def near_trace(character):
    return (
        character["map_id"] == TRACE[0]
        and character.get("instance_id", 0) == 0
        and character["z"] == TRACE[3]
        and abs(character["x"] - TRACE[1]) + abs(character["y"] - TRACE[2]) <= 4
    )


def spawn_trace_fight(store, groups, account_id, generation, character):
    """Spawn an owned, retryable encounter after a validated movement."""
    if not near_trace(character):
        return None
    from wakfu_server.monsters import owned_instance
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import published_geometry
    from wakfu_server.combat_monster_world import spawn_group

    origin = tuple(character[k] for k in ("x", "y", "z"))
    geometry = published_geometry(TRACE[0])
    available = groups.available(TRACE[0], 0)
    occupied = {
        tuple(m[k] for k in ("x", "y", "z"))
        for group in available
        for m in group["members"]
    }
    available_keys = [
        f"ruel-phorreur:{-m['id']}"
        for group in available
        for m in group["members"]
        if m["ref"] == PHORREUR and m["id"] < 0
    ]
    candidates = [
        cell for cell in geometry.outgoing.get(origin, ()) if cell not in occupied
    ]
    if not candidates:
        return None
    group_id = secrets.randbits(62) + 1
    cell = candidates[0]
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        state = storage.load_locked(db, character["id"])
        if 3972 not in state["running"] or 8452 in state["objectives"]:
            return None
        if (
            available_keys
            and db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key = ANY(%s) LIMIT 1",
                (character["id"], available_keys),
            ).fetchone()
        ):
            return None
        policy = db.execute(
            "SELECT value FROM settings WHERE name=%s", (ruel_hunts.SETTING,)
        ).fetchone()
        if not policy or not policy["value"].get("enabled"):
            return None
        actor_id = -allocate_block(db, 1)
        monster = owned_instance(
            PHORREUR,
            15,
            actor_id,
            map_id=TRACE[0],
            instance_id=0,
            x=cell[0],
            y=cell[1],
            z=cell[2],
        )
        fact = {
            "kind": "reconstructed_ruel_phorreur_spawn_v1",
            "actor_id": actor_id,
            "reference": PHORREUR,
            "owner": character["id"],
        }
        storage.record_event(db, character["id"], f"ruel-phorreur:{-actor_id}", fact)
        groups.register_transaction(db, TRACE[0], 0, group_id, [monster])
    return (12608, spawn_group([monster], group_id=group_id))


def settle_trace_fight(db, store, character, event):
    """Count only victory over an encounter spawned for this character."""
    ids = [identity for identity, ref in event["original_monsters"] if ref == PHORREUR]
    if not ids:
        return []
    state = storage.load_locked(db, character["id"])
    if 3972 not in state["running"] or 8452 in state["objectives"]:
        return []
    for actor_id in ids:
        row = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], f"ruel-phorreur:{-actor_id}"),
        ).fetchone()
        if row and row["payload"] == {
            "kind": "reconstructed_ruel_phorreur_spawn_v1",
            "actor_id": actor_id,
            "reference": PHORREUR,
            "owner": character["id"],
        }:
            break
    else:
        return []
    policy = db.execute(
        "SELECT value FROM settings WHERE name=%s", (ruel_hunts.SETTING,)
    ).fetchone()
    if not policy or not policy["value"].get("enabled"):
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
        (policy["value"]["revision"], 3972),
    ).fetchone()
    if not row:
        raise ValueError("Missing Ruel trace definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, intents, objectives, completed = mission_progress.advance_objective(
        state,
        row["data"]["native"],
        8452,
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if not objectives:
        return []
    if not storage.record_event(
        db,
        character["id"],
        f"ruel-trace-fight:{event['fight_id']}",
        {"kind": "reconstructed_ruel_trace_victory_v1", "actor_id": actor_id},
    ):
        raise ValueError("Duplicate Ruel trace victory")
    for quest_id, reward in intents:
        rewards.validate(reward)
        storage.claim_reward(db, character["id"], quest_id, "once", reward["d"], reward)
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"], state, after, objectives, completed, now_ms
    ) + drain_rewards(db, store, character)
