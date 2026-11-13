"""Reconstructed Ruel hunt offers at the Astrub courthouse.

Native node/choice identities and level gates are retained. Placement and the
transition to the offer node are local reconstructions, never original captures.
"""
from copy import deepcopy
import struct
from wakfu_server import npc_dialogue, npc_world
from wakfu_server.achievements import (
    mission_progress,
    rewards,
    ruel_hunts,
    storage,
    wire,
)
from wakfu_server.achievements.service import _owner, drain_rewards

ACTOR = -2251799934994573
REFERENCE = 4573
ACTION = 930
MAP = 527
POSITION = (-22, 2, 0)


def _enabled(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name=%s", (ruel_hunts.SETTING,)
    ).fetchone()
    return bool(
        row
        and isinstance(row["value"], dict)
        and row["value"].get("enabled") is True
        and row["value"].get("schema") == ruel_hunts.SETTING
    )


def placement():
    # The actual NPC position is unknown; this is a walkable cell beside the
    # native Astrub courthouse entrance, not a recovered actor placement.
    return {
        "actor_id": ACTOR,
        "reference_id": REFERENCE,
        "map_id": MAP,
        "instance_id": 0,
        "x": POSITION[0],
        "y": POSITION[1],
        "z": POSITION[2],
        "direction": 1,
        "interaction_range": 4,
        "dialogue_root": 4147,
        "action_ids": [ACTION],
        "native_capture_id": None,
    }


def scene_packet(db, character):
    if (character["map_id"], character.get("instance_id", 0)) != (
        MAP,
        0,
    ) or not _enabled(db):
        return None
    return npc_world.spawn(placement(), enabled_actions=(ACTION,))


def recognizes(store, opcode, body, session):
    if opcode == 12058 and session is not None and getattr(session, "ruel_hunt", False):
        return True
    if opcode == 13222:
        match = len(body) == 16 and struct.unpack(">qq", body) == (ACTOR, ACTION)
    elif opcode == 12535:
        match = len(body) == 13 and struct.unpack(">ibq", body)[1:] == (2, ACTOR)
    else:
        return False
    if not match:
        return False
    with store.connection() as db:
        return _enabled(db)


def begin(
    store, account_id, generation, character, actor_id, action_id, *, character_provider
):
    if (actor_id, action_id) != (ACTOR, ACTION):
        raise ValueError("Unknown Ruel action")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        if not _enabled(db) or not npc_world.nearby(current, placement()):
            raise ValueError("Ruel está fuera de alcance")
        state = storage.load_locked(db, current["id"])
        now_ms = int(store.now().timestamp() * 1000)
        choice, candidates = ruel_hunts.available(
            state, ruel_hunts.load_catalog(), level=current["level"], now_ms=now_ms
        )
    if 3974 in state["completed"]:
        root = 4146 if choice is not None and candidates else 4141
        graph = (
            {(root, choice): 4147, (4147, 10347): 0, (4146, 10450): 0}
            if root == 4146
            else {(4141, 10341): 0}
        )
    elif 3973 in state["completed"]:
        root, graph = 4144, {(4144, 10344): 0}
    elif 3973 in state["running"]:
        root, graph = 4195, {(4195, 10463): 0}
    elif 3971 in state["running"] or 3972 in state["running"]:
        root = 4150
        graph = {(4150, 10446): 0}
        graph[(4150, 10351 if 3971 in state["running"] else 10443)] = 0
    elif current["level"] >= 15 and 3971 not in state["completed"]:
        root, graph = 4142, {(4142, 10342): 4143, (4143, 10343): 4150, (4150, 10351): 0}
    else:
        root, graph = 4141, {(4141, 10341): 0}
    allowed_nodes = (
        {root} | {node for node, _ in graph} | {node for node in graph.values() if node}
    )
    owner = (current["id"], account_id)

    def speaker(actor, node):
        value = character_provider()
        return (
            (value["id"], value["account_id"]) == owner
            and actor == ACTOR
            and node in allowed_nodes
            and npc_world.nearby(value, placement())
        )

    session = npc_dialogue.DialogueSession(
        npc_dialogue.catalog()["node_index"],
        graph,
        authorize_node=lambda node: node["id"] in allowed_nodes,
        authorize_choice=lambda item: (session.node_id, item["id"]) in graph,
    )
    packet = session.open(root, ACTOR, speaker)
    session.ruel_hunt = True
    session.ruel_offered_choice = choice
    return session, [packet]


