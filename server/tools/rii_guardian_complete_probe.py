"""Local TLS guardian acceptance through native defeat, scene callback and Zaap.

Only arrival prerequisites are fixtures. Movement, entrance, dialogue, fight,
ending callback and departure use normal protocol requests after login.
Private receipts contain packet evidence, not client animation verification.
"""

import json
import os
from pathlib import Path
import secrets
import struct
import time
from collections import deque
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from tools.rii_lessons_complete_probe import Run, ObservedPeer
from tools.candidate_friendly_duel_socket_smoke import placement, text
from wakfu_server.achievements import storage
from wakfu_server.combat_terrain import published_geometry
from protocol_codec import DIRECTIONS
from wakfu_server.progression import level_xp
from wakfu_server.store import Store


def login(store, peer, account, character, label):
    generation = store.begin_session(account["id"])
    ticket = store.issue_token(
        account["id"], "ticket", generation=generation, realm_id=10
    )
    peer.send(426, text(ticket) + text("guardian-" + label))
    peer.wait(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
    peer.wait(630)
    peer.wait(711)
    peer.send(12449)
    peer.wait(12436)
    peer.wait(711)
    # The final scene ACK is a request, not a request for another711. Ordered
    # following gameplay requests are processed after this load acknowledgment.
    peer.send(12449)
    return generation


def wait_packet(peer, opcode, start, predicate=lambda body: True, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with peer.observation_lock:
            rows = list(peer.records[start:])
        for received, body in rows:
            if received in (349, 674):
                raise AssertionError(
                    ("Native action rejected", body.decode("utf-8", errors="replace"))
                )
            if received == opcode and predicate(body):
                return body
        time.sleep(0.05)
    raise AssertionError(
        ("Missing native packet", opcode, [op for op, _ in rows[-25:]])
    )


def walk(peer, map_id, start, goal):
    if start == goal:
        return
    graph = published_geometry(map_id).outgoing
    previous, queue = {start: None}, deque([start])
    while queue and goal not in previous:
        source = queue.popleft()
        for destination in graph.get(source, ()):
            if destination not in previous:
                previous[destination] = source
                queue.append(destination)
    assert goal in previous, ("No native walking route", map_id, start, goal)
    path, point = [], goal
    while point != start:
        path.append(point)
        point = previous[point]
    path.reverse()
    assert len(path) <= 255, len(path)
    directions = {(dx, dy): identity for identity, (_, dx, dy) in DIRECTIONS.items()}
    encoded, previous_cell = bytearray(), start
    for cell in path:
        dz = cell[2] - previous_cell[2]
        assert -16 <= dz <= 15
        encoded.append(
            (directions[(cell[0] - previous_cell[0], cell[1] - previous_cell[1])] << 5)
            | (dz & 31)
        )
        previous_cell = cell
    peer.send(13331, struct.pack(">iiihB", 0, *start, len(path)) + encoded)
    # The owning client receives no path echo. Allow its legitimate movement
    # duration before requesting a nearby interaction; no server timer is added.
    time.sleep(min(15, 0.18 * len(path) + 0.2))


def npc_descriptors(peer, start, reference):
    with peer.observation_lock:
        packets = list(peer.records[start:])
    found = []
    for opcode, body in packets:
        if opcode != 12608:
            continue
        offset = 2
        for _ in range(body[1]):
            kind, identity, size = struct.unpack_from(">BqH", body, offset)
            offset += 11
            blob = body[offset : offset + size]
            offset += size
            if kind != 1 or not blob or blob[0] != 11 or len(blob) < 22:
                continue
            breed_offset = 20 + struct.unpack_from(">H", blob, 18)[0]
            if struct.unpack_from(">h", blob, breed_offset)[0] == reference:
                found.append(identity)
    return found


def main():
    dsn = os.environ["WAKFU_DATABASE_URL"]
    assert conninfo_to_dict(dsn).get("host") in ("127.0.0.1", "localhost")
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    resume = os.environ.get("WAKFU_RII_GUARDIAN_RESUME")
    if resume:
        receipt = json.loads(Path(resume).read_text())
        account = {"id": receipt["account_id"]}
        char = store.character(account["id"], receipt["character_id"])
        assert char["name"].startswith("Rii Guardian ")
        suffix = char["name"][13:]
        receipt.pop("error", None)
        if "wire" in receipt:
            receipt.setdefault("previous_wire_runs", []).append(receipt.pop("wire"))
    else:
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        account = store.register("rii_guardian_" + suffix, secrets.token_urlsafe(24))
        char = store.create_character(account["id"], "Rii Guardian " + suffix, breed=19)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1385,instance_id=0,x=-19,y=25,z=5,level=6 WHERE id=%s",
                (char["id"],),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(6), char["id"]),
            )
            state = storage.load_locked(db, char["id"])
            state.update(
                running=[5146, 5160],
                tracking=[5146, 5160],
                completed=[5143, 5145, 5154, 5155, 5156],
                objectives=[
                    10595,
                    10596,
                    10606,
                    10607,
                    10612,
                    10613,
                    10614,
                    10615,
                    10616,
                    10617,
                    10618,
                    10619,
                ],
            )
            storage.store(db, char["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) VALUES(%s,%s,1,'rii-guardian-arrival-fixture') ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=character_achievement_authority.revision+1",
                (
                    char["id"],
                    Jsonb(
                        {
                            key: state[key]
                            for key in ("running", "completed", "objectives")
                        }
                    ),
                ),
            )
        receipt = {"account_id": account["id"], "character_id": char["id"]}
    peer = ObservedPeer()
    try:
        generation = login(store, peer, account, char, "rii-guardian")
        current = store.character(account["id"], char["id"])
        start = len(peer.records) if current["map_id"] == 1385 else 0
        if current["map_id"] == 1385:
            peer.send(12296, struct.pack(">qiBi", 34619, 4560, 0, 2))
            wait_packet(peer, 13974, start)
            peer.send(12449)
        else:
            assert current["map_id"] == 1387, current["map_id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not npc_descriptors(peer, start, 5458):
            time.sleep(0.1)
        npcs = npc_descriptors(peer, start, 5458)
        assert npcs, "Sanctuary did not publish native Grougaloragran"
        with store.connection() as db:
            state = storage.load_locked(db, char["id"])
        assert 10582 in state["objectives"], state
        receipt["sanctuary_entrance_verified"] = True
        print("SANCTUARY_ENTRY", char["id"], flush=True)
        current = store.character(account["id"], char["id"])
        walk(peer, 1387, tuple(current[key] for key in ("x", "y", "z")), (-10, 0, 2))
        before = len(peer.records)
        peer.send(13222, struct.pack(">qq", npcs[-1], 1238))
        body = wait_packet(peer, 12969, before)
        assert struct.unpack_from(">i", body)[0] == 5764, body.hex()
        for node, choice, next_node in ((5764, 13343, 5790), (5790, 13345, 5791)):
            before = len(peer.records)
            peer.send(12058, struct.pack(">ii", node, choice))
            body = wait_packet(peer, 12218, before)
            assert struct.unpack_from(">i", body)[0] == next_node, body.hex()
        before = len(peer.records)
        peer.send(12058, struct.pack(">ii", 5791, 13347))
        body = wait_packet(peer, 13652, before, timeout=45)
        fight_id, actors = placement(body)
        targets = [identity for identity in actors if identity != char["id"]]
        assert (
            len(targets) == 1
            and actors[char["id"]] == (-8, 0, 0)
            and actors[targets[0]] == (-16, 0, 0)
        ), actors
        wait_packet(peer, 12847, before)
        receipt.update(
            fight_id=fight_id,
            target_id=targets[0],
            native_positions={str(k): v for k, v in actors.items()},
        )
        print("NATIVE_GUARDIAN_ADMITTED", char["id"], fight_id, flush=True)
        run = Run(store, account, char, {"lessons": []})
        run.peer = peer
        run.fight_id = fight_id
        run.targets = targets
        assert (
            run.poll(
                lambda value: True, timeout=10, label="guardian placement checkpoint"
            ).get("native_fight_model")
            == 71
        ), "Placement rebuild lost native guardian model"
        turn_cursor = len(peer.records)
        peer.send(12523, b"\x01")
        next_ack, acked, hero_turns = 1, set(), 0
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with peer.observation_lock:
                messages = list(peer.records[turn_cursor:])
                turn_cursor = len(peer.records)
            for opcode, payload in messages:
                if opcode in (349, 674):
                    raise AssertionError(
                        ("Native combat input rejected", opcode, payload.hex())
                    )
                if (
                    len(payload) < 20
                    or struct.unpack_from(">i", payload)[0] != fight_id
                ):
                    continue
                if opcode == 12502:
                    # cvW ends one native global activation. Mirror the client
                    # acknowledgement from live wire, never a stale SQL ACK.
                    assert next_ack not in acked
                    peer.send(13510, struct.pack(">i", next_ack))
                    acked.add(next_ack)
                    next_ack += 1
                elif (
                    opcode == 13482
                    and struct.unpack_from(">q", payload, 12)[0] == char["id"]
                ):
                    hero_turns += 1
                    print("NATIVE_PLAYER_TURN", hero_turns, flush=True)
                    peer.send(
                        12403,
                        struct.pack(
                            ">qh",
                            char["id"],
                            run.checkpoint().get("native_timeline_round", 1),
                        ),
                    )
            snap = run.checkpoint()
            if snap and snap["phase"] == "finished":
                break
            time.sleep(0.05)
        receipt["native_turn_acknowledgements"] = sorted(acked)
        receipt["native_player_turns"] = hero_turns
        snap = run.poll(
            lambda value: value["phase"] == "finished",
            timeout=30,
            label="guardian native defeat",
        )
        assert snap["winner"] == 0 and snap["actors"][str(char["id"])]["hp"] == 0, snap
        receipt["native_table_turn"] = snap.get(
            "native_table_turn", snap.get("native_timeline_round")
        )
        print(
            "NATIVE_GUARDIAN_DEFEAT", fight_id, receipt["native_table_turn"], flush=True
        )
        wait_packet(peer, 12755, before)
        with store.connection() as db:
            state = storage.load_locked(db, char["id"])
        assert (
            10584 not in state["objectives"]
        ), "Guardian completed before its ending callback"
        returned = len(peer.records)
        peer.send(12925, struct.pack(">iB", fight_id, 1))
        event = wait_packet(
            peer,
            13411,
            returned,
            lambda body: len(body) >= 10
            and struct.unpack_from(">i", body, 1)[0] == 22532,
        )
        assert struct.unpack(">BiiB", event) == (0, 22532, 2548, 0)
        callback = len(peer.records)
        peer.send(12921, struct.pack(">i", 2))
        peer.send(12921, struct.pack(">i", 22532))
        wait_packet(peer, 13974, callback)
        peer.send(12449)
        current = store.character(account["id"], char["id"])
        assert (current["map_id"], current["x"], current["y"], current["z"]) == (
            1385,
            -19,
            25,
            5,
        ), current
        with store.connection() as db:
            state = storage.load_locked(db, char["id"])
            reward = db.execute(
                "SELECT xp,kamas FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight_id, char["id"]),
            ).fetchone()
        assert (
            5146 in state["completed"]
            and 10622 in state["objectives"]
            and 5161 in state["running"]
        ), state
        assert reward is None or reward["xp"] == reward["kamas"] == 0, reward
        receipt.update(
            guardian_completed=True, combat_reward=reward, native_fight_model=71
        )
        from wakfu_server import native_transports

        zaap = native_transports.OBJECTS[34644]
        walk(
            peer,
            1385,
            (-19, 25, 5),
            (
                int(zaap["arrival_x"]),
                int(zaap["arrival_y"]),
                int(zaap["arrival_heights"][0]),
            ),
        )
        opened = len(peer.records)
        peer.send(12870, struct.pack(">qi", 34644, 0))
        # Native Zaap activation opens the local client menu; it does not
        # promise a13530 response (that opcode corrects world movement).
        departure = len(peer.records)
        peer.send(13686, struct.pack(">qq", 34644, 19249))
        wait_packet(peer, 13974, departure)
        with store.connection() as db:
            state = storage.load_locked(db, char["id"])
        assert 5161 in state["completed"] and 10624 in state["objectives"], state
        receipt.update(
            success=True,
            progress=state,
            combat_reward=reward,
            final_map=store.character(account["id"], char["id"])["map_id"],
        )
        print(
            "PASS",
            {k: receipt[k] for k in ("character_id", "fight_id", "final_map")},
            flush=True,
        )
    except Exception as error:
        receipt["error"] = repr(error)
        raise
    finally:
        receipt["wire"] = [(opcode, body.hex()) for opcode, body in peer.records]
        peer.close()
        output = Path(
            os.environ.get(
                "WAKFU_RII_GUARDIAN_RECEIPT",
                ".local-state/wakemu/qa/rii-guardian-" + suffix + ".json",
            )
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2, default=str))
        print("RECEIPT", output, flush=True)


if __name__ == "__main__":
    main()
