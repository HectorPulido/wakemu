"""Two-peer TLS regression for ordered shared-combat push delivery.

Run inside a disposable candidate world container. Both accounts and the
candidate PostgreSQL database are created by this script; it never contacts
the live world.
"""
import os
import queue
import secrets
import socket
import ssl
import struct
import threading
import time
import json
from collections import deque
from functools import lru_cache
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.store import Store
from tls_smoke_io import recv_exact, send_all
from candidate_session_lease import start as start_test_session_heartbeat
from candidate_session_lease import stop_all as stop_test_session_heartbeats


def text(value):
    raw = value.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        port = int(os.environ.get("WAKFU_CANDIDATE_PORT", "15556"))
        error = None
        for _ in range(20):
            raw = socket.create_connection(("127.0.0.1", port), timeout=15)
            try:
                self.socket = ssl._create_unverified_context().wrap_socket(
                    raw, server_hostname="localhost"
                )
                break
            except (OSError, ssl.SSLError) as exc:
                error = exc
                raw.close()
                time.sleep(0.25)
        else:
            raise AssertionError(f"TLS listener did not accept a reconnect: {error}")
        # Frequent reader timeouts let serialized foreground TLS writes get
        # the socket lock promptly during long native combat actions.
        self.socket.settimeout(0.1)
        self.io_lock = threading.Lock()
        self.events = queue.Queue()
        self.pending = []
        self.sent_opcodes = []
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def send(self, opcode, body=b""):
        self.sent_opcodes.append(opcode)
        send_all(self.socket, frame(opcode, body), io_lock=self.io_lock)

    def _exact(self, size):
        return recv_exact(self.socket, size, closed=self.closed, io_lock=self.io_lock)

    def _read(self):
        try:
            while not self.closed.is_set():
                try:
                    size = struct.unpack(">I", self._exact(4))[0]
                    if not 6 <= size <= 327670:
                        raise AssertionError(f"invalid server frame size {size}")
                    payload = self._exact(size - 4)
                    self.events.put((struct.unpack_from(">H", payload)[0], payload[2:]))
                except socket.timeout:
                    continue
        except Exception as error:
            if not self.closed.is_set():
                self.events.put((None, error))

    def wait(self, opcode, timeout=45):
        deadline = time.monotonic() + timeout
        seen = []
        for index, packet in enumerate(self.pending):
            if packet[0] == opcode:
                del self.pending[index]
                return packet[1], [packet]
        while time.monotonic() < deadline:
            try:
                packet = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if packet[0] is None:
                raise AssertionError(
                    f"TLS peer failed while waiting for {opcode}: {packet[1]}"
                )
            seen.append(packet)
            if packet[0] == opcode:
                return packet[1], seen
            self.pending.append(packet)
        raise AssertionError(
            f"timeout waiting opcode {opcode}; received {[op for op, _ in seen]}"
        )

    def wait_any(self, opcodes, timeout=45):
        deadline = time.monotonic() + timeout
        seen = []
        for index, packet in enumerate(self.pending):
            if packet[0] in opcodes:
                del self.pending[index]
                return packet, [packet]
        while time.monotonic() < deadline:
            try:
                packet = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if packet[0] is None:
                raise AssertionError(f"TLS peer failed: {packet[1]}")
            seen.append(packet)
            if packet[0] in opcodes:
                return packet, seen
            self.pending.append(packet)
        raise AssertionError(
            f"timeout waiting {opcodes}; received {[op for op, _ in seen]}"
        )

    def close(self):
        self.closed.set()
        try:
            with self.io_lock:
                self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            with self.io_lock:
                self.socket.close()
        except OSError:
            pass
        self.reader.join(timeout=3)


