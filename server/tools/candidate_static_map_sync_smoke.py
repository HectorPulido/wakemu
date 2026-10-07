"""Verify quiet 13984 delivery across one isolated TLS map transition.

Run inside a disposable candidate container after its HTTP health check. The
script uses only a ``wakemu_candidate_smoke_*`` database and never sends 14689.
"""
import json
import base64
import hashlib
import os
import secrets
import socket
import ssl
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server import combat_terrain, world_static
from wakfu_server.command_permissions import set_admin
from wakfu_server.store import Store


def _text(value):
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        address = os.environ.get("WAKFU_SMOKE_HOST", "127.0.0.1")
        port = int(os.environ.get("WAKFU_SMOKE_PORT", "15556"))
        raw = socket.create_connection((address, port), timeout=5)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        self.socket.settimeout(1)
        self.received = []
        self.sent_opcodes = []

    def send(self, opcode, body=b""):
        self.socket.sendall(_frame(opcode, body))
        self.sent_opcodes.append(opcode)

    def exact(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out reading native TLS frame")
            try:
                chunk = self.socket.recv(size - len(data))
            except socket.timeout:
                continue
            if not chunk:
                raise AssertionError("Candidate TLS connection closed unexpectedly")
            data.extend(chunk)
        return bytes(data)

    def receive(self, timeout=12):
        deadline = time.monotonic() + timeout
        size = struct.unpack(">I", self.exact(4, deadline))[0]
        if not 6 <= size <= 327670:
            raise AssertionError("Invalid native server frame size")
        frame = self.exact(size - 4, deadline)
        packet = struct.unpack_from(">H", frame)[0], frame[2:]
        self.received.append(packet)
        return packet

    def until(self, *opcodes, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                packet = self.receive(max(0.1, deadline - time.monotonic()))
            except TimeoutError:
                continue
            if packet[0] in opcodes:
                return packet
        raise AssertionError(f"Timed out waiting for candidate opcodes {opcodes}")


def _catalog_rows(map_id):
    rows = json.loads((world_static.DATA_ROOT / "native-map-objects.json").read_text())
    return [row for row in rows if row["map_id"] == map_id]


def _decode_snapshot(body):
    if len(body) < 2:
        raise AssertionError("Truncated 13984 state snapshot")
    count = struct.unpack_from(">h", body)[0]
    if count < 0:
        raise AssertionError("Negative 13984 object count")
    offset = 2
    rows = {}
    for _ in range(count):
        if offset + 10 > len(body):
            raise AssertionError("Truncated 13984 object header")
        identity, size = struct.unpack_from(">qh", body, offset)
        offset += 10
        if size < 0 or offset + size > len(body):
            raise AssertionError("Invalid 13984 object payload length")
        if identity in rows:
            raise AssertionError("Duplicate object ID inside 13984 snapshot")
        rows[identity] = body[offset : offset + size]
        offset += size
    if offset != len(body):
        raise AssertionError("Trailing bytes in 13984 state snapshot")
    return rows


def _expected_rows(map_id):
    return {
        row["id"]: bytes.fromhex(row["payload_hex"]) for row in _catalog_rows(map_id)
    }


def _captured_13984_bodies():
    path = os.environ.get("WAKFU_CAPTURE_PATH")
    if not path:
        return set()
    bodies = set()
    with open(path, encoding="utf-8") as source:
        for line in source:
            frame = json.loads(line)
            if frame.get("direction") == "in" and frame.get("opcode") == 13984:
                bodies.add(base64.b64decode(frame["body_base64"]))
    return bodies


def _collect_map_snapshot(
    peer, map_id, start_index, *, minimum_snapshots=1, replay_bodies=()
):
    expected = _expected_rows(map_id)
    if not expected:
        raise AssertionError(f"No native static objects are exported for map {map_id}")
    seen = {}
    full_snapshots = 0
    replayed_snapshots = 0
    index = start_index
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        while index < len(peer.received):
            opcode, body = peer.received[index]
            index += 1
            if opcode == 13984:
                if body in replay_bodies:
                    replayed_snapshots += 1
                    continue
                received = _decode_snapshot(body)
                for identity, payload in received.items():
                    if identity not in expected:
                        raise AssertionError(
                            f"13984 object {identity} is not in native map {map_id}"
                        )
                    if expected[identity] != payload:
                        raise AssertionError(
                            f"13984 object {identity} payload differs from map {map_id} "
                            f"catalog ({len(payload)} vs {len(expected[identity])} bytes)"
                        )
                seen.update(received)
                if received == expected:
                    full_snapshots += 1
                if set(seen) == set(expected) and full_snapshots >= minimum_snapshots:
                    return index, len(seen), full_snapshots, replayed_snapshots
                if not set(seen).issubset(expected):
                    raise AssertionError(
                        f"13984 sent object IDs for another map: {sorted(set(seen)-set(expected))[:8]}"
                    )
        try:
            peer.receive(max(0.1, deadline - time.monotonic()))
        except TimeoutError:
            continue
    missing = sorted(set(expected) - set(seen))
    raise AssertionError(
        f"Quiet 13984 sync for map {map_id} missed {len(missing)} objects: {missing[:12]}"
    )


def _select_character(peer, account_id, generation, store, character):
    ticket = store.issue_token(account_id, "ticket", generation=generation, realm_id=10)
    peer.send(426, _text(ticket) + _text("static-map-sync-smoke"))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    peer.send(12449)
    peer.until(12436)
    peer.until(711)
    peer.send(12449)
    peer.until(711)


def main():
    database_url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(database_url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Static map TLS smoke requires a disposable candidate database"
        )
    store = Store(
        database_url,
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    account = store.register(
        "static_sync_" + secrets.token_hex(5), secrets.token_urlsafe(24)
    )
    account_id = account["id"]
    set_admin(store, account_id, True, operator="candidate-smoke", reason="static sync")
    name = "Sync " + "".join(
        secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)
    )
    character = store.create_character(account_id, name, breed=8)
    character = store.character(account_id, character["id"])
    initial_map = character["map_id"]
    target_map = 527 if initial_map != 527 else 1134
    target = tuple(combat_terrain.map_geometry(target_map)["cells"][0])

    peer = None
    try:
        generation = store.begin_session(account_id)
        peer = Peer()
        _select_character(peer, account_id, generation, store, character)
        captured_states = _captured_13984_bodies()
        initial_cursor, initial_count, _, initial_replayed = _collect_map_snapshot(
            peer,
            initial_map,
            0,
            replay_bodies=captured_states if initial_map == 1134 else (),
        )

        command = f"!tp {target_map} {target[0]} {target[1]} {target[2]}"
        encoded = command.encode("utf-8")
        peer.send(12366, struct.pack(">H", len(encoded)) + encoded)
        peer.until(674)
        cursor = len(peer.received)
        cursor, target_count, _, target_replayed = _collect_map_snapshot(
            peer,
            target_map,
            cursor,
            replay_bodies=captured_states if target_map == 1134 else (),
        )
        with store.connection() as db:
            persisted = store.character(account_id, character["id"], db)
        if (persisted["map_id"], persisted["x"], persisted["y"], persisted["z"]) != (
            target_map,
            *target,
        ):
            raise AssertionError("TLS transition did not persist the expected map cell")
        if 14689 in peer.sent_opcodes:
            raise AssertionError("The smoke client must not send map-ready 14689")
        quiet_sent_opcodes = list(peer.sent_opcodes)

        peer.socket.close()
        generation = store.begin_session(account_id)
        peer = Peer()
        _select_character(peer, account_id, generation, store, persisted)
        (
            reconnect_cursor,
            reconnect_count,
            retries,
            reconnect_replayed,
        ) = _collect_map_snapshot(
            peer,
            target_map,
            0,
            minimum_snapshots=3,
            replay_bodies=captured_states if target_map == 1134 else (),
        )
        if reconnect_count != target_count:
            raise AssertionError(
                "Reconnect 13984 snapshot has a different map object count"
            )
        if 14689 in peer.sent_opcodes:
            raise AssertionError("Reconnect quiet sync unexpectedly sent 14689")

        force_started = time.monotonic()
        peer.send(14689)
        _, forced_body = peer.until(13984, timeout=3)
        force_seconds = time.monotonic() - force_started
        if _decode_snapshot(forced_body) != _expected_rows(target_map):
            raise AssertionError(
                "Forced 14689 response differs from target map objects"
            )
        if force_seconds >= 3:
            raise AssertionError("Forced map sync did not respond promptly")
        print(
            json.dumps(
                {
                    "database": database,
                    "initial_map": initial_map,
                    "initial_object_count": initial_count,
                    "initial_replayed_capture_snapshots": initial_replayed,
                    "target_map": target_map,
                    "target_cell": target,
                    "target_object_count": target_count,
                    "target_replayed_capture_snapshots": target_replayed,
                    "target_object_ids_sha256": hashlib.sha256(
                        b"".join(
                            struct.pack(">q", identity)
                            for identity in sorted(_expected_rows(target_map))
                        )
                    ).hexdigest(),
                    "quiet_transition_client_opcodes": quiet_sent_opcodes,
                    "reconnect_quiet_snapshot_count": retries,
                    "reconnect_object_count": reconnect_count,
                    "reconnect_replayed_capture_snapshots": reconnect_replayed,
                    "force_request_opcodes": peer.sent_opcodes,
                    "forced_snapshot_seconds": round(force_seconds, 3),
                    "result": "PASS",
                },
                sort_keys=True,
            )
        )
    finally:
        if peer is not None:
            peer.socket.close()


if __name__ == "__main__":
    main()