def choose(store, account_id, generation, character, session, body):
    request = npc_dialogue.decode_request(12058, body)
    prior = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            _owner(db, current)
            if not _enabled(db) or not npc_world.nearby(current, placement()):
                raise ValueError("Ruel está fuera de alcance")
            packet = session.choose(**request)
            packets = []
            edge = request["node_id"], request["choice_id"]
            if edge in ((4143, 10343), (4150, 10351), (4144, 10344)):
                before = storage.load_locked(db, current["id"])
                after = deepcopy(before)
                now_ms = int(store.now().timestamp() * 1000)
                added, completed, intents = [], [], []
                if edge == (4143, 10343):
                    if (
                        current["level"] < 15
                        or 3971 in after["running"]
                        or 3971 in after["completed"]
                    ):
                        raise ValueError("Ruel introduction is unavailable")
                    after["running"].append(3971)
                    after["running"].sort()
                    mission_progress.auto_track(after, 3971)
                else:
                    quest, objective = (
                        (3971, 8451) if edge == (4150, 10351) else (3974, 8459)
                    )
                    if quest == 3974:
                        if 3973 not in after["completed"] or 3974 in after["completed"]:
                            raise ValueError("Ruel reward is unavailable")
                        if 3974 not in after["running"]:
                            after["running"].append(3974)
                            after["running"].sort()
                    policy = db.execute(
                        "SELECT value FROM settings WHERE name=%s",
                        (ruel_hunts.SETTING,),
                    ).fetchone()["value"]
                    row = db.execute(
                        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
                        (policy["revision"], quest),
                    ).fetchone()
                    if row is None:
                        raise ValueError("Missing Ruel story definition")
                    (
                        after,
                        intents,
                        added,
                        completed,
                    ) = mission_progress.advance_objective(
                        after,
                        row["data"]["native"],
                        objective,
                        character=current,
                        store=store,
                        now_ms=now_ms,
                    )
                    if (
                        quest == 3971
                        and completed
                        and 3972 not in after["running"]
                        and 3972 not in after["completed"]
                    ):
                        after["running"].append(3972)
                        after["running"].sort()
                        mission_progress.auto_track(after, 3972)
                fact = {
                    "kind": "reconstructed_ruel_story_dialogue_v1",
                    "node": edge[0],
                    "choice": edge[1],
                }
                if not storage.record_event(
                    db, current["id"], f"ruel-story:{edge[0]}:{edge[1]}", fact
                ):
                    raise ValueError("Ruel story receipt already exists")
                for identity, reward in intents:
                    rewards.validate(reward)
                    storage.claim_reward(
                        db, current["id"], identity, "once", reward["d"], reward
                    )
                storage.store(db, current["id"], after)
                packets.extend(
                    wire.changes(current["id"], before, after, added, completed, now_ms)
                )
                packets.extend(drain_rewards(db, store, current))
            if (request["node_id"], request["choice_id"]) == (4147, 10347):
                before = storage.load_locked(db, current["id"])
                now_ms = int(store.now().timestamp() * 1000)
                after, hunt = ruel_hunts.assign(
                    before,
                    ruel_hunts.load_catalog(),
                    character_id=current["id"],
                    level=current["level"],
                    offered_choice=session.ruel_offered_choice,
                    now_ms=now_ms,
                )
                fact = {
                    "kind": "reconstructed_ruel_assignment_v1",
                    "quest_id": hunt["quest_id"],
                    "objective_id": hunt["objective_id"],
                    "target_id": hunt["target_id"],
                    "day": now_ms // 86400000,
                }
                if not storage.record_event(
                    db, current["id"], f"ruel-assign:{hunt['quest_id']}", fact
                ):
                    raise ValueError("Ruel assignment receipt already exists")
                storage.store(db, current["id"], after)
                packets.extend(
                    wire.changes(current["id"], before, after, [], [], now_ms)
                )
            if packet is not None:
                packets.append(packet)
            return {"packets": packets}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = prior
        raise
