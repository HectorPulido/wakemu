"""Exercise 13787 identification through a disposable candidate TLS socket.

The script only creates a temporary admin account in a guarded candidate DB.
It checks the under-level 13766 result, one priced local-policy success,
durable retry, and reconnect publication through both native item carriers.
"""
import os
import secrets
import select
import socket
import ssl
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.inventory_items import item_form, item_proto
from wakfu_server.store import Store
from wakfu_server.wire import ENTITY_LAYOUTS, proto_fields


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


def _text(value):
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


class Peer:
    def __init__(self):
        raw = socket.create_connection(("127.0.0.1", 15556), timeout=10)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        self.socket.settimeout(45)
        self.received = []

    def send(self, opcode, body=b""):
        self.socket.sendall(_frame(opcode, body))

    def exact(self, count):
        output = bytearray()
        while len(output) < count:
            chunk = self.socket.recv(count - len(output))
            if not chunk:
                raise AssertionError("Candidate closed identification TLS socket")
            output.extend(chunk)
        return bytes(output)

    def receive(self):
        size = struct.unpack(">I", self.exact(4))[0]
        if not 6 <= size <= 327670:
            raise AssertionError("Invalid candidate native frame size")
        frame = self.exact(size - 4)
        packet = struct.unpack_from(">H", frame)[0], frame[2:]
        self.received.append(packet)
        return packet

    def until(self, wanted, timeout=45):
        wanted = set(wanted if isinstance(wanted, (tuple, list, set)) else (wanted,))
        seen = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            packet = self.receive()
            seen.append(packet)
            if packet[0] in wanted:
                return packet, seen
        raise AssertionError(f"Candidate omitted native packet(s) {sorted(wanted)}")

    def drain(self, quiet=0.15):
        packets = []
        while self.socket.pending() or select.select([self.socket], [], [], quiet)[0]:
            packets.append(self.receive())
        return packets

    def close(self):
        self.socket.close()


def _connect(store, account_id, character, generation):
    peer = Peer()
    ticket = store.issue_token(account_id, "ticket", generation=generation, realm_id=10)
    peer.send(426, _text(ticket) + _text("isolated-shard-identification-smoke"))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    peer.send(12449)
    peer.until(12436)
    peer.send(12449)
    peer.until(711)
    peer.drain()
    return peer


def _command(peer, command):
    raw = command.encode("ascii")
    peer.send(12366, struct.pack(">H", len(raw)) + raw)


