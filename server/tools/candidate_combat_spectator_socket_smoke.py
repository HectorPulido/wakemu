"""Three-peer TLS smoke for read-only spectators in a disposable world.

Run inside an isolated candidate container with the matching source mounted.
The script creates all accounts only in the candidate database.
"""
import os
import queue
import secrets
import re
import socket
import ssl
import struct
import threading
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat.combat_spectator_wire import decode_spectator_bootstrap
from wakfu_server.combat.combat_multiplayer_wire import decode_external
from wakfu_server.store import Store
from tls_smoke_io import recv_exact


def _text(value):
    raw = value.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        port = int(os.environ.get("WAKFU_CANDIDATE_PORT", "15556"))
        raw = socket.create_connection(("127.0.0.1", port), timeout=15)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        self.socket.settimeout(2)
        self.events = queue.Queue()
        self.pending = []
        self.sent = []
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def send(self, opcode, body=b""):
        self.sent.append(opcode)
        self.socket.sendall(_frame(opcode, body))

    def _exact(self, size):
        return recv_exact(self.socket, size, closed=self.closed)

    def _read(self):
        try:
            while not self.closed.is_set():
                try:
                    size = struct.unpack(">I", self._exact(4))[0]
                    if not 6 <= size <= 327670:
                        raise AssertionError(f"invalid frame size {size}")
                    payload = self._exact(size - 4)
                    self.events.put((struct.unpack_from(">H", payload)[0], payload[2:]))
                except socket.timeout:
                    continue
        except Exception as error:
            self.events.put((None, error))

    def wait(self, opcode, timeout=45):
        deadline = time.monotonic() + timeout
        for index, packet in enumerate(self.pending):
            if packet[0] == opcode:
                del self.pending[index]
                return packet[1], [packet]
        seen = []
        while time.monotonic() < deadline:
            try:
                packet = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if packet[0] is None:
                raise AssertionError(
                    f"TLS peer failed waiting for {opcode}: {packet[1]}"
                )
            seen.append(packet)
            if packet[0] == opcode:
                return packet[1], seen
            self.pending.append(packet)
        raise AssertionError(f"timeout for {opcode}; received {[op for op, _ in seen]}")

    def wait_any(self, opcodes, timeout=45):
        deadline = time.monotonic() + timeout
        for index, packet in enumerate(self.pending):
            if packet[0] in opcodes:
                del self.pending[index]
                return packet, [packet]
        seen = []
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
            f"timeout for {opcodes}; received {[op for op, _ in seen]}"
        )

    def close(self):
        self.closed.set()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

    def discard_buffered(self):
        """Separate the next protocol response from earlier world traffic."""
        self.pending.clear()
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                return

    def assert_absent(self, opcode, timeout=0.25):
        deadline = time.monotonic() + timeout
        if any(packet[0] == opcode for packet in self.pending):
            raise AssertionError(f"unexpected packet {opcode}")
        while time.monotonic() < deadline:
            try:
                packet = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                return
            if packet[0] is None:
                raise AssertionError(
                    f"TLS peer failed while checking {opcode}: {packet[1]}"
                )
            if packet[0] == opcode:
                raise AssertionError(f"unexpected packet {opcode}")
            self.pending.append(packet)


