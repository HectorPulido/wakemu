#!/usr/bin/env python3
"""Drive the native Rii Celestial Dojo path over a real local World TLS session.

One disposable local QA account per run. The fixture premise (a character that
already completed the Huly/Otomai/Kheperalia conversations) is written before
login; after login every step is a real native packet: teleporter, NPC
conversation, dialogue choice, lesson encounter and combat bootstrap.

Run with PYTHONPATH=server from the repository root against the local World:

  PYTHONPATH=server WAKFU_DATABASE_URL=... WAKFU_DATABASE_PASSWORD_FILE=... \
    python3 server/tools/dojo_official_path_probe.py
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import secrets
import socket
import ssl
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol_codec import DIRECTIONS  # noqa: E402
from tools import verify_clean_install as access  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402
from wakfu_server.combat_geometry import published_geometry  # noqa: E402
from wakfu_server.store import Store  # noqa: E402

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "agents_docs/reports/quest-reconstruction/dojo-official-contract-20261112.json"
)
AIRYNA = -1706442046308339
DOJO_PORTAL, DOJO_DESTINATION, DOJO_MAP, RII_MAP = 34607, 4561, 1388, 1385
PORTAL_APPROACH = (21, -22, 1)
QUEST_PACKETS = {
    13205: "ctx_activacion",
    13312: "ctq_mision_activa",
    13371: "ctu_seguimiento",
    13832: "ctv_objetivo",
    13422: "cts_mision_completada",
    13295: "ctA_contador",
}


class Session:
    """Minimal native client: framing, packet capture and walking paths."""

    def __init__(self, host, port, *, label):
        self.socket = ssl._create_unverified_context().wrap_socket(
            socket.create_connection((host, port), timeout=10),
            server_hostname="localhost",
        )
        self.socket.settimeout(6)
        self.log = []

    def send(self, opcode, body=b""):
        self.socket.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)

    def _read(self, size):
        out = bytearray()
        while len(out) < size:
            part = self.socket.recv(size - len(out))
            if not part:
                raise AssertionError("World closed the dojo probe socket")
            out.extend(part)
        return bytes(out)

    def pump(self, seconds=4.0):
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self.socket.settimeout(max(0.05, remaining))
            try:
                length = struct.unpack(">I", self._read(4))[0]
                payload = self._read(length - 4)
            except (TimeoutError, socket.timeout):
                return
            if not 6 <= length <= 327700:
                raise AssertionError("invalid native frame length %d" % length)
            opcode = struct.unpack(">H", payload[:2])[0]
            self.log.append(dict(opcode=opcode, body=payload[2:].hex()))

    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()


def decode_marker(body):
    from wakfu_server.achievements.rii_dojo_markers import decode

    return decode(body)


def rii_dojo_ready_event():
    from wakfu_server.achievements.rii_dojo_arrival import READY

    return READY


def transition_map(body):
    size = struct.unpack_from(">H", bytes.fromhex(body), 0)[0]
    block = bytes.fromhex(body)[2 : 2 + size]
    x, y, z, map_id = struct.unpack_from(">iihq", block, 18)
    return dict(map_id=map_id, cell=[x, y, z])


def quest_events(records):
    out = []
    for row in records:
        opcode, raw = row["opcode"], bytes.fromhex(row["body"])
        # Native layout is always an i64 owner identity first.
        if opcode in (13205, 13312, 13832, 13422):
            out.append(
                dict(
                    kind=QUEST_PACKETS[opcode],
                    owner=struct.unpack_from(">q", raw, 0)[0],
                    id=struct.unpack_from(">i", raw, 8)[0],
                )
            )
        elif opcode == 13371:
            out.append(
                dict(
                    kind=QUEST_PACKETS[opcode],
                    owner=struct.unpack_from(">q", raw, 0)[0],
                    id=struct.unpack_from(">i", raw, 8)[0],
                    tracked=bool(raw[12]),
                )
            )
        elif opcode == 13295:
            out.append(
                dict(
                    kind=QUEST_PACKETS[opcode],
                    owner=struct.unpack_from(">q", raw, 0)[0],
                    variable=struct.unpack_from(">i", raw, 8)[0],
                    value=struct.unpack_from(">q", raw, 12)[0],
                )
            )
    return out


def scenario_events(records):
    result = []
    for row in records:
        if row["opcode"] != 13411:
            continue
        raw = bytes.fromhex(row["body"])
        result.append(
            dict(
                event=struct.unpack_from(">i", raw, 1)[0],
                scenario=struct.unpack_from(">i", raw, 5)[0],
                arguments=[
                    struct.unpack_from(">q", raw, 10 + 8 * index)[0]
                    for index in range(raw[9])
                ],
            )
        )
    return result


def notifications(records):
    """Decoded GAME_INFORMATION texts: the server's own rejection reason."""
    out = []
    for row in records:
        if row["opcode"] != 349:
            continue
        raw = bytes.fromhex(row["body"])
        size = struct.unpack_from(">h", raw, 2)[0]
        out.append(raw[4 : 4 + size].decode("utf-8", "replace"))
    return out


