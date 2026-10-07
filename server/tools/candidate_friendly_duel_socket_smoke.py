"""Two-peer TLS acceptance, forfeit, and no-reward smoke for friendly duels.

Run this only inside a disposable candidate world with its own
``wakemu_candidate_smoke_*`` database. The script creates four test accounts,
checks one refusal and one accepted duel, disconnects both sockets, then
reconnects both owners and verifies durable no-reward/full-health settlement.
"""
import os
import queue
import secrets
import socket
import ssl
import struct
import threading
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.store import Store
from tls_smoke_io import recv_exact


def text(value):
    raw = value.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw


def frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        port = int(os.environ.get("WAKFU_CANDIDATE_PORT", "15556"))
        raw = socket.create_connection(("127.0.0.1", port), timeout=15)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        self.socket.settimeout(1)
        self.events = queue.Queue()
        self.pending = []
        self.sent = []
        self.closed = threading.Event()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def send(self, opcode, body=b""):
        self.sent.append(opcode)
        self.socket.sendall(frame(opcode, body))

    def _exact(self, size):
        return recv_exact(self.socket, size, closed=self.closed)

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

    def wait(self, opcode, timeout=30):
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
                    f"TLS peer failed while waiting {opcode}: {packet[1]}"
                )
            seen.append(packet)
            if packet[0] == opcode:
                return packet[1], seen
            self.pending.append(packet)
        raise AssertionError(
            f"timeout waiting {opcode}; received {[op for op, _ in seen]}"
        )

    def close(self):
        self.closed.set()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()


def login(store, peer, account, character, label):
    generation = store.begin_session(account["id"])
    ticket = store.issue_token(
        account["id"], "ticket", generation=generation, realm_id=10
    )
    peer.send(426, text(ticket) + text("friendly-duel-" + label))
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


def challenge_body(target_id, position):
    x, y, z = position
    return struct.pack(">qiihBB", target_id, x, y, z, 0, 1)


def placement(body):
    if len(body) < 7:
        raise AssertionError("truncated duel placement roster")
    fight_id, count = struct.unpack_from(">ih", body)
    if count < 2 or len(body) != 7 + count * 18:
        raise AssertionError("malformed native duel placement roster")
    actors = {}
    offset = 6
    for _ in range(count):
        actor_id, x, y, z = struct.unpack_from(">qiih", body, offset)
        actors[actor_id] = (x, y, z)
        offset += 18
    return fight_id, actors