def _login(store, peer, account, character, label):
    generation = store.begin_session(account["id"])
    ticket = store.issue_token(
        account["id"], "ticket", generation=generation, realm_id=10
    )
    peer.send(426, _text(ticket) + _text("spectator-" + label))
    peer.wait(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.wait(630)
    peer.wait(711)
    peer.send(12449)
    peer.wait(12436)
    peer.wait(711)
    peer.send(12449)
    peer.wait(711)
    return generation


def _spawned_actor(body):
    if len(body) < 13 or body[:2] != b"\x00\x01" or body[2] != 1:
        return None
    actor_id = struct.unpack_from(">q", body, 3)[0]
    size = struct.unpack_from(">H", body, 11)[0]
    actor = body[13 : 13 + size]
    if len(actor) != size or actor[0] != 11:
        raise AssertionError("malformed monster appearance")
    name_size = struct.unpack_from(">H", actor, 18)[0]
    offset = 20 + name_size
    reference = struct.unpack_from(">h", actor, offset)[0]
    position = struct.unpack_from(">iih", actor, offset + 2)
    return actor_id, reference, position


def _console_text(body):
    if not body:
        raise AssertionError("empty local console response")
    name_size = body[0]
    offset = 1 + name_size + 11
    if len(body) < offset + 2:
        raise AssertionError("truncated local console response")
    text_size = struct.unpack_from(">H", body, offset)[0]
    text = body[offset + 2 : offset + 2 + text_size].decode("utf-8")
    if len(text.encode("utf-8")) != text_size:
        raise AssertionError("truncated local console text")
    return text


def _placement(body):
    fight_id, count = struct.unpack_from(">ih", body)
    if count < 2 or len(body) != 7 + count * 18:
        raise AssertionError("malformed 13652 placement roster")
    actors = {}
    offset = 6
    for _ in range(count):
        actor, x, y, z = struct.unpack_from(">qiih", body, offset)
        actors[actor] = (x, y, z)
        offset += 18
    return fight_id, actors


def _active_actor(packets):
    for opcode, body in reversed(packets):
        if opcode == 12873 and len(body) >= 12:
            return struct.unpack_from(">q", body, 4)[0]
    raise AssertionError("turn start omitted the current actor state")


def _wait_fight_marker(peer, fight_id, phase_code, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body, _ = peer.wait(13753, timeout=max(0.05, deadline - time.monotonic()))
        marker = decode_external(body)
        if marker["fight_id"] == fight_id and marker["phase_code"] == phase_code:
            return marker
    raise AssertionError(f"no marker for fight {fight_id} at phase {phase_code}")


def main():
    database = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError("requires a disposable candidate database")
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        owners = []
        for label in ("owner", "observer", "watcher"):
            account = store.register(
                "spectator_" + label + "_" + secrets.token_hex(4),
                secrets.token_urlsafe(24),
            )
            set_admin(
                store,
                account["id"],
                True,
                operator="candidate-spectator",
                reason="isolated spectator TLS smoke",
            )
            character = store.create_character(
                account["id"],
                "Scout "
                + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)),
                breed=8,
            )
            owners.append((account, character))

        owner, observer, existing_observer = Peer(), Peer(), Peer()
        peers.extend((owner, observer, existing_observer))
        _login(store, owner, *owners[0], "owner")
        _login(store, observer, *owners[1], "observer")
        _login(store, existing_observer, *owners[2], "existing_observer")
        owner_character = owners[0][1]
        observer_character = owners[1][1]
        existing_observer_character = owners[2][1]
        with store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_monster_levels "
                "(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) "
                "VALUES(4196,1,10000,5,5,'isolated spectator TLS smoke') "
                "ON CONFLICT(monster_reference,monster_level) DO UPDATE SET "
                "base_xp=EXCLUDED.base_xp,min_kamas=EXCLUDED.min_kamas,"
                "max_kamas=EXCLUDED.max_kamas,source=EXCLUDED.source"
            )

        owner.discard_buffered()
        command = "!mob 4196 1 1"
        owner.send(12366, struct.pack(">H", len(command)) + command.encode())
        console_text, _ = owner.wait(674)
        group_match = re.search(r"grupo=(\d+)", _console_text(console_text))
        if group_match is None:
            raise AssertionError("console response omitted the spawned group identity")
        spawned_actor_id = -int(group_match.group(1))
        monster = None
        for _ in range(20):
            body, _ = owner.wait(12608, timeout=5)
            candidate = _spawned_actor(body)
            if (
                candidate is not None
                and candidate[0] == spawned_actor_id
                and candidate[1] == 4196
            ):
                monster = candidate
                break
        if monster is None:
            raise AssertionError("candidate did not spawn the requested test monster")
        monster_id, _, position = monster

        # Ignore map/bootstrap marker snapshots from earlier disposable runs;
        # the following assertion concerns this newly-created fight only.
        owner.discard_buffered()
        owner.send(13130, struct.pack(">qiihB", monster_id, *position, 1))
        placement_body, _ = owner.wait(13652)
        fight_id, actors = _placement(placement_body)
        if owner_character["id"] not in actors or monster_id not in actors:
            raise AssertionError("fight placement omitted the owner or target")
        marker = _wait_fight_marker(observer, fight_id, 1)
        if (
            marker["fight_id"] != fight_id
            or marker["kind"] != 2
            or marker["myo"] != owner_character["map_id"]
            or marker["myp"] <= 0
            or marker["phase_code"] != 1
            or not marker["mys"]
        ):
            raise AssertionError("world fight marker omitted current public placement")
        owner.assert_absent(13753)
        owner.send(12523, b"\x01")
        _, start_packets = owner.wait(13482)
        current_actor = _active_actor(start_packets)
        active_marker = _wait_fight_marker(observer, fight_id, 2)
        if active_marker["fight_id"] != fight_id or active_marker["phase_code"] != 2:
            raise AssertionError("world marker did not update to active fight phase")
        print({"fight_id": fight_id, "active_actor": current_actor}, flush=True)

        observer.send(13413, struct.pack(">i", fight_id))
        snapshot_body, snapshot_packets = observer.wait(12044)
        snapshot = decode_spectator_bootstrap(snapshot_body)
        expected = {owner_character["id"], monster_id}
        got = {entry["actor_id"] for entry in snapshot["participants"]}
        if snapshot["fight_id"] != fight_id or snapshot["phase_code"] != 2:
            raise AssertionError("observer did not receive the current active fight")
        if got != expected:
            raise AssertionError("observer snapshot has a stale or foreign roster")
        if any(opcode == 12755 for opcode, _ in snapshot_packets):
            raise AssertionError("observer bootstrap exposed a private fight report")

        # Leaving is a native no-response notification; reentry must install a
        # new current snapshot and must not replay previously queued events.
        observer.discard_buffered()
        observer.send(12154, struct.pack(">i", fight_id))
        restored, _ = observer.wait_any({12608, 12789, 13948, 13984}, timeout=10)
        if not restored[1]:
            raise AssertionError("observer leave did not restore world state")
        restored_marker = _wait_fight_marker(observer, fight_id, 2)
        if (
            restored_marker["fight_id"] != fight_id
            or restored_marker["phase_code"] != 2
        ):
            raise AssertionError(
                "observer world return did not restore the current marker"
            )

        existing_observer.send(13413, struct.pack(">i", fight_id))
        existing_body, _ = existing_observer.wait(12044)
        existing_snapshot = decode_spectator_bootstrap(existing_body)
        if (
            existing_snapshot["fight_id"] != fight_id
            or existing_snapshot["phase_code"] != 2
        ):
            raise AssertionError(
                "existing observer did not subscribe to the active fight"
            )

        # Enter while the next turn is intentionally behind the native 13510
        # ACK barrier. The registry must defer the 12044 bootstrap rather than
        # fabricate an action deadline or reject a valid same-map observer.
        owner_turn_count = 1
        acknowledged_turn = 1
        for _ in range(20):
            if current_actor == owner_character["id"]:
                break
            owner.send(13510, struct.pack(">i", acknowledged_turn))
            acknowledged_turn += 1
            _, turn_packets = owner.wait(13482, timeout=15)
            current_actor = _active_actor(turn_packets)
        if current_actor != owner_character["id"]:
            raise AssertionError("could not reach an owned turn for ACK-gap test")
        # 12502 is not correlated by request ID in this client protocol. Clear
        # traffic left by earlier server turns so the wait below proves the
        # response to this exact action, rather than a queued earlier turn end.
        owner.discard_buffered()
        owner.send(12403, struct.pack(">qh", current_actor, owner_turn_count))
        end_turn_body, end_turn_packets = owner.wait(12502, timeout=10)
        if (
            not any(opcode == 12502 for opcode, _ in end_turn_packets)
            or len(end_turn_body) < 20
            or struct.unpack_from(">q", end_turn_body, 12)[0] != current_actor
        ):
            raise AssertionError("owned turn did not produce a fresh 12502")
        existing_observer.discard_buffered()
        existing_event, existing_event_packets = existing_observer.wait(
            12502, timeout=10
        )
        if (
            len(existing_event) < 20
            or struct.unpack_from(">q", existing_event, 12)[0] != current_actor
            or not any(opcode == 12502 for opcode, _ in existing_event_packets)
        ):
            raise AssertionError(
                "existing observer missed the public event at the ACK barrier"
            )
        observer.send(13413, struct.pack(">i", fight_id))
        observer.assert_absent(12044, timeout=0.15)
        owner.send(13510, struct.pack(">i", acknowledged_turn))
        acknowledged_turn += 1
        reentry_body, reentry_packets = observer.wait(12044)
        reentry = decode_spectator_bootstrap(reentry_body)
        if reentry["fight_id"] != fight_id or reentry["phase_code"] != 2:
            raise AssertionError(
                "deferred observer entry did not receive current combat state"
            )
        if any(opcode in {12502, 13482, 13509, 12755} for opcode, _ in reentry_packets):
            raise AssertionError(
                "deferred observer received historical events with its snapshot"
            )
        if len(reentry["myG"]) < 15:
            raise AssertionError("deferred snapshot omitted the active native timeline")
        turn_round, turn_id, on_turn, deadline_ms = struct.unpack_from(
            ">hiBq", reentry["myG"]
        )
        now_ms = int(time.time() * 1000)
        if (
            turn_round < 1
            or turn_id < 1
            or on_turn != 1
            or deadline_ms <= now_ms - 1000
            or deadline_ms > now_ms + 60000
        ):
            raise AssertionError(
                "deferred snapshot did not carry the current live turn deadline"
            )
        _, turn_packets = owner.wait(13482, timeout=15)
        current_actor = _active_actor(turn_packets)

        # A spectator may neither create another fight nor invite a duel.
        observer.send(13130, struct.pack(">qiihB", monster_id, *position, 1))
        observer.wait(674)
        observer.send(12117, b"")
        observer.wait(12708)

        owner_turn_count = 2
        reports = []
        observer_public = []
        existing_observer_public = []
        for _ in range(40):
            if current_actor == owner_character["id"]:
                target = actors[monster_id]
                owner.send(
                    12889, struct.pack(">qqbiih", current_actor, -1, 15, *target)
                )
                try:
                    (opcode, body), action_packets = owner.wait_any(
                        {12755, 674}, timeout=3
                    )
                except AssertionError:
                    opcode, body, action_packets = None, b"", []
                if opcode == 674:
                    raise AssertionError("owner unarmed attack was rejected")
                if opcode == 12755:
                    reports.append(body)
                    break
                owner.send(12403, struct.pack(">qh", current_actor, owner_turn_count))
                owner_turn_count += 1

            try:
                (opcode, body), _ = owner.wait_any({12502, 12755}, timeout=40)
            except AssertionError as error:
                raise AssertionError("candidate fight did not advance") from error
            if opcode == 12755:
                reports.append(body)
                break
            owner.send(13510, struct.pack(">i", acknowledged_turn))
            acknowledged_turn += 1
            _, turn_packets = owner.wait(13482)
            current_actor = _active_actor(turn_packets)
            try:
                event, _ = observer.wait_any(
                    {12502, 12873, 13482, 13509, 12238, 12755}, timeout=3
                )
                observer_public.append(event[0])
                if event[0] == 12755:
                    raise AssertionError("observer received private reward report")
                if event[0] == 12238:
                    break
            except AssertionError as error:
                if "timeout" not in str(error):
                    raise
            try:
                existing_event, _ = existing_observer.wait_any(
                    {12502, 12873, 13482, 13509, 12238, 12755}, timeout=0.05
                )
                existing_observer_public.append(existing_event[0])
                if existing_event[0] == 12755:
                    raise AssertionError(
                        "existing observer received private reward report"
                    )
                if existing_event[0] == 12238:
                    break
            except AssertionError as error:
                if "timeout" not in str(error):
                    raise

        if not reports:
            report, _ = owner.wait(12755, timeout=15)
            reports.append(report)
        if 13509 not in observer_public:
            try:
                event, _ = observer.wait_any({13509, 12755}, timeout=5)
                observer_public.append(event[0])
            except AssertionError:
                pass
        if 13509 not in existing_observer_public:
            try:
                event, _ = existing_observer.wait_any({13509, 12755}, timeout=5)
                existing_observer_public.append(event[0])
            except AssertionError:
                pass
        if 13509 not in observer_public:
            raise AssertionError(
                f"observer did not receive public action updates: {observer_public}"
            )
        if 13509 not in existing_observer_public:
            raise AssertionError(
                "existing observer did not receive public action updates: "
                f"{existing_observer_public}"
            )
        # The owner alone may receive the native report. The spectator is
        # returned to exploration by public cvF/12238 cleanup.
        if 12238 not in observer_public:
            try:
                observer.wait(12238, timeout=15)
                observer_public.append(12238)
            except AssertionError as error:
                raise AssertionError(
                    "observer did not receive native terminal cleanup"
                ) from error
        if 12238 not in existing_observer_public:
            try:
                existing_observer.wait(12238, timeout=15)
                existing_observer_public.append(12238)
            except AssertionError as error:
                raise AssertionError(
                    "existing observer did not receive terminal cleanup"
                ) from error

        owner.send(12925, struct.pack(">iB", fight_id, 0))
        owner.wait(13974)
        with store.connection() as db:
            owner_reward = db.execute(
                "SELECT 1 FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight_id, owner_character["id"]),
            ).fetchone()
            observer_reward = db.execute(
                "SELECT 1 FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight_id, observer_character["id"]),
            ).fetchone()
            existing_observer_reward = db.execute(
                "SELECT 1 FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight_id, existing_observer_character["id"]),
            ).fetchone()
            participants = db.execute(
                "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s",
                (fight_id,),
            ).fetchall()
        if (
            owner_reward is None
            or observer_reward is not None
            or existing_observer_reward is not None
        ):
            raise AssertionError("spectator gained or owner lost reward attribution")
        participant_ids = {row["character_id"] for row in participants}
        if (
            observer_character["id"] in participant_ids
            or existing_observer_character["id"] in participant_ids
        ):
            raise AssertionError("spectator was persisted as a fight participant")
        print(
            {
                "fight_id": fight_id,
                "observer_snapshot_phase": snapshot["phase_code"],
                "world_marker_placement_phase": marker["phase_code"],
                "world_marker_active_phase": active_marker["phase_code"],
                "marker_uid": marker["myp"],
                "marker_restored_after_leave": restored_marker["fight_id"],
                "observer_reentry_phase": reentry["phase_code"],
                "observer_world_restored_opcode": restored[0],
                "observer_public_events": observer_public,
                "existing_observer_ack_barrier_event": 12502,
                "existing_observer_public_events": existing_observer_public,
                "deferred_timeline": {
                    "round": turn_round,
                    "turn_id": turn_id,
                    "on_fighter_turn": bool(on_turn),
                    "deadline_future_ms": deadline_ms - now_ms,
                },
                "owner_reward_persisted": True,
                "observer_reward_absent": True,
                "existing_observer_reward_absent": True,
                "observer_not_participant": True,
                "world_return": "native 12238 cleanup; observer socket remained active",
            },
            flush=True,
        )
    finally:
        for peer in peers:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
