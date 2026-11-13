"""Reconstructed interrogation using native suspect actors and dialogue text."""
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

SUSPECTS = {
    -2251799934994693: (
        4693,
        971,
        (-25, 3, 0),
        4155,
        {
            (4155, 10359): 4156,
            (4156, 10362): 4158,
            (4158, 10363): 4159,
            (4159, 10364): 4160,
            (4160, 10365): 0,
        },
    ),
    -2251799934994695: (
        4695,
        972,
        (-24, 5, 0),
        4162,
        {
            (4162, 10381): 4164,
            (4164, 10380): 4165,
            (4165, 10394): 4169,
            (4169, 10391): 4170,
            (4170, 10392): 4171,
            (4171, 10393): 0,
        },
    ),
    -2251799934994694: (
        4694,
        973,
        (-20, 4, 0),
        4173,
        {
            (4173, 10401): 4174,
            (4174, 10431): 4180,
            (4180, 10419): 4181,
            (4181, 10420): 4182,
            (4182, 10421): 0,
        },
    ),
}


def placement(actor):
    ref, action, position, root, _ = SUSPECTS[actor]
    return dict(
        actor_id=actor,
        reference_id=ref,
        map_id=527,
        instance_id=0,
        x=position[0],
        y=position[1],
        z=position[2],
        direction=1,
        interaction_range=4,
        dialogue_root=root,
        action_ids=[action],
        native_capture_id=None,
    )


def scene_packets(db, character):
    if character["map_id"] != 527 or character.get("instance_id", 0) != 0:
        return []
    from wakfu_server.ruel_hunt_npc import _enabled

    if not _enabled(db):
        return []
    state = storage.load_locked(db, character["id"])
    if 3973 not in state["running"]:
        return []
    return [
        npc_world.spawn(placement(actor), enabled_actions=(data[1],))
        for actor, data in SUSPECTS.items()
    ]


def recognizes(opcode, body, session):
    if opcode == 12058:
        return session is not None and getattr(session, "ruel_investigation", False)
    if opcode == 13222 and len(body) == 16:
        actor, action = struct.unpack(">qq", body)
        return actor in SUSPECTS and SUSPECTS[actor][1] == action
    if opcode == 12535 and len(body) == 13:
        _, kind, actor = struct.unpack(">ibq", body)
        return kind == 2 and actor in SUSPECTS
    return False


def begin(store, account_id, generation, character, actor, *, character_provider):
    if actor not in SUSPECTS:
        raise ValueError("Unknown investigation suspect")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        current = store.character(account_id, character["id"], db)
        _owner(db, current)
        state = storage.load_locked(db, current["id"])
        if 3973 not in state["running"] or not npc_world.nearby(
            current, placement(actor)
        ):
            raise ValueError("Suspect is unavailable")
    _, _, _, root, graph = SUSPECTS[actor]
    nodes = (
        {root} | {node for node, _ in graph} | {node for node in graph.values() if node}
    )
    owner = current["id"], account_id

    def speaker(candidate, node):
        value = character_provider()
        return (
            (value["id"], value["account_id"]) == owner
            and candidate == actor
            and node in nodes
            and npc_world.nearby(value, placement(actor))
        )

    session = npc_dialogue.DialogueSession(
        npc_dialogue.catalog()["node_index"],
        graph,
        authorize_node=lambda node: node["id"] in nodes,
        authorize_choice=lambda item: (session.node_id, item["id"]) in graph,
    )
    packet = session.open(root, actor, speaker)
    session.ruel_investigation = True
    return session, [packet]


def choose(store, account_id, generation, character, session, body):
    request = npc_dialogue.decode_request(12058, body)
    actor = session.speaker_id
    previous = session.node_id, session.speaker_id, session.authorize_speaker
    try:
        with store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
            store.lock_character(
                db, account_id, generation, character["id"], selected=True
            )
            current = store.character(account_id, character["id"], db)
            _owner(db, current)
            state = storage.load_locked(db, current["id"])
            if (
                actor not in SUSPECTS
                or 3973 not in state["running"]
                or not npc_world.nearby(current, placement(actor))
            ):
                raise ValueError("Suspect is unavailable")
            packet = session.choose(**request)
            packets = []
            if SUSPECTS[actor][4].get((request["node_id"], request["choice_id"])) == 0:
                key = f"ruel-investigation:{SUSPECTS[actor][0]}"
                fact = {
                    "kind": "reconstructed_ruel_interview_v1",
                    "reference": SUSPECTS[actor][0],
                }
                storage.record_event(db, current["id"], key, fact)
                rows = db.execute(
                    "SELECT event_key FROM character_achievement_events WHERE character_id=%s AND event_key = ANY(%s)",
                    (
                        current["id"],
                        [f"ruel-investigation:{v[0]}" for v in SUSPECTS.values()],
                    ),
                ).fetchall()
                if len(rows) == 3:
                    policy = db.execute(
                        "SELECT value FROM settings WHERE name=%s",
                        (ruel_hunts.SETTING,),
                    ).fetchone()
                    row = db.execute(
                        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
                        (policy["value"]["revision"], 3973),
                    ).fetchone()
                    if not row:
                        raise ValueError("Missing Ruel investigation definition")
                    now_ms = int(store.now().timestamp() * 1000)
                    (
                        after,
                        intents,
                        added,
                        completed,
                    ) = mission_progress.advance_objective(
                        state,
                        row["data"]["native"],
                        8458,
                        character=current,
                        store=store,
                        now_ms=now_ms,
                    )
                    for quest_id, reward in intents:
                        rewards.validate(reward)
                        storage.claim_reward(
                            db, current["id"], quest_id, "once", reward["d"], reward
                        )
                    storage.store(db, current["id"], after)
                    packets.extend(
                        wire.changes(
                            current["id"], state, after, added, completed, now_ms
                        )
                    )
                    packets.extend(drain_rewards(db, store, current))
                    if completed:
                        packets.extend(
                            (12304, b"\x00\x00\x01" + struct.pack(">Bq", 1, suspect))
                            for suspect in SUSPECTS
                        )
            if packet is not None:
                packets.append(packet)
            return {"packets": packets}
    except BaseException:
        session.node_id, session.speaker_id, session.authorize_speaker = previous
        raise