def main():
    database = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Friendly-duel socket smoke requires a disposable candidate DB"
        )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peers = []
    try:
        owners = []
        for label in "abcd":
            account = store.register(
                "duel_" + label + "_" + secrets.token_hex(4), secrets.token_urlsafe(24)
            )
            character = store.create_character(
                account["id"],
                "Duel "
                + label.upper()
                + " "
                + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(6)),
                breed=8,
            )
            owners.append((account, character))

        # Give both accepted participants an existing wound. Duel settlement
        # must restore it without modifying their exterior tile or progression.
        cells = map_geometry(1134)["edges"][0]
        for index, cell in enumerate(cells):
            account, character = owners[index]
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s,hp=5,hp_damage=max_hp-5,"
                    "health_dead=false WHERE id=%s AND account_id=%s",
                    (*cell, character["id"], account["id"]),
                )

        for index, owner in enumerate(owners):
            peer = Peer()
            peers.append(peer)
            login(store, peer, owner[0], owner[1], f"peer-{index}")

        # A refusal must notify both leases and create no combat row.
        account_c, char_c = owners[2]
        account_d, char_d = owners[3]
        peer_c, peer_d = peers[2], peers[3]
        peer_c.send(12117, challenge_body(char_d["id"], (999, 999, 0)))
        invite_body, _ = peer_d.wait(13179)
        if invite_body != struct.pack(">qB", char_c["id"], 1):
            raise AssertionError("native duel invitation names the wrong challenger")
        peer_d.send(13520, struct.pack(">qBB", char_c["id"], 0, 0))
        refusal_target, _ = peer_d.wait(12708)
        refusal_source, _ = peer_c.wait(12708)
        if refusal_target != b"\x01" or refusal_source != b"\x01":
            raise AssertionError("native refusal was not published to both leases")
        with store.connection() as db:
            refused = db.execute(
                "SELECT status,fight_id FROM friendly_duel_invitations "
                "WHERE challenger_character_id=%s AND target_character_id=%s "
                "ORDER BY id DESC LIMIT 1",
                (char_c["id"], char_d["id"]),
            ).fetchone()
            if (
                refused is None
                or refused["status"] != "rejected"
                or refused["fight_id"] is not None
            ):
                raise AssertionError("refusal did not remain a no-fight durable result")

        account_a, char_a = owners[0]
        account_b, char_b = owners[1]
        peer_a, peer_b = peers[0], peers[1]
        baseline = {}
        for account, character in ((account_a, char_a), (account_b, char_b)):
            with store.connection() as db:
                row = db.execute(
                    "SELECT c.hp,c.max_hp,c.hp_damage,c.health_dead,c.map_id,c.instance_id,"
                    "c.x,c.y,c.z,p.xp,w.kamas FROM characters c "
                    "JOIN character_progression p ON p.character_id=c.id "
                    "JOIN account_wallets w ON w.account_id=c.account_id "
                    "WHERE c.id=%s AND c.account_id=%s",
                    (character["id"], account["id"]),
                ).fetchone()
            baseline[character["id"]] = dict(row)
        peer_a.send(12117, challenge_body(char_b["id"], (999, 999, 0)))
        invite_body, _ = peer_b.wait(13179)
        if invite_body != struct.pack(">qB", char_a["id"], 1):
            raise AssertionError("accepted duel invitation names the wrong challenger")
        peer_b.send(13520, struct.pack(">qBB", char_a["id"], 1, 0))
        position_a, _ = peer_a.wait(13652)
        position_b, _ = peer_b.wait(13652)
        fight_id, actors_a = placement(position_a)
        fight_id_b, actors_b = placement(position_b)
        if (
            fight_id_b != fight_id
            or set(actors_a) != {char_a["id"], char_b["id"]}
            or actors_a != actors_b
        ):
            raise AssertionError(
                "accepted duel did not push one shared two-player placement"
            )
        peer_a.wait(12847)
        peer_b.wait(12847)
        with store.connection() as db:
            row = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()
        if row is None or (row["status"], row["fight_kind"]) != ("placement", "duel"):
            raise AssertionError("accepted duel was not durably marked as a duel fight")

        peer_a.send(12523, b"\x01")
        peer_b.send(12523, b"\x01")
        peer_a.wait(13482)
        peer_b.wait(13482)
        # Close both sockets without sending another gameplay packet. One
        # disconnect must durably forfeit/settle before either session ends.
        peer_b.close()
        peer_a.close()
        deadline = time.monotonic() + 30
        outcome = None
        while time.monotonic() < deadline:
            with store.connection() as db:
                outcome = db.execute(
                    "SELECT winner_character_id,loser_character_id,reason "
                    "FROM friendly_duel_outcomes WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()
            if outcome is not None:
                break
            time.sleep(0.1)
        if outcome is None or outcome["reason"] != "disconnect":
            raise AssertionError("dual disconnect did not persist a duel forfeit")

        with store.connection() as db:
            fight = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s", (fight_id,)
            ).fetchone()
            rows = db.execute(
                "SELECT c.id,c.hp,c.max_hp,c.hp_damage,c.health_dead,c.map_id,c.instance_id,"
                "c.x,c.y,c.z,p.xp,w.kamas FROM characters c "
                "JOIN character_progression p ON p.character_id=c.id "
                "JOIN account_wallets w ON w.account_id=c.account_id "
                "WHERE c.id=ANY(%s) ORDER BY c.id",
                ([char_a["id"], char_b["id"]],),
            ).fetchall()
            for table in (
                "fight_rewards",
                "fight_drop_awards",
                "fight_drop_attempt_receipts",
                "fight_drop_delivery_receipts",
            ):
                if db.execute(
                    f"SELECT 1 FROM {table} WHERE fight_id=%s LIMIT 1", (fight_id,)
                ).fetchone():
                    raise AssertionError(f"duel wrote forbidden PvE rows to {table}")
        if fight["status"] != "finished" or fight["fight_kind"] != "duel":
            raise AssertionError("duel disconnect was not durably finished")
        if outcome["winner_character_id"] not in (char_a["id"], char_b["id"]):
            raise AssertionError("forfeit winner is outside the accepted roster")
        for row in rows:
            before = baseline[row["id"]]
            if (
                row["hp"] != row["max_hp"]
                or row["hp_damage"] != 0
                or row["health_dead"]
                or row["xp"] != before["xp"]
                or row["kamas"] != before["kamas"]
                or tuple(row[key] for key in ("map_id", "instance_id", "x", "y", "z"))
                != tuple(
                    before[key] for key in ("map_id", "instance_id", "x", "y", "z")
                )
            ):
                raise AssertionError(
                    f"duel settlement violated no-reward/full-HP/location for {row['id']}"
                )

        # Both leases were offline at settlement; new leases must replay the
        # committed report and return through the native continuation packet.
        for index, owner in enumerate((owners[0], owners[1])):
            replacement = Peer()
            peers[index] = replacement
            login(store, replacement, owner[0], owner[1], f"reconnect-{index}")
            replacement.wait(12755, timeout=20)
            replacement.send(12925, struct.pack(">iB", fight_id, 0))
            replacement.wait(13974, timeout=20)

        print(
            {
                "fight_id": fight_id,
                "participants": [char_a["id"], char_b["id"]],
                "refusal_no_fight": True,
                "both_disconnects_settled": True,
                "full_hp_no_rewards_no_teleport": True,
                "reconnect_report_and_return": True,
            },
            flush=True,
        )
    finally:
        for peer in peers:
            try:
                peer.close()
            except Exception:
                pass
        store.close()


if __name__ == "__main__":
    main()