def login(store, peer, account, character, label):
    # Disposable TLS peers do not run the client's idle-session heartbeat.
    # Keep their isolated smoke-test leases valid during long synchronous NPC
    # turns, which can otherwise block both socket handlers past the default
    # 60-second session lease before the next native 12502 is emitted.
    generation = store.begin_session(account["id"], ttl=3600)
    start_test_session_heartbeat(store, account["id"], generation)
    ticket = store.issue_token(
        account["id"], "ticket", generation=generation, realm_id=10
    )
    peer.send(426, text(ticket) + text("shared-push-" + label))
    peer.wait(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
    peer.wait(630)
    peer.wait(711)
    peer.send(12449)
    peer.wait(12436)
    peer.wait(711)
    peer.send(12449)
    peer.wait(711)
    return generation


def spawned_actor(body):
    if len(body) < 13 or body[:2] != b"\x00\x01" or body[2] != 1:
        return None
    actor_id = struct.unpack_from(">q", body, 3)[0]
    size = struct.unpack_from(">H", body, 11)[0]
    actor = body[13 : 13 + size]
    if len(actor) != size or actor[0] != 11:
        raise AssertionError("malformed monster actor appearance")
    name_size = struct.unpack_from(">H", actor, 18)[0]
    offset = 20 + name_size
    reference = struct.unpack_from(">h", actor, offset)[0]
    position = struct.unpack_from(">iih", actor, offset + 2)
    return actor_id, reference, position


def placement(body):
    fight_id, count = struct.unpack_from(">ih", body)
    if len(body) != 7 + count * 18:
        raise AssertionError("malformed 13652 placement roster")
    rows = {}
    offset = 6
    for _ in range(count):
        actor, x, y, z = struct.unpack_from(">qiih", body, offset)
        rows[actor] = (x, y, z)
        offset += 18
    return fight_id, rows


@lru_cache(maxsize=8)
def _walk_edges(map_id):
    graph = {}
    data_root = Path(__file__).resolve().parents[1] / "protocol"
    path = data_root / "combat-maps" / f"{map_id}.json"
    if not path.is_file():
        raise AssertionError(f"candidate lacks geometry for map {map_id}")
    with open(path, "rt", encoding="utf-8") as source:
        geometry = json.load(source)
    if geometry.get("map_id") != map_id:
        raise AssertionError("candidate combat map geometry identity mismatch")
    for start_raw, end_raw in geometry["edges"]:
        start, end = tuple(start_raw), tuple(end_raw)
        if start[2] == end[2] and abs(start[0] - end[0]) + abs(start[1] - end[1]) == 1:
            graph.setdefault(start, set()).add(end)
    return {cell: tuple(sorted(next_cells)) for cell, next_cells in graph.items()}


def _path_to_melee_range(map_id, start, target, occupied, *, maximum_steps=4):
    adjacent = lambda cell: (
        abs(cell[0] - target[0]) + abs(cell[1] - target[1]) == 1
        and cell[2] == target[2]
    )
    if adjacent(start):
        return []
    graph = _walk_edges(map_id)
    queue = deque([start])
    previous = {start: None}
    goal = None
    while queue:
        cell = queue.popleft()
        for candidate in graph.get(cell, ()):
            if candidate in previous or candidate in occupied:
                continue
            previous[candidate] = cell
            if adjacent(candidate):
                goal = candidate
                queue.clear()
                break
            queue.append(candidate)
    if goal is None:
        return None
    route = []
    cursor = goal
    while previous[cursor] is not None:
        route.append(cursor)
        cursor = previous[cursor]
    route.reverse()
    return route[:maximum_steps]


def main():
    dbname = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not dbname.startswith("wakemu_candidate_smoke_"):
        raise ValueError("requires a disposable candidate database")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        owners = []
        for label in ("a", "b"):
            account = store.register(
                "push_" + label + "_" + secrets.token_hex(4), secrets.token_urlsafe(24)
            )
            set_admin(
                store,
                account["id"],
                True,
                operator="candidate-push",
                reason="isolated TLS test",
            )
            character = store.create_character(
                account["id"],
                "Push "
                + label.upper()
                + " "
                + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(6)),
                breed=8,
            )
            owners.append((account, character))

        for index in range(2):
            peer = Peer()
            peers.append(peer)
            login(store, peer, *owners[index], f"peer-{index}")
            print(f"peer {index + 1} selected", flush=True)
        first, second = peers
        char_a = owners[0][1]
        char_b = owners[1][1]

        # Both characters remain fresh at level 1. Raise only this disposable
        # database's monster reward input so the shared fight deterministically
        # levels both participants and exercises post-award drop-context replay.
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_monster_levels "
                "(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) "
                "VALUES(4196,1,10000,5,5,'isolated shared level-up regression') "
                "ON CONFLICT(monster_reference,monster_level) DO UPDATE SET "
                "base_xp=EXCLUDED.base_xp,min_kamas=EXCLUDED.min_kamas,"
                "max_kamas=EXCLUDED.max_kamas,source=EXCLUDED.source"
            )

        monster_text = "!mob 4196 1 1"
        first.send(12366, struct.pack(">H", len(monster_text)) + monster_text.encode())
        first.wait(674)
        target = None
        for _ in range(20):
            spawn_body, _ = first.wait(12608, timeout=5)
            candidate = spawned_actor(spawn_body)
            if candidate is not None and candidate[1] == 4196:
                target = candidate
                break
        if target is None:
            raise AssertionError("test command did not publish the requested monster")
        monster_id, monster_ref, monster_position = target
        print("target spawned", flush=True)

        first.send(13130, struct.pack(">qiihB", monster_id, *monster_position, 1))
        position_body, _ = first.wait(13652)
        fight_id, actor_positions = placement(position_body)
        if char_a["id"] not in actor_positions or monster_id not in actor_positions:
            raise AssertionError("starter placement omitted an owner or target")

        # B joins A's placement and then sends no requests during the fight.
        second.send(13241, struct.pack(">qB", char_a["id"], 0))
        own_bootstrap, bootstrap_packets = second.wait(12847)
        if not own_bootstrap:
            raise AssertionError("joiner did not receive its own placement bootstrap")
        second_positions = next(
            (body for opcode, body in bootstrap_packets if opcode == 13652), None
        )
        if second_positions is None:
            second_positions, _ = second.wait(13652)
        joined_fight_id, actor_positions = placement(second_positions)
        if joined_fight_id != fight_id or char_b["id"] not in actor_positions:
            raise AssertionError("joiner placement omitted its actor or fight identity")
        print("peer 2 joined placement", flush=True)
        first_join, _ = first.wait(13091)
        if struct.unpack_from(">i", first_join)[0] != fight_id:
            raise AssertionError("join notification belongs to a different fight")
        first.send(12523, b"\x01")
        second.send(12523, b"\x01")

        first_ready, _ = first.wait(13482)
        second_ready, _ = second.wait(13482)
        if first_ready != second_ready:
            raise AssertionError("owners did not receive the same initial turn packet")
        peer_b_sent_after_ready = len(second.sent_opcodes)
        print("both owners ready", flush=True)

        controlled = {char_a["id"]: first, char_b["id"]: second}
        turn_counts = {char_a["id"]: 1, char_b["id"]: 1}
        ack_turn = 1
        last_start = first_ready
        report_a = report_b = None
        deliveries = 0
        for _ in range(80):
            actor_id = struct.unpack_from(">q", last_start, 12)[0]
            print(f"turn actor {actor_id}", flush=True)
            if actor_id in controlled:
                actor_peer = controlled[actor_id]
                target = actor_positions[monster_id]
                current_position = actor_positions[actor_id]
                occupied = {
                    position
                    for identity, position in actor_positions.items()
                    if identity != actor_id
                }
                route = _path_to_melee_range(
                    char_a["map_id"], current_position, target, occupied
                )
                if route is None:
                    print(
                        f"no native melee route for {actor_id}; ending turn", flush=True
                    )
                elif route:
                    move_body = struct.pack(">q", actor_id) + b"".join(
                        struct.pack(">iih", *cell) for cell in route
                    )
                    actor_peer.send(12161, move_body)
                    try:
                        _, movement_packets = first.wait_any({13624, 674}, timeout=5)
                    except AssertionError as error:
                        raise AssertionError(
                            f"movement did not resolve for actor {actor_id}"
                        ) from error
                    if any(op == 674 for op, _ in movement_packets):
                        raise AssertionError(
                            f"candidate rejected native path for actor {actor_id}: {route}"
                        )
                    actor_positions[actor_id] = route[-1]
                    print(f"moved {actor_id} by {len(route)} native steps", flush=True)

                if (
                    abs(actor_positions[actor_id][0] - target[0])
                    + abs(actor_positions[actor_id][1] - target[1])
                    == 1
                    and actor_positions[actor_id][2] == target[2]
                ):
                    actor_peer.send(
                        12889, struct.pack(">qqbiih", actor_id, -1, 15, *target)
                    )
                    print(f"sent unarmed action for {actor_id}", flush=True)
                    # A native report means the attack resolved the fight. If it
                    # did not, end this owned turn and synchronize both clients.
                    try:
                        _, action_packets = first.wait_any({12755, 674}, timeout=3)
                    except AssertionError:
                        action_packets = []
                    if any(op == 674 for op, _ in action_packets):
                        raise AssertionError(
                            "candidate rejected a controlled unarmed action"
                        )
                    report_a = next(
                        (body for op, body in action_packets if op == 12755), None
                    )
                    if report_a is not None:
                        break
                actor_peer.send(
                    12403, struct.pack(">qh", actor_id, turn_counts[actor_id])
                )
                turn_counts[actor_id] += 1
            # 12502 marks the server's turn boundary. Its ACK is required from
            # every participant before the next turn can be published.
            try:
                (end_opcode, end_body), end_packets = first.wait_any(
                    {12502, 12755}, timeout=40
                )
            except AssertionError as error:
                raise AssertionError(
                    f"fight stalled at actor {actor_id}: {error}"
                ) from error
            if end_opcode == 12755:
                report_a = end_body
                break
            first.send(13510, struct.pack(">i", ack_turn))
            second.send(13510, struct.pack(">i", ack_turn))
            ack_turn += 1
            try:
                (next_opcode, next_body), turn_packets = first.wait_any(
                    {13482, 12755}, timeout=40
                )
            except AssertionError as error:
                raise AssertionError(
                    f"next turn was not pushed after ACK: {error}"
                ) from error
            if next_opcode == 12755:
                report_a = next_body
                break
            last_start = next_body
            deliveries += sum(1 for op, _ in turn_packets if op == 13482)

        if report_a is None:
            # The report is a private settlement packet, independent of which
            # participant won the last action.
            try:
                report_a, _ = first.wait(12755, timeout=10)
            except AssertionError as error:
                raise AssertionError(
                    "candidate fight did not reach a winner"
                ) from error
        # Deliberately do not send B anything after it joined/readied. Its
        # report proves the settled batch is actively pushed, not request-drained.
        report_b, _ = second.wait(12755, timeout=10)
        if not report_a or not report_b:
            raise AssertionError("one owner did not receive its private fight summary")
        peer_b_fight_opcodes = second.sent_opcodes[peer_b_sent_after_ready:]
        peer_b_gameplay_requests = [
            opcode for opcode in peer_b_fight_opcodes if opcode != 13510
        ]
        if peer_b_gameplay_requests:
            raise AssertionError(
                "inactive peer sent gameplay requests after ready: "
                f"{peer_b_gameplay_requests}"
            )

        with store.connection() as db:
            rewards = db.execute(
                "SELECT character_id,xp,kamas,start_xp,end_xp,start_level,end_level "
                "FROM fight_rewards "
                "WHERE fight_id=%s ORDER BY character_id",
                (fight_id,),
            ).fetchall()
            progression = db.execute(
                "SELECT character_id,xp FROM character_progression "
                "WHERE character_id=ANY(%s) ORDER BY character_id",
                ([char_a["id"], char_b["id"]],),
            ).fetchall()
            levels = db.execute(
                "SELECT id,level FROM characters WHERE id=ANY(%s) ORDER BY id",
                ([char_a["id"], char_b["id"]],),
            ).fetchall()
            attempts = db.execute(
                "SELECT character_id,count(*) AS attempts "
                "FROM fight_drop_attempt_receipts WHERE fight_id=%s "
                "GROUP BY character_id ORDER BY character_id",
                (fight_id,),
            ).fetchall()
            deliveries = db.execute(
                "SELECT character_id,count(*) AS deliveries "
                "FROM fight_drop_delivery_receipts WHERE fight_id=%s "
                "GROUP BY character_id ORDER BY character_id",
                (fight_id,),
            ).fetchall()
        if {row["character_id"] for row in rewards} != {char_a["id"], char_b["id"]}:
            raise AssertionError("shared settlement did not persist both owner rewards")
        reward_by_character = {row["character_id"]: row for row in rewards}
        if any(
            reward_by_character[identity]["xp"] <= 0
            for identity in (char_a["id"], char_b["id"])
        ):
            raise AssertionError(
                "uncapped shared-combat XP was not awarded to both owners"
            )
        if {
            identity: reward_by_character[identity]["start_level"]
            for identity in (char_a["id"], char_b["id"])
        } != {char_a["id"]: 1, char_b["id"]: 1}:
            raise AssertionError(
                "shared level-up test did not start both fresh characters at level 1"
            )
        if any(
            reward_by_character[identity]["end_level"] <= 1
            for identity in (char_a["id"], char_b["id"])
        ):
            raise AssertionError("shared fight did not level up both fresh characters")
        progression_by_character = {
            row["character_id"]: row["xp"] for row in progression
        }
        if any(
            progression_by_character.get(identity)
            != reward_by_character[identity]["end_xp"]
            for identity in (char_a["id"], char_b["id"])
        ):
            raise AssertionError(
                "progression XP does not match the durable fight-reward result"
            )
        level_by_character = {row["id"]: row["level"] for row in levels}
        if any(
            level_by_character.get(identity)
            != reward_by_character[identity]["end_level"]
            for identity in (char_a["id"], char_b["id"])
        ):
            raise AssertionError(
                "character level does not match the durable fight-reward result"
            )
        if {row["character_id"] for row in attempts} != {char_a["id"], char_b["id"]}:
            raise AssertionError(
                "shared settlement did not persist each owner's drop rolls"
            )
        delivery_counts = {row["character_id"]: row["deliveries"] for row in deliveries}
        if any(
            identity not in {char_a["id"], char_b["id"]} for identity in delivery_counts
        ):
            raise AssertionError(
                "drop delivery was attributed outside the fight roster"
            )

        # Reconnect B after settlement but before return. Its authenticated
        # session must receive the durable private report without another fight action.
        second.close()
        replacement = Peer()
        peers[1] = replacement
        generation_b = login(
            store, replacement, owners[1][0], char_b, "peer-b-reconnect"
        )
        replayed_b, _ = replacement.wait(12755, timeout=20)
        if not replayed_b:
            raise AssertionError(
                "reconnected owner did not receive settled report replay"
            )

        # Both owners return through the native continuation; the registry is
        # retired only after both return, while the settlement remains durable.
        for peer in peers:
            peer.send(12925, struct.pack(">iB", fight_id, 0))
        for peer in peers:
            peer.wait(13974)
        with store.connection() as db:
            final_status = db.execute(
                "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()["status"]
        if final_status != "finished":
            raise AssertionError(
                "shared fight was not durably retired after both returns"
            )
        print(
            {
                "fight_id": fight_id,
                "owners": [char_a["id"], char_b["id"]],
                "report_packets": [len(report_a), len(report_b)],
                "peer_b_sent_after_ready": peer_b_fight_opcodes,
                "peer_b_gameplay_requests_after_ready": peer_b_gameplay_requests,
                "peer_b_required_turn_ack_count": peer_b_fight_opcodes.count(13510),
                "peer_b_received_report_without_gameplay_request": not peer_b_gameplay_requests,
                "turn_ack_sequence": ack_turn - 1,
                "persisted_rewards": [
                    {
                        "character_id": row["character_id"],
                        "xp": row["xp"],
                        "kamas": row["kamas"],
                        "start_xp": row["start_xp"],
                        "end_xp": row["end_xp"],
                        "start_level": row["start_level"],
                        "end_level": row["end_level"],
                    }
                    for row in rewards
                ],
                "drop_attempts": [
                    {"character_id": row["character_id"], "count": row["attempts"]}
                    for row in attempts
                ],
                "drop_deliveries": delivery_counts,
                "reconnected_generation": generation_b,
                "settled_report_replayed": True,
                "both_returned": True,
            }
        )
    finally:
        for peer in peers:
            peer.close()
        stop_test_session_heartbeats()
        store.close()


if __name__ == "__main__":
    main()
