"""Local TLS acceptance of the Rii rabbit and grandmother arrival handoff.

Only new, isolated QA characters receive initial prerequisites. Subsequent
travel, callbacks, dialogue, exit and reconnects use real World requests.
This verifies protocol/state behavior, not graphical cinematic rendering.
"""

import json
import os
from pathlib import Path
import queue
import secrets
import struct
import threading
import time
from collections import deque

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from protocol_codec import DIRECTIONS
from tools.rii_lesson_parity_probe import LocalPeer
from tools.candidate_friendly_duel_socket_smoke import text
from wakfu_server.achievements import storage
from wakfu_server.combat_terrain import published_geometry
from wakfu_server.store import Store


class ObservedPeer(LocalPeer):
    GAMEPLAY_TRACE_OPCODES = frozenset(
        (13205, 13312, 13832, 13422, 13371, 13295, 12471, 13879)
    )

    def __init__(self):
        self.records = []
        self.observation_lock = threading.Lock()
        self.observation_changed = threading.Condition(self.observation_lock)
        super().__init__()

    def _read(self):
        try:
            while not self.closed.is_set():
                size = struct.unpack(">I", self._exact(4))[0]
                if not 6 <= size <= 327670:
                    raise AssertionError("Invalid World frame length")
                packet = self._exact(size - 4)
                row = struct.unpack_from(">H", packet)[0], packet[2:]
                with self.observation_changed:
                    self.records.append(row)
                    self.observation_changed.notify_all()
                self.events.put(row)
        except Exception as error:
            if not self.closed.is_set():
                self.events.put((None, error))

    def mark(self):
        with self.observation_lock:
            return len(self.records)

    def matching(self, opcode, start=0, predicate=lambda body: True, timeout=15):
        deadline = time.monotonic() + timeout
        rows = []
        while time.monotonic() < deadline:
            with self.observation_lock:
                rows = self.records[start:]
            for op, body in rows:
                if op == opcode and predicate(body):
                    return body
            if self.closed.is_set():
                break
            time.sleep(0.04)
        raise AssertionError(
            ("Missing World packet", opcode, [op for op, _ in rows[-25:]])
        )

    def matching_any(
        self, opcodes, start=0, predicate=lambda opcode, body: True, timeout=15
    ):
        """Wait for one actual received opcode without polling or consuming the queue."""
        wanted = frozenset(opcodes)
        if not wanted:
            raise ValueError("matching_any requires at least one opcode")
        deadline = time.monotonic() + timeout
        with self.observation_changed:
            while True:
                rows = self.records[start:]
                for opcode, body in rows:
                    if opcode in wanted and predicate(opcode, body):
                        return opcode, body
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.closed.is_set():
                    raise AssertionError(
                        (
                            "Missing World packet",
                            sorted(wanted),
                            [op for op, _ in rows[-25:]],
                        )
                    )
                self.observation_changed.wait(remaining)

    def scenario(self, event, start=0):
        return self.matching(
            13411,
            start,
            lambda body: len(body) >= 10
            and struct.unpack_from(">i", body, 1)[0] == event,
        )

    def gameplay_trace(self, start=0, opcodes=None):
        """Return metadata-only decoded gameplay packets, never login frames.

        The allowlist is intentionally narrow so private QA receipts can prove
        mission/objective and item notifications without storing credentials,
        chat, full inventory records, or unrelated map/bootstrap payloads.
        """
        from protocol_codec import decode_body

        selected = (
            self.GAMEPLAY_TRACE_OPCODES if opcodes is None else frozenset(opcodes)
        )
        selected &= self.GAMEPLAY_TRACE_OPCODES
        with self.observation_lock:
            rows = tuple(self.records[start:])
        trace = []
        for sequence, (opcode, body) in enumerate(rows, start=start):
            if opcode not in selected:
                continue
            row = {"sequence": sequence, "opcode": opcode, "body_bytes": len(body)}
            if opcode == 13879:
                # Quest-inventory deltas carry only actor/reference/quantity;
                # retain those fields without keeping the frame body.
                try:
                    if len(body) < 8:
                        raise ValueError("Short quest-inventory update")
                    actor_id = struct.unpack_from(">q", body)[0]
                    offset, updates = 8, []
                    while offset < len(body):
                        operation = body[offset]
                        offset += 1
                        if operation not in (0, 1, 2):
                            raise ValueError("Unknown quest-inventory operation")
                        required = 4 if operation == 1 else 6
                        if len(body) - offset < required:
                            raise ValueError("Truncated quest-inventory update")
                        reference = struct.unpack_from(">i", body, offset)[0]
                        offset += 4
                        quantity = None
                        if operation != 1:
                            quantity = struct.unpack_from(">h", body, offset)[0]
                            offset += 2
                        updates.append(
                            dict(
                                operation=operation,
                                reference_id=reference,
                                quantity=quantity,
                            )
                        )
                    row["fields"] = {
                        "actor_id": actor_id,
                        "quest_item_updates": updates,
                    }
                except (TypeError, ValueError, struct.error) as error:
                    row["decode_error"] = type(error).__name__
                trace.append(row)
                continue
            try:
                # protocol_codec names directions from the client endpoint;
                # observed World sends arrive on its "in" side.
                decoded = decode_body("in", opcode, body)
            except (TypeError, ValueError, struct.error) as error:
                row["decode_error"] = type(error).__name__
            else:
                if opcode == 12471:
                    # Keep only the ProtoItem identity and stack count; never
                    # persist its opaque payload or appearance/equipment data.
                    from wakfu_server.wire import proto_fields

                    item = {
                        tag >> 3: value
                        for tag, value in proto_fields(
                            bytes.fromhex(decoded["item_binary_hex"])
                        )
                    }
                    row["item_update"] = {
                        "container_id": decoded["container_id"],
                        "slot": decoded["destination_position"],
                        "uid": item.get(1),
                        "reference_id": item.get(2),
                        "quantity": item.get(3),
                        "mAB": decoded["mAB"],
                    }
                else:
                    row["fields"] = decoded
            trace.append(row)
        return trace

    def persist_gameplay_trace(self, path, start=0, opcodes=None):
        """Persist a safe packet summary only under private local QA storage."""
        target = Path(path).resolve()
        repository = Path(__file__).resolve().parents[2]
        private_roots = (
            repository / ".runtime",
            repository / ".local-state" / "wakemu" / "qa",
        )
        if not any(target == root or root in target.parents for root in private_roots):
            raise ValueError("Gameplay traces must stay in private local QA storage")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.gameplay_trace(start, opcodes), indent=2) + "\n"
        )
        return target