def nodes(records):
    return [
        struct.unpack_from(">i", bytes.fromhex(row["body"]), 0)[0]
        for row in records
        if row["opcode"] in (12218, 12969)
    ]


def approach_cells(geometry, start, target, *, radius=3, max_depth=1):
    """Closest walkable cells around a world actor, reached from `start`."""
    goals = [
        cell
        for cell in geometry.cells
        if max(abs(cell[0] - target[0]), abs(cell[1] - target[1])) <= max_depth
        and abs(cell[2] - target[2]) <= 1
    ]
    if not goals:
        raise ValueError("no approach floor around %s" % (target,))
    if start in goals:
        return start, []
    queue, previous = deque([(start, [])]), {start: None}
    while queue:
        current, path = queue.popleft()
        if current in goals:
            return current, path
        for cell in geometry.outgoing.get(current, ()):
            if cell not in previous:
                previous[cell] = current
                queue.append((cell, path + [cell]))
    raise ValueError("no walking route from %s to %s" % (start, target))


def walk(session, geometry, start, path):
    if not path:
        return start
    directions = {(x, y): key for key, (_, x, y) in DIRECTIONS.items()}
    steps, current = bytearray(), start
    for cell in path:
        delta = (cell[0] - current[0], cell[1] - current[1])
        if delta not in directions:
            raise ValueError("non-adjacent native step %s -> %s" % (current, cell))
        vertical = cell[2] - current[2]
        if not -16 <= vertical <= 15:
            raise ValueError("altitude delta is not encodable")
        steps.append((directions[delta] << 5) | (vertical & 31))
        current = cell
    session.send(13331, struct.pack(">iiihB", 0, *start, len(steps)) + bytes(steps))
    return current