def _wait_item(store, character_id, reference, quantity, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with store.connection() as db:
            row = db.execute(
                "SELECT uid,reference,quantity FROM inventory_items "
                "WHERE character_id=%s AND reference=%s ORDER BY uid LIMIT 1",
                (character_id, reference),
            ).fetchone()
        if row is not None and row["quantity"] == quantity:
            return dict(row)
        time.sleep(0.05)
    raise AssertionError(f"Candidate did not grant native item {reference}")


def _wait_level(store, character_id, level, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with store.connection() as db:
            row = db.execute(
                "SELECT level FROM characters WHERE id=%s", (character_id,)
            ).fetchone()
        if row is not None and row["level"] == level:
            return
        time.sleep(0.05)
    raise AssertionError("Candidate level command did not commit")


def _parse_13766(body):
    if len(body) < 21:
        raise AssertionError("Truncated native 13766 response")
    status, uid, reserved, element_size = struct.unpack_from(">iqBI", body)
    offset = 17
    if (
        reserved != 0
        or element_size not in (0, 2)
        or len(body) < offset + element_size + 4
    ):
        raise AssertionError("Malformed native 13766 element section")
    elements = body[offset : offset + element_size]
    offset += element_size
    shard_size = struct.unpack_from(">I", body, offset)[0]
    offset += 4
    if len(body) != offset + shard_size:
        raise AssertionError("Malformed native 13766 ProtoShard section")
    return dict(status=status, uid=uid, elements=elements, shard=body[offset:])


def _check_native_shard(shard):
    slots = []
    for tag, value in proto_fields(shard):
        if tag != 10:
            continue
        fields = dict(proto_fields(value))
        position = fields.get(80)
        color = fields.get(96)
        if type(position) is not int or type(color) is not int or not 0 <= color <= 4:
            raise AssertionError("Candidate shard contains an invalid native slot")
        if fields.get(88, 0) != 0 or fields.get(112, 0) != 0:
            raise AssertionError("Freshly identified shard slot should be empty")
        slots.append((position, color))
    if not 1 <= len(slots) <= 4 or [row[0] for row in slots] != list(range(len(slots))):
        raise AssertionError("Candidate shard count or slot positions are invalid")


def _check_reconnect_bootstrap(peer, character, item):
    from wakfu_server.inventory_shards import option

    persisted = next(
        row for row in character["inventory_items"] if row["uid"] == item["uid"]
    )
    proto = item_proto(persisted)
    form = item_form(persisted)
    shard = persisted["shard_state"]
    if shard is None or option(persisted) is None:
        raise AssertionError("Reopened item did not hydrate its ProtoShard/vA state")
    equipment_carriers = []
    bag_sections = []
    for opcode, body in peer.received:
        if opcode == 13078 and len(body) >= 13:
            owner, size, _flags = struct.unpack_from(">qIB", body)
            if owner == character["id"] and len(body) == 13 + size:
                equipment_carriers.append(body[13:])
        elif opcode == 13713 and len(body) > 8:
            entity = body[8:]
            layout = ENTITY_LAYOUTS.get(entity[0])
            if layout is None:
                continue
            bags = next(
                (
                    section
                    for section in layout["sections"]
                    if section["name"] == "BAGS"
                ),
                None,
            )
            if bags is not None:
                bag_sections.append(entity[bags["start"] : bags["end"]])
    if not any(proto in carrier for carrier in equipment_carriers):
        raise AssertionError("Reconnect equipment bootstrap omitted ProtoItem field 52")
    if not any(form in section for section in bag_sections):
        raise AssertionError("Reconnect native BAGS section omitted the vA item form")
    return shard


def main():
    database = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"]).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Identification smoke requires a disposable candidate database"
        )
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
    )
    peer = None
    try:
        account = store.register(
            "shard_smoke_" + secrets.token_hex(5), secrets.token_urlsafe(24)
        )["id"]
        set_admin(
            store,
            account,
            True,
            operator="candidate-shard-identification-smoke",
            reason="disposable socket test",
        )
        character = store.create_character(
            account,
            "Shard Test "
            + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(6)),
            breed=8,
        )
        with store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=100 WHERE account_id=%s", (account,)
            )
            db.execute(
                "UPDATE settings SET value=jsonb_set(value,'{cost_kamas}','7') "
                "WHERE name='socket_identification_policy'"
            )
        generation = store.begin_session(account)
        peer = _connect(store, account, character, generation)

        # Laminadora (ref 12) is a native eligible template requiring level
        # 60. At level 1 it must return 13766/TOO_HIGH_LEVEL and leave no row.
        _command(peer, "!item 12 1")
        low_item = _wait_item(store, character["id"], 12, 1)
        peer.drain()
        peer.send(13787, struct.pack(">q", low_item["uid"]))
        low_packet, _ = peer.until(13766)
        low_result = _parse_13766(low_packet[1])
        if low_result != dict(status=2, uid=low_item["uid"], elements=b"", shard=b""):
            raise AssertionError(
                "Under-level candidate did not emit the exact 13766 status-2 result"
            )
        with store.connection() as db:
            if (
                db.execute(
                    "SELECT 1 FROM inventory_socket_identification_receipts WHERE uid=%s",
                    (low_item["uid"],),
                ).fetchone()
                or db.execute(
                    "SELECT 1 FROM inventory_item_shards WHERE uid=%s",
                    (low_item["uid"],),
                ).fetchone()
            ):
                raise AssertionError("Under-level identification mutated durable state")
            if (
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
                ).fetchone()["kamas"]
                != 100
            ):
                raise AssertionError("Under-level identification charged kamas")

        _command(peer, "!nivel 100")
        _wait_level(store, character["id"], 100)
        _command(peer, "!item 2869 1")  # Espada Mento, native item level 80.
        high_item = _wait_item(store, character["id"], 2869, 1)
        peer.drain()
        with store.connection() as db:
            elements = db.execute(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                (high_item["uid"],),
            ).fetchone()
            if elements is None:
                raise AssertionError(
                    "Native eligible item lacks its persisted element selections"
                )
            before = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account,)
            ).fetchone()["kamas"]

        request = struct.pack(">q", high_item["uid"])
        peer.send(13787, request)
        success_packet, _ = peer.until(13766)
        success = _parse_13766(success_packet[1])
        if success["status"] != 0 or success["uid"] != high_item["uid"]:
            raise AssertionError(
                "Eligible identification did not return native status 0"
            )
        if success["elements"] != bytes(
            (elements["damage_elements"], elements["resistance_elements"])
        ):
            raise AssertionError("13766 did not preserve both elemental masks")
        _check_native_shard(success["shard"])
        wallet_packet, _ = peer.until(12753)
        if wallet_packet[1] != struct.pack(">q", before - 7):
            raise AssertionError(
                "Candidate did not publish the configured account wallet balance"
            )

        with store.connection() as db:
            durable = db.execute(
                "SELECT r.reference,r.cost_kamas,r.shard_state,w.kamas "
                "FROM inventory_socket_identification_receipts r "
                "JOIN account_wallets w USING(account_id) WHERE r.uid=%s AND r.account_id=%s",
                (high_item["uid"], account),
            ).fetchone()
            receipt_count = db.execute(
                "SELECT count(*) AS n FROM inventory_socket_identification_receipts "
                "WHERE account_id=%s AND character_id=%s AND uid=%s",
                (account, character["id"], high_item["uid"]),
            ).fetchone()["n"]
        if (
            durable is None
            or durable["reference"] != 2869
            or durable["cost_kamas"] != 7
        ):
            raise AssertionError("Identification receipt is incomplete")
        if (
            bytes(durable["shard_state"]) != success["shard"]
            or durable["kamas"] != before - 7
            or receipt_count != 1
        ):
            raise AssertionError(
                "Identification receipt, ProtoShard or cost is not atomic"
            )

        peer.drain()
        peer.send(13787, request)
        retry_packet, _ = peer.until(13766)
        if retry_packet != success_packet:
            raise AssertionError(
                "Identical 13787 retry rerolled or changed its native response"
            )
        wallet_retry, _ = peer.until(12753)
        if wallet_retry[1] != struct.pack(">q", before - 7):
            raise AssertionError("Identification retry charged kamas a second time")
        with store.connection() as db:
            if (
                db.execute(
                    "SELECT count(*) AS n FROM inventory_socket_identification_receipts "
                    "WHERE account_id=%s AND character_id=%s AND uid=%s",
                    (account, character["id"], high_item["uid"]),
                ).fetchone()["n"]
                != 1
            ):
                raise AssertionError("Identification retry inserted another receipt")

        peer.close()
        peer = None
        generation = store.begin_session(account)
        character = store.character(account, character["id"])
        peer = _connect(store, account, character, generation)
        character = store.character(account, character["id"])
        state = _check_reconnect_bootstrap(peer, character, high_item)
        if state != success["shard"]:
            raise AssertionError("Reconnection published a different ProtoShard")
        print(
            "PASS: candidate TLS 13787→13766 status-2 level gate; successful identified UID; one 7-kama local-policy charge; identical retry; reconnect preserves field52 and vA"
        )
    finally:
        if peer is not None:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