def login(store, peer, account, character):
    generation = store.begin_session(account["id"])
    ticket = store.issue_token(
        account["id"], "ticket", generation=generation, realm_id=10
    )
    peer.send(426, text(ticket) + text("rii-departure-probe"))
    peer.wait(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
    peer.wait(630)
    peer.wait(711)
    peer.send(12449)
    peer.wait(12436)
    peer.wait(711)
    peer.send(12449)
    return generation


def map_id(body):
    return struct.unpack_from(">BqBqiihqBBiihq", body, 2)[7]


class Probe:
    def __init__(self, store, *, legacy=False):
        self.store, self.legacy, self.peer = store, legacy, None
        suffix = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(9))
        self.account = store.register(
            "rii_departure_" + suffix, secrets.token_urlsafe(24)
        )
        self.character = store.create_character(
            self.account["id"], "Rii Departure " + suffix, breed=19
        )
        assert self.character["id"] != 352
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s",
                (
                    527 if legacy else 1385,
                    0 if legacy else 2,
                    32 if legacy else -11,
                    0 if legacy else 1,
                    self.character["id"],
                    self.account["id"],
                ),
            )
            state = storage.load_locked(db, self.character["id"])
            state.update(
                running=[] if legacy else [5161],
                tracking=[] if legacy else [5161],
                completed=[5146, 5160, 5161, 5278] if legacy else [5146, 5160],
                objectives=[10584, 10622, 10624, 10967] if legacy else [10584, 10622],
            )
            storage.store(db, self.character["id"], state)
            db.execute(
                "INSERT INTO character_achievement_authority(character_id,snapshot,revision,provenance) "
                "VALUES(%s,%s,1,'rii-departure-initial-fixture') "
                "ON CONFLICT(character_id) DO UPDATE SET snapshot=EXCLUDED.snapshot,revision=character_achievement_authority.revision+1",
                (
                    self.character["id"],
                    Jsonb(
                        {k: state[k] for k in ("running", "completed", "objectives")}
                    ),
                ),
            )
            if legacy:
                from wakfu_server import rii_zaap_scene

                storage.record_event(
                    db,
                    self.character["id"],
                    rii_zaap_scene.START_EVENT_KEY,
                    rii_zaap_scene._start_payload(self.character["id"]),
                )
                storage.record_event(
                    db,
                    self.character["id"],
                    rii_zaap_scene.CALLBACK_EVENT_KEY,
                    {
                        "kind": "rii_zaap_scene_callback",
                        "character_id": self.character["id"],
                        "scenario_event": 22534,
                    },
                )
        self.receipt = {
            "account_id": self.account["id"],
            "character_id": self.character["id"],
            "legacy": legacy,
            "checks": [],
        }

    def current(self):
        return self.store.character(self.account["id"], self.character["id"])

    def progress(self):
        with self.store.connection() as db:
            return storage.load_locked(db, self.character["id"])

    def check(self, label):
        self.receipt["checks"].append(label)
        print("PASS", self.character["id"], label, flush=True)

    def connect(self):
        if self.peer is not None:
            self.peer.close()
            time.sleep(0.6)
        self.peer = ObservedPeer()
        login(self.store, self.peer, self.account, self.current())

    def callback(self, event, expected=None):
        start = self.peer.mark()
        self.peer.send(12921, struct.pack(">i", event))
        if expected is not None:
            self.peer.scenario(expected, start)
        return start

    def walk(self, goal):
        current = self.current()
        start = tuple(current[k] for k in ("x", "y", "z"))
        if start == goal:
            return
        graph = published_geometry(current["map_id"]).outgoing
        previous, pending = {start: None}, deque([start])
        while pending and goal not in previous:
            cell = pending.popleft()
            for target in graph.get(cell, ()):
                if target not in previous:
                    previous[target] = cell
                    pending.append(target)
        if goal not in previous:
            raise AssertionError(("No native walking path", start, goal))
        path, cell = [], goal
        while cell != start:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        directions = {(dx, dy): key for key, (_, dx, dy) in DIRECTIONS.items()}
        encoded, point = bytearray(), start
        for cell in path:
            encoded.append(
                (directions[(cell[0] - point[0], cell[1] - point[1])] << 5)
                | ((cell[2] - point[2]) & 31)
            )
            point = cell
        self.peer.send(13331, struct.pack(">iiihB", 0, *start, len(path)) + encoded)
        time.sleep(min(5, 0.22 * len(path) + 0.25))

    def run(self):
        self.connect()
        if not self.legacy:
            start = self.peer.mark()
            self.peer.send(12870, struct.pack(">qHH", 34719, 5, 0))
            self.peer.scenario(22534, start)
            self.check("native rabbit scene authorized")
            self.connect()
            self.peer.scenario(22534)
            self.check("pending rabbit scene resumes after reconnect")
            start = self.callback(22534)
            self.peer.matching(13974, start, lambda body: map_id(body) == 895)
            self.peer.send(12449)
        self.peer.scenario(17029)
        assert self.current()["map_id"] == 895
        state = self.progress()
        assert (
            5161 in state["completed"]
            and 10624 in state["objectives"]
            and 5568 in state["running"]
        )
        self.check("owned arrival895 and mission5568 activated")
        self.connect()
        self.peer.scenario(17029)
        self.callback(17029, 23936)
        self.check("load handshake and fall video")
        self.connect()
        self.peer.scenario(17029)
        self.callback(17029, 23936)
        self.callback(23936, 17022)
        self.check("video callback launches grandmother scene")
        self.connect()
        self.peer.scenario(17029)
        self.callback(17029, 17022)
        start = self.callback(17022)
        self.peer.matching(13259, start)
        assert tuple(self.current()[key] for key in ("x", "y", "z")) == (-3, -4, 0)
        self.check(
            "cinematic reconnect skips completed video and settles indoor position"
        )
        self.connect()
        time.sleep(0.4)
        assert not any(
            op == 13411
            and len(body) >= 10
            and struct.unpack_from(">i", body, 5)[0] == 2120
            for op, body in self.peer.records
        )
        self.check("completed arrival does not replay on reconnect")
        self.walk((0, -3, 0))
        start = self.peer.mark()
        self.peer.send(13222, struct.pack(">qq", -1776810787923716, 587))
        root = self.peer.matching(12969, start)
        assert struct.unpack_from(">i", root)[0] == 7115
        for node, choice, target in (
            (7115, 15205, 7116),
            (7116, 15208, 7117),
            (7117, 15209, 7118),
            (7118, 15210, 0),
        ):
            start = self.peer.mark()
            self.peer.send(12058, struct.pack(">ii", node, choice))
            body = self.peer.matching(12218, start)
            assert struct.unpack_from(">i", body)[0] == target
        assert 11508 in self.progress()["objectives"]
        self.check("four native grandmother choices complete11508")
        self.walk((-1, 1, 0))
        start = self.peer.mark()
        self.peer.send(12870, struct.pack(">qHH", 35386, 5, 0))
        self.peer.matching(13974, start, lambda body: map_id(body) == 527)
        self.peer.send(12449)
        assert 11509 in self.progress()["objectives"]
        assert tuple(self.current()[key] for key in ("map_id", "x", "y", "z")) == (
            527,
            7,
            156,
            0,
        )
        self.check("native house exit completes11509 and reaches Astrub")
        self.connect()
        assert self.current()["map_id"] == 527
        assert {11508, 11509} <= set(self.progress()["objectives"])
        self.check("final progress survives reconnect")
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT event_key FROM character_achievement_events WHERE character_id=%s AND (event_key LIKE 'astrub-arrival%%' OR event_key LIKE 'rii-zaap-scene%%' OR event_key LIKE 'astrub-house-exit%%') ORDER BY event_key",
                (self.character["id"],),
            ).fetchall()
        self.receipt["events"] = [row["event_key"] for row in rows]
        self.receipt["progress"] = self.progress()
        return self.receipt


def main():
    dsn = os.environ["WAKFU_DATABASE_URL"]
    if conninfo_to_dict(dsn).get("host") not in ("127.0.0.1", "localhost"):
        raise ValueError("This gameplay probe is local only")
    store = Store(dsn, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    path = Path(
        os.environ.get(
            "WAKFU_RII_DEPARTURE_RECEIPT",
            ".local-state/wakemu/qa/rii-departure-probe.json",
        )
    )
    prior = json.loads(path.read_text()) if path.exists() else {}
    prior_failures = [
        *prior.get("prior_failures", []),
        *(run for run in prior.get("runs", []) if "error" in run),
    ]
    receipts = []
    try:
        for legacy in (False, True):
            probe = Probe(store, legacy=legacy)
            try:
                receipts.append(probe.run())
            except Exception as error:
                probe.receipt["error"] = repr(error)
                receipts.append(probe.receipt)
                raise
            finally:
                if probe.peer is not None:
                    probe.peer.close()
    finally:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "scope": "local TLS/state; graphical rendering not verified",
                    "prior_failures": prior_failures,
                    "runs": receipts,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
