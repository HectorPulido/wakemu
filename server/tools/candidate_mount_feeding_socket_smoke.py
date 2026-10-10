"""Full native TLS smoke for pet feeding against a disposable candidate.

The test uses command grants only in its guarded candidate database, sends the
real 12767 body, decodes the resulting ProtoItem/ProtoPet at 12471, checks the
native model values and reconnect bootstrap, and never targets a live DB.
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
from wakfu_server.store import Store
from wakfu_server.wire import proto_fields


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


def _text(value):
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _fields(body):
    return {tag >> 3: value for tag, value in proto_fields(body)}


def _decode_pet_proto(item_proto):
    item = _fields(item_proto)
    if type(item.get(1)) is not int or type(item.get(2)) is not int:
        raise AssertionError("Native ProtoItem identity is malformed")
    mount_blob = item.get(50)
    if type(mount_blob) is not bytes:
        raise AssertionError("12471 omitted the nested ProtoPet field 50")
    pet = _fields(mount_blob)
    required = (1, 2, 5, 6, 7, 8)
    if any(field not in pet for field in required):
        raise AssertionError("Native ProtoPet omitted definition/name/HP/XP/dates")
    return item, pet


def _decode_insert(body):
    if len(body) < 15:
        raise AssertionError("Truncated native 12471 insertion")
    container, slot, size = struct.unpack_from(">qhI", body)
    start, end = 14, 14 + size
    if size <= 0 or len(body) != end + 1 or body[end] not in (0, 1):
        raise AssertionError("Malformed native 12471 ProtoItem length/notification")
    item, pet = _decode_pet_proto(body[start:end])
    return dict(container=container, slot=slot, item=item, pet=pet)


class Peer:
    def __init__(self):
        host = os.environ.get("WAKFU_MOUNT_SMOKE_HOST", "127.0.0.1")
        port = int(os.environ.get("WAKFU_MOUNT_SMOKE_PORT", "15556"))
        raw = socket.create_connection((host, port), timeout=10)
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
                raise AssertionError("Candidate closed mount-feeding TLS socket")
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
    peer.send(426, _text(ticket) + _text("isolated-mount-feeding-smoke"))
    peer.until(13873)
    peer.selection_start = len(peer.received)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    # 630/711 can arrive before the rest of the selection bootstrap. Drain
    # its trailing BAGS/registry/UID packets before requesting map entry.
    peer.drain(quiet=0.25)
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
                "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                "WHERE character_id=%s AND reference=%s ORDER BY uid LIMIT 1",
                (character_id, reference),
            ).fetchone()
        if row is not None and row["quantity"] == quantity:
            return dict(row)
        time.sleep(0.05)
    raise AssertionError(f"Candidate did not grant native item {reference}")


def _feed(peer, food, pet):
    peer.drain()
    peer.send(12767, struct.pack(">qqi", pet["uid"], food["uid"], 1))
    first, _ = peer.until(12470)
    second, _ = peer.until(12470)
    insert, _ = peer.until(12471)
    registry, _ = peer.until(13078)
    if not registry[1]:
        raise AssertionError("Feeding omitted the refreshed equipped item registry")
    food_uid, food_delta = struct.unpack(">qh", first[1])
    pet_uid, pet_delta = struct.unpack(">qh", second[1])
    if (food_uid, food_delta, pet_uid, pet_delta) != (food["uid"], -1, pet["uid"], -1):
        raise AssertionError("Feeding did not publish the native ordered UID deltas")
    refreshed = _decode_insert(insert[1])
    if (
        refreshed["item"].get(1) != pet["uid"]
        or refreshed["item"].get(2) != 18682
        or refreshed["item"].get(3) != 1
        or refreshed["container"] != pet["container"]
        or refreshed["slot"] != pet["slot"]
    ):
        raise AssertionError(
            "Refreshed ProtoItem changed pet identity or inventory slot"
        )
    return refreshed["pet"]


def _wait_receipt(store, pet_uid, count, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with store.connection() as db:
            rows = db.execute(
                "SELECT * FROM mount_feeding_receipts WHERE pet_uid=%s ORDER BY id",
                (pet_uid,),
            ).fetchall()
            state = db.execute(
                "SELECT xp,health,revision FROM inventory_mounts WHERE uid=%s",
                (pet_uid,),
            ).fetchone()
        if len(rows) == count:
            return state, rows
        time.sleep(0.05)
    raise AssertionError("Candidate feeding receipt did not commit")


def _bootstrap_pet_proto(peer, character_id, pet_uid):
    selected_packets = peer.received[getattr(peer, "selection_start", 0) :]
    rich_index = None
    for index, (opcode, body) in enumerate(selected_packets):
        if opcode != 13078 or len(body) < 13:
            continue
        owner, size, _flags = struct.unpack_from(">qIB", body)
        if owner != character_id or len(body) != 13 + size:
            continue
        for tag, item_blob in proto_fields(body[13:]):
            if tag != 10 or type(item_blob) is not bytes:
                continue
            item = _fields(item_blob)
            if item.get(1) == pet_uid:
                if type(item.get(50)) is not bytes:
                    raise AssertionError("Reconnect 13078 omitted ProtoPet field 50")
                rich_index = index
                if not any(op == 13713 for op, _ in selected_packets[:rich_index]):
                    raise AssertionError(
                        "Rich inventory registry preceded BAGS bootstrap"
                    )
                if not any(op == 13778 for op, _ in selected_packets[rich_index + 1 :]):
                    raise AssertionError(
                        "UID pool was not restored after rich inventory"
                    )
                return _fields(item[50])
    raise AssertionError("Reconnect bootstrap omitted the pet ProtoItem")


def main():
    database_url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(database_url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError("Mount-feeding smoke requires a disposable candidate database")
    store = Store(
        database_url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"]
    )
    peer = None
    try:
        account_id = store.register(
            "mount_feed_" + secrets.token_hex(5), secrets.token_urlsafe(24)
        )["id"]
        set_admin(
            store,
            account_id,
            True,
            operator="candidate-mount-feeding-smoke",
            reason="disposable native TLS test",
        )
        character = store.create_character(
            account_id,
            "Feed Smoke "
            + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(5)),
            breed=8,
        )
        generation = store.begin_session(account_id, ttl=600)
        peer = _connect(store, account_id, character, generation)

        # 18682 is the native Dragopavo item/model76; model76 earns 50 XP per
        # YI food and has 20 max health. Grants occur only in this candidate DB.
        _command(peer, "!item 18682 1")
        pet = _wait_item(store, character["id"], 18682, 1)
        # Freshly created mount fixtures are born with a current meal date,
        # which correctly blocks XP food for the rest of that UTC day. This
        # smoke explicitly prepares an eligible preexisting mount state.
        with store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET last_meal_date=0 WHERE uid=%s",
                (pet["uid"],),
            )
        _command(peer, "!item 18378 2")  # Pienso universal: native XP food.
        xp_food = _wait_item(store, character["id"], 18378, 2)
        peer.drain()

        xp_pet = _feed(peer, xp_food, pet)
        if xp_pet.get(5) != 20 or xp_pet.get(6) != 50:
            raise AssertionError("Native ProtoPet did not publish health20 / XP50")
        state, receipts = _wait_receipt(store, pet["uid"], 1)
        if (state["xp"], state["health"], state["revision"]) != (50, 20, 1):
            raise AssertionError(
                "Durable XP feeding state differs from ProtoPet publication"
            )
        if receipts[0]["effect_kind"] != "xp" or receipts[0]["xp_delta"] != 50:
            raise AssertionError("XP receipt does not match native model76 meal values")

        # The same body is indistinguishable from a transport retry inside the
        # configured debounce. It emits no additive packet and makes no receipt.
        peer.send(12767, struct.pack(">qqi", pet["uid"], xp_food["uid"], 1))
        time.sleep(0.25)
        duplicate_packets = peer.drain()
        if any(opcode in (12470, 12471, 13078) for opcode, _ in duplicate_packets):
            raise AssertionError("Duplicate XP body unexpectedly republished packets")
        _wait_receipt(store, pet["uid"], 1)

        # After the non-native debounce expires, an identical second request
        # on the same UTC date must still fail the native daily XP gate.
        time.sleep(3.4)
        peer.send(12767, struct.pack(">qqi", pet["uid"], xp_food["uid"], 1))
        _info, rejected_packets = peer.until(349)
        if any(opcode in (12470, 12471) for opcode, _ in rejected_packets):
            raise AssertionError("Same-day XP rejection changed or refreshed inventory")
        with store.connection() as db:
            remaining_food = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (xp_food["uid"],)
            ).fetchone()
        if remaining_food is None or remaining_food["quantity"] != 1:
            raise AssertionError("Same-day XP rejection consumed the remaining food")
        _wait_receipt(store, pet["uid"], 1)

        # Reproduce missing HP only in this disposable candidate database.
        with store.connection() as db:
            db.execute(
                "UPDATE inventory_mounts SET health=0 WHERE uid=%s", (pet["uid"],)
            )
        _command(peer, "!item 12284 1")  # Polvos de Osamodas: YJ=1.
        heal_one = _wait_item(store, character["id"], 12284, 1)
        heal_pet = _feed(peer, heal_one, pet)
        if heal_pet.get(5) != 1 or heal_pet.get(6) != 50:
            raise AssertionError("YJ=1 heal or preserved XP was missing from ProtoPet")
        state, receipts = _wait_receipt(store, pet["uid"], 2)
        if (state["xp"], state["health"], state["revision"]) != (50, 1, 2):
            raise AssertionError(
                "Durable YJ=1 healing differs from ProtoPet publication"
            )
        if receipts[1]["effect_kind"] != "heal" or receipts[1]["health_delta"] != 1:
            raise AssertionError("YJ=1 healing receipt is incorrect")

        _command(peer, "!item 18377 1")  # Pienso real de vitalidad: YJ=20.
        heal_twenty = _wait_item(store, character["id"], 18377, 1)
        heal_pet = _feed(peer, heal_twenty, pet)
        if heal_pet.get(5) != 20 or heal_pet.get(6) != 50:
            raise AssertionError("YJ=20 heal or preserved XP was missing from ProtoPet")
        state, receipts = _wait_receipt(store, pet["uid"], 3)
        if (state["xp"], state["health"], state["revision"]) != (50, 20, 3):
            raise AssertionError(
                "Durable YJ=20 healing differs from ProtoPet publication"
            )
        if receipts[2]["effect_kind"] != "heal" or receipts[2]["health_delta"] != 19:
            raise AssertionError("YJ=20 healing did not clamp to missing health")

        peer.close()
        peer = None
        generation = store.begin_session(account_id, ttl=600)
        peer = _connect(store, account_id, character, generation)
        reopened = _bootstrap_pet_proto(peer, character["id"], pet["uid"])
        if reopened.get(5) != 20 or reopened.get(6) != 50:
            raise AssertionError(
                "Reconnect 13078 did not hydrate durable ProtoPet HP/XP"
            )
        state, receipts = _wait_receipt(store, pet["uid"], 3)
        if (state["xp"], state["health"], state["revision"]) != (50, 20, 3):
            raise AssertionError("Reconnect changed durable pet state or receipts")
        print(
            "PASS: TLS 12767 XP50; 12284/YJ1 and 18377/YJ20 healing; "
            "12470→12470→12471 ProtoPet refresh; receipt replay; 13078 reconnect"
        )
    finally:
        if peer is not None:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