def prepare_fixture(store, receipt, http, *, repeat=False):
    """One disposable QA owner holding exactly the pre-dojo Rii journal state."""
    letters = lambda size: "".join(
        random.choice("abcdefghijklmnoprstuvwxyz") for _ in range(size)
    )
    username, credential = "dojoqa" + letters(8), secrets.token_urlsafe(16)
    account = http("/register", {"username": username, "password": credential})
    login = http("/login", {"username": username, "password": credential})
    character = http(
        "/characters", {"name": letters(9), "breed": 6}, login["api_token"]
    )
    with store.connection() as db:
        db.execute(
            "UPDATE characters SET map_id=%s, instance_id=0, x=%s, y=%s, z=%s "
            "WHERE id=%s",
            (RII_MAP, *PORTAL_APPROACH, character["id"]),
        )
        from wakfu_server.achievements import storage

        state = storage.load_locked(db, character["id"])
        running = [5154, 5160] if not repeat else [5143, 5160]
        objectives = [10595, 10596, 10607, 10612, 10613, 10615]
        if repeat:
            objectives = objectives + [10574, 10606, 10614]
        state.update(
            running=running,
            tracking=[5143, 5160] if repeat else [5160],
            objectives=objectives,
            completed=[] if not repeat else [5154],
        )
        storage.store(db, character["id"], state)
        # Dialogue criteria read the achievement authority projection, not only
        # the progress blob, so the fixture must keep both identical.
        db.execute(
            "INSERT INTO character_achievement_authority"
            "(character_id,snapshot,revision,provenance) VALUES (%s,%s,1,'dojo-probe-fixture') "
            "ON CONFLICT (character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot, "
            "revision=character_achievement_authority.revision+1",
            (
                character["id"],
                Jsonb(
                    {
                        "running": state["running"],
                        "completed": state["completed"],
                        "objectives": state["objectives"],
                    }
                ),
            ),
        )
        row = db.execute(
            "SELECT revision, definition_count FROM native_quest_metadata_releases "
            "ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
        airyna = db.execute(
            "SELECT reference_id, actor_id, x, y, z, interaction_range "
            "FROM world_dialogue_npcs WHERE map_id=%s AND actor_id=%s AND enabled",
            (DOJO_MAP, AIRYNA),
        ).fetchone()
        dojo_geometry = published_geometry(DOJO_MAP)
        dojo_floor = [
            cell
            for cell in getattr(dojo_geometry, "cells", ())
            if cell[2] == 3
            and abs(cell[0] - airyna["x"]) + abs(cell[1] - airyna["y"]) <= 2
        ]
    receipt["fixture"] = dict(
        account_id=account["id"],
        character_id=character["id"],
        name=character["name"],
        start_map=RII_MAP,
        start_cell=list(PORTAL_APPROACH),
        journal=dict(running=running, objectives=objectives),
        native_release=row,
        airyna=dict(airyna),
        dojo_floor_near_airyna=sorted(dojo_floor)[:6],
    )
    return login, character


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    parser.add_argument(
        "--receipt",
        default=".local-state/wakemu/qa/dojo-official-path-%s.json"
        % datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    parser.add_argument(
        "--lesson-cast",
        action="store_true",
        help="Reproduce the official distance-lesson casts on our server",
    )
    parser.add_argument(
        "--repeat-path",
        action="store_true",
        help="Skip straight to the native repeat entries of node 5787",
    )
    parser.add_argument(
        "--keep-account",
        action="store_true",
        help="Leave the disposable QA account in place after the run",
    )
    args = parser.parse_args()
    lesson_cast = args.lesson_cast
    repeat = args.repeat_path

    def http(path, payload, token=None):
        import urllib.error
        import urllib.request

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            args.http_url + path,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise AssertionError(
                "HTTP %s %s: %s"
                % (error.code, path, error.read().decode("utf-8", "replace"))
            ) from error

    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    receipt = dict(
        schema="wakemu.rii-dojo-live-path-probe-v2",
        started=datetime.now(timezone.utc).isoformat(),
        official_contract=(
            json.loads(CONTRACT_PATH.read_text())["dojo_entry"]
            if CONTRACT_PATH.exists()
            else None
        ),
        stages=[],
    )
    login, character = prepare_fixture(store, receipt, http, repeat=repeat)
    access.ACCESS.update(
        http_url=args.http_url,
        world_host=args.world_host,
        world_port=args.world_port,
        dispatcher_port=args.dispatcher_port,
    )
    return_path = False
    receipt["mode"] = "repeat" if repeat else "full"
    ticket, _ = access.dispatcher_ticket(login["game_token"])
    session = Session(args.world_host, args.world_port, label="dojo")
    verdict = {}
    try:
        session.send(426, access.text(ticket) + access.text("dojo-official-path-probe"))
        session.pump(3)
        session.send(
            23664, struct.pack(">q", character["id"]) + access.text(character["name"])
        )
        session.pump(8)
        session.send(12449)
        session.pump(2)
        session.send(14689)
        session.pump(4)
        session.log.clear()

        def stage(label, opcode, body, *, seconds=6.0):
            start = len(session.log)
            session.send(opcode, body)
            session.pump(seconds)
            records = session.log[start:]
            if os.environ.get("WAKFU_PROBE_DUMP_HERO_STATES") == "1":
                Path("/tmp/dojo_hero_states.json").write_text(
                    json.dumps(
                        [
                            row
                            for row in records
                            if row["opcode"] in (13912, 12873, 12613, 13497)
                        ]
                    )
                )
            entry = dict(
                label=label,
                request=dict(opcode=opcode, body=body.hex()),
                packets=[row["opcode"] for row in records],
                quest=quest_events(records),
                scenario=scenario_events(records),
                nodes=nodes(records),
                information=notifications(records),
                fight_bootstrap=any(row["opcode"] == 12847 for row in records),
                monster_spawn=sum(1 for row in records if row["opcode"] == 12608),
            )
            transition = [
                transition_map(row["body"]) for row in records if row["opcode"] == 13974
            ]
            if transition:
                entry["transition"] = transition[-1]
            bootstrap = [row for row in records if row["opcode"] == 12847]
            if bootstrap:
                from wakfu_server.combat.combat_protocol_reconstruction import (
                    decode_packet,
                )

                try:
                    decoded = decode_packet(12847, bytes.fromhex(bootstrap[0]["body"]))
                    entry["bootstrap"] = dict(
                        phase=decoded.get("phase"),
                        metadata=list(decoded["metadata"]),
                        actors=[
                            dict(
                                id=row["id"],
                                kind=row["kind"],
                                team=row["team"],
                                reference=(
                                    struct.unpack_from(
                                        ">h",
                                        row["descriptor"] or b"",
                                        len(row["descriptor"] or b"") - 27,
                                    )[0]
                                    if row["kind"] == 1
                                    else None
                                ),
                                cell=(
                                    list(
                                        struct.unpack_from(
                                            ">iih", row["descriptor"] or b"", 1
                                        )
                                    )
                                    if row["kind"] == 1
                                    else None
                                ),
                            )
                            for row in decoded.get("actors", ())
                        ],
                    )
                except (ValueError, struct.error) as error:
                    entry["bootstrap_error"] = str(error)
            spawns = [row for row in records if row["opcode"] == 12608]
            entry["spawn_bodies"] = [row["body"][:120] for row in spawns[:4]]
            markers = []
            for row in records:
                if row["opcode"] not in (13497, 13560):
                    continue
                try:
                    markers.append(decode_marker(bytes.fromhex(row["body"])))
                except Exception:
                    continue
            if markers:
                entry["dojo_markers"] = markers
            receipt["stages"].append(entry)
            print(
                "%-22s packets=%-3d quest=%s nodes=%s transition=%s events=%s spawn=%d bootstrap=%s info=%s"
                % (
                    label,
                    len(records),
                    [
                        (row["kind"], row.get("id", row.get("variable")))
                        for row in entry["quest"]
                    ][:8],
                    entry["nodes"],
                    entry.get("transition", {}).get("map_id"),
                    [row["event"] for row in entry["scenario"]],
                    entry["monster_spawn"],
                    entry["fight_bootstrap"],
                    entry["information"],
                )
            )
            return entry

        # 1. Native Celestial Dojo entrance, exactly as the official client asks.
        entry = stage(
            "dojo_portal",
            12296,
            struct.pack(">qiBi", DOJO_PORTAL, DOJO_DESTINATION, 0, 2),
            seconds=8,
        )
        verdict["dojo_entry_map"] = entry.get("transition", {}).get("map_id")

        # 1b. The installed dojo script reports its ready event back.
        entry = stage(
            "dojo_ready_callback", 12921, struct.pack(">i", rii_dojo_ready_event())
        )
        verdict["carrier_after_ready"] = [
            (row["kind"], row.get("id")) for row in entry["quest"]
        ]

        # 2. Walk to Airyna on the dojo floor.
        airyna = receipt["fixture"]["airyna"]
        after = entry.get("transition", {}).get("cell") or [0, 0, 0]
        geometry = published_geometry(DOJO_MAP)
        # The reviewer-approved reachable approach wins over the actor platform
        # whenever the native NPC stands on an unreachable height.
        from wakfu_server.npc_interaction_anchors import interaction_anchor

        anchor = interaction_anchor(dict(airyna, map_id=DOJO_MAP, instance_id=0))
        goal = (
            (anchor["x"], anchor["y"], anchor["z"])
            if anchor is not None
            else (airyna["x"], airyna["y"], airyna["z"])
        )
        cell, path = approach_cells(geometry, tuple(after), goal, max_depth=0)
        if path:
            walk(session, geometry, tuple(after), path)
            session.pump(3)
        receipt["dojo_approach"] = dict(
            from_cell=after, goal=list(goal), cell=list(cell), steps=len(path)
        )
        session.pump(3)
        session.log.clear()

        # 3. Airyna's curriculum conversation (native action 1390, root 5755).
        entry = stage(
            "airyna_curriculum_open",
            13222,
            struct.pack(">qq", AIRYNA, 1390),
            seconds=6,
        )
        verdict["curriculum_node"] = (entry["nodes"] or [None])[0]

        # 4. Accept the curriculum: official effects 10614 + 10606 + 5154 + 5143.
        entry = stage(
            "accept_curriculum",
            12058,
            struct.pack(">ii", 5755, 13258),
            seconds=8,
        )
        verdict["after_accept"] = [
            (row["kind"], row.get("id")) for row in entry["quest"]
        ]

        # 5. Ask for the first lesson: guide event, sack spawn, fight bootstrap.
        if lesson_cast:
            # The cast mode owns its own lesson; an open orientation fight
            # would keep Airyna's dialogue unavailable.
            pass
        else:
            entry = stage(
                "first_lesson",
                12058,
                struct.pack(">ii", 5756, 13260),
                seconds=10,
            )
            verdict["first_lesson"] = dict(
                scenario=[row["event"] for row in entry["scenario"]],
                monster_spawn=entry["monster_spawn"],
                fight_bootstrap=entry["fight_bootstrap"],
            )

        if lesson_cast:
            # Reproduce the official distance-lesson casts against our own
            # server: choose lesson three, become ready, step to the captured
            # cells and cast spell 7967 at the sack cell.
            # The QA character starts with the orientation lesson unlocked; the
            # readiness packet is what drives the real fight initialization where
            # the captured lesson carriers are applied.
            entry = stage(
                "choose_orientation",
                12058,
                struct.pack(">ii", 5756, 13260),
                seconds=10,
            )
            hero = (entry.get("bootstrap") or {}).get("actors", [{}])[0].get("id")
            sack = next(
                (
                    row
                    for row in (entry.get("bootstrap") or {}).get("actors", [])
                    if row.get("reference") == 5466
                ),
                None,
            )
            if hero is None or sack is None:
                verdict["lesson_cast"] = "missing lesson actors"
                return
            ready_entry = stage("ready", 12523, bytes([1]), seconds=8)
            verdict["after_ready"] = {
                "packets": ready_entry["packets"],
                "presentation": sum(
                    1
                    for row in ready_entry["packets"]
                    if row in (13497, 12613, 12238, 13560)
                ),
            }
            return
            cell = tuple(sack["cell"])
            for index, offset in enumerate((2, 3, 2, 3), 2):
                stage(
                    f"step_{offset}",
                    12161,
                    struct.pack(">q", hero)
                    + struct.pack(">iih", cell[0] + offset, cell[1], 0),
                    seconds=5,
                )
                stage(
                    f"cast_{offset}",
                    13260,
                    struct.pack(
                        ">qqiih",
                        hero,
                        7967,
                        cell[0],
                        cell[1],
                        cell[2] if len(cell) > 2 else 0,
                    ),
                    seconds=6,
                )
            return

        if return_path:
            return
        if repeat:
            # Stand where the official session stood, then ask for the menu and
            # for the native "already done" entry of lesson 1.
            stage(
                "menu_open_in_dojo", 13222, struct.pack(">qq", AIRYNA, 1389), seconds=8
            )
            stage(
                "repeat_orientation_13330",
                12058,
                struct.pack(">ii", 5787, 13330),
                seconds=10,
            )
            return
        # 6. Airyna's lesson menu after the curriculum quest is running.
        stage("menu_open", 13222, struct.pack(">qq", AIRYNA, 1389), seconds=6)
        stage("menu_elements", 12058, struct.pack(">ii", 5787, 13323), seconds=10)
        verdict["menu_elements"] = dict(
            scenario=[row["event"] for row in receipt["stages"][-1]["scenario"]],
            monster_spawn=receipt["stages"][-1]["monster_spawn"],
            fight_bootstrap=receipt["stages"][-1]["fight_bootstrap"],
            information=receipt["stages"][-1]["information"],
        )
    finally:
        session.close()
        receipt["verdict"] = verdict
        receipt["finished"] = datetime.now(timezone.utc).isoformat()
        Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(verdict, indent=2))
        print("receipt:", args.receipt)


if __name__ == "__main__":
    main()
