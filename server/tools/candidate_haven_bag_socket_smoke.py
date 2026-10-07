"""Exercise native haven-bag gem transfers over TLS in a disposable candidate.

Run inside the isolated candidate container with this file supplied on stdin.
It creates one temporary admin account only in the candidate database.
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
from wakfu_server.inventory import bags
from wakfu_server.store import Store


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
                raise AssertionError("Candidate closed the haven-bag TLS socket")
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

    def collect(self, required, timeout=20):
        remaining = set(required)
        seen = []
        deadline = time.monotonic() + timeout
        while remaining and time.monotonic() < deadline:
            packet = self.receive()
            seen.append(packet)
            remaining.discard(packet[0])
        if remaining:
            raise AssertionError(
                f"Candidate transfer omitted packets {sorted(remaining)}"
            )
        return seen

    def drain(self, quiet=0.15):
        """Consume already-published bootstrap/console packets between actions."""
        packets = []
        while self.socket.pending() or select.select([self.socket], [], [], quiet)[0]:
            packets.append(self.receive())
        return packets

    def close(self):
        self.socket.close()


def _connect(store, account_id, generation, ticket, character):
    peer = Peer()
    peer.send(426, _text(ticket) + _text("isolated-haven-bag-gem-smoke"))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    peer.send(12449)
    peer.until(12436)
    peer.until(711)
    peer.send(12449)
    peer.until(711)
    peer.drain()
    return peer


def _console_item(peer, reference, quantity):
    command = f"!item {reference} {quantity}".encode("ascii")
    peer.send(12366, struct.pack(">H", len(command)) + command)


def _wait_item(store, character_id, reference, expected_quantity, *, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with store.connection() as db:
            row = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s "
                "AND reference=%s ORDER BY uid LIMIT 1",
                (character_id, reference),
            ).fetchone()
        if row is not None and row["quantity"] == expected_quantity:
            return dict(row)
        time.sleep(0.05)
    raise AssertionError("Candidate test-console item grant did not commit")


def _room_snapshot(body, account_id, character_id):
    if len(body) < 18:
        raise AssertionError("Truncated native haven-bag snapshot")
    owner_account, owner_character, name_length = struct.unpack_from(">qqH", body)
    if (owner_account, owner_character) != (account_id, character_id):
        raise AssertionError("Haven-bag snapshot belongs to another owner")
    offset = 18 + name_length
    if len(body) < offset + 19:
        raise AssertionError("Truncated native haven-bag room header")
    _, _, _, room_count = struct.unpack_from(">qhqB", body, offset)
    offset += 19
    rooms = {}
    for _ in range(room_count):
        if len(body) < offset + 3:
            raise AssertionError("Truncated native haven-bag room")
        room_index, furniture_count = struct.unpack_from(">BH", body, offset)
        offset += 3
        if furniture_count:
            raise AssertionError("Smoke snapshot unexpectedly contains furniture")
        if len(body) < offset + 26:
            raise AssertionError("Truncated native haven-bag gem record")
        (
            discriminator,
            enabled,
            primary_ref,
            primary_uid,
            secondary_ref,
            secondary_uid,
        ) = struct.unpack_from(">BBiqiq", body, offset)
        if discriminator != 0:
            raise AssertionError("Unexpected native haven-bag room discriminator")
        rooms[room_index] = {
            "enabled": bool(enabled),
            "primary": (primary_ref, primary_uid),
            "secondary": (secondary_ref, secondary_uid),
        }
        offset += 26
    return rooms


def _assert_committed(
    store,
    account_id,
    character_id,
    source_uid,
    source_quantity,
    installed_uid,
    room,
    primary,
    reference,
):
    with store.connection() as db:
        source = db.execute(
            "SELECT quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
            (source_uid, character_id),
        ).fetchone()
        installed = db.execute(
            "SELECT reference,room_index,primary_slot FROM haven_bag_gems "
            "WHERE uid=%s AND account_id=%s AND character_id=%s",
            (installed_uid, account_id, character_id),
        ).fetchone()
        all_rows = db.execute(
            "SELECT uid,reference,quantity FROM inventory_items WHERE character_id=%s",
            (character_id,),
        ).fetchall()
        layout = db.execute(
            "SELECT layout FROM haven_bags WHERE character_id=%s", (character_id,)
        ).fetchone()["layout"]
    if source_quantity is None:
        if source is not None:
            raise AssertionError("Unit gem UID was left duplicated in inventory")
    elif source is None or source["quantity"] != source_quantity:
        raise AssertionError("Stack quantity does not match the committed transfer")
    if (
        installed is None
        or installed["reference"] != reference
        or installed["room_index"] != room
        or installed["primary_slot"] is not primary
    ):
        raise AssertionError("Haven-bag gem ownership row is incorrect")
    if any(row["uid"] == installed_uid for row in all_rows):
        raise AssertionError("Installed gem UID is also present in inventory")
    room_row = next(row for row in layout if row["index"] == room)
    slot = "primary" if primary else "secondary"
    if (room_row[f"{slot}_ref"], room_row[f"{slot}_uid"]) != (reference, installed_uid):
        raise AssertionError("Room layout does not match its installed gem record")


def main():
    url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Haven-bag socket smoke requires a disposable candidate database"
        )
    store = Store(url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    peer = None
    try:
        account = store.register(
            "bag_gem_smoke_" + secrets.token_hex(5), secrets.token_urlsafe(24)
        )
        account_id = account["id"]
        set_admin(
            store,
            account_id,
            True,
            operator="candidate-haven-bag-smoke",
            reason="disposable socket test",
        )
        character = store.create_character(
            account_id,
            "Bag Gem "
            + "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(7)),
            breed=8,
        )
        character_id = character["id"]
        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = _connect(store, account_id, generation, ticket, character)

        # Exercise the already-supported elemental-selection response over
        # the real candidate TLS dispatcher. Reference 2869 accepts three
        # damage elements; the fixed native mask 26 is WATER+EARTH+AIR. This
        # does not invoke socket generation/13787 or consume RNG.
        _console_item(peer, 2869, 1)
        element_item = _wait_item(store, character_id, 2869, 1)
        peer.drain()
        peer.send(12487, struct.pack(">qBB", element_item["uid"], 26, 0))
        _, element_packets = peer.until(13766)
        expected_element_result = (
            struct.pack(">iqBI", 0, element_item["uid"], 0, 2)
            + bytes((26, 0))
            + struct.pack(">I", 0)
        )
        actual_element_result = next(
            body for opcode, body in element_packets if opcode == 13766
        )
        if actual_element_result != expected_element_result:
            raise AssertionError(
                "13766 elemental result differs from its native byte layout"
            )
        with store.connection() as db:
            selected = db.execute(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements "
                "WHERE uid=%s",
                (element_item["uid"],),
            ).fetchone()
        if selected is None or (
            selected["damage_elements"],
            selected["resistance_elements"],
        ) != (26, 0):
            raise AssertionError(
                "Candidate did not persist the selected elemental masks"
            )

        # A decor gem stack exercises a distinct server-allocated UID before
        # native 12234 consumes the one-unit temporary inventory item.
        _console_item(peer, 4263, 3)
        source = _wait_item(store, character_id, 4263, 3)
        peer.drain()
        _console_item(peer, 4262, 1)
        commerce = _wait_item(store, character_id, 4262, 1)
        peer.drain()
        container = character["inventory_containers"][0]["uid"]

        peer.send(13578, struct.pack(">q", 0))
        _, entry_packets = peer.until(13974)
        entry = next((body for opcode, body in entry_packets if opcode == 13307), None)
        if entry is None or entry[:2] != b"\x01\x01":
            raise AssertionError("Candidate did not enter its own haven bag")
        peer.drain()

        peer.send(12177, struct.pack(">qBB", source["uid"], 1, 0))
        split_packets = peer.collect((12470, 12471, 12234))
        split_delta = next(body for opcode, body in split_packets if opcode == 12470)
        split_insert = next(body for opcode, body in split_packets if opcode == 12471)
        installed_uid, installed_room = struct.unpack(
            ">qB", next(body for opcode, body in split_packets if opcode == 12234)
        )
        if split_delta != struct.pack(">qh", source["uid"], -1):
            raise AssertionError(
                "Candidate emitted an incorrect one-unit stack decrement"
            )
        container_uid, temp_slot, proto_size = struct.unpack_from(">qhI", split_insert)
        if (
            container_uid != container
            or len(split_insert) != 14 + proto_size + 1
            or split_insert[-1:] != b"\x00"
        ):
            raise AssertionError(
                "Candidate split insertion packet has invalid native framing"
            )
        from wakfu_server.wire import proto_fields

        fields = dict(proto_fields(split_insert[14 : 14 + proto_size]))
        if installed_room != 1 or fields.get(8) != installed_uid:
            raise AssertionError("12234 did not name its resolvable unit UID")
        _assert_committed(
            store,
            account_id,
            character_id,
            source["uid"],
            2,
            installed_uid,
            1,
            True,
            4263,
        )
        if temp_slot >= 30:
            raise AssertionError(
                "Split unit was placed outside the native inventory capacity"
            )

        # Duplicate insert retry must not consume the stack again or allocate a
        # second durable gem. The native body has no nonce; current room state
        # makes the identical source UID/room request a no-op.
        peer.send(12177, struct.pack(">qBB", source["uid"], 1, 0))
        _, retry_packets = peer.until(12234)
        if struct.unpack(">qB", retry_packets[-1][1]) != (installed_uid, 1):
            raise AssertionError(
                "Insertion retry did not return the existing installed UID"
            )
        _assert_committed(
            store,
            account_id,
            character_id,
            source["uid"],
            2,
            installed_uid,
            1,
            True,
            4263,
        )
        peer.drain()

        # The existing base gem remains primary; a commerce gem is secondary.
        peer.send(12177, struct.pack(">qBB", commerce["uid"], 0, 0))
        _, secondary_packets = peer.until(12234)
        if struct.unpack(">qB", secondary_packets[0][1]) != (commerce["uid"], 0):
            raise AssertionError("Secondary gem ACK used a wrong room or UID")
        with store.connection() as db:
            layout = db.execute(
                "SELECT layout FROM haven_bags WHERE character_id=%s", (character_id,)
            ).fetchone()["layout"]
        entrance = next(row for row in layout if row["index"] == 0)
        if (entrance["primary_ref"], entrance["primary_uid"]) != (
            4262,
            character_id * 256 + 1,
        ):
            raise AssertionError(
                "Fixed entrance gem changed during secondary insertion"
            )
        _assert_committed(
            store,
            account_id,
            character_id,
            commerce["uid"],
            None,
            commerce["uid"],
            0,
            False,
            4262,
        )
        peer.drain()

        # A byte-exact attempt to remove room 0's fixed primary is rejected
        # with the authoritative config only, never a transfer success ACK.
        occupied_slot = 2
        peer.send(13090, struct.pack(">qBBB", container, occupied_slot, 0, 1))
        _, protected_packets = peer.until(12187)
        if any(opcode == 12451 for opcode, _ in protected_packets):
            raise AssertionError(
                "Candidate reported success for the fixed entrance gem removal"
            )
        peer.drain()

        # Exit and reconnect while both physical gem slots are occupied. The
        # persisted room snapshot after reentry must contain both same UIDs.
        peer.send(12247, b"\x00")
        peer.until(13974)
        peer.close()
        peer = None
        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = _connect(store, account_id, generation, ticket, character)
        peer.send(13578, struct.pack(">q", 0))
        _, reentry_packets = peer.until(13974)
        if not any(
            opcode == 13307 and body[:2] == b"\x01\x01"
            for opcode, body in reentry_packets
        ):
            raise AssertionError("Candidate reconnect did not reenter the private bag")
        peer.drain()
        # Invalid rearrange is a nonmutating way to request native owner config.
        peer.send(13210, b"\x00")
        _, snapshot_packets = peer.until(12187)
        snapshot = _room_snapshot(snapshot_packets[0][1], account_id, character_id)
        if snapshot[1]["primary"] != (4263, installed_uid):
            raise AssertionError("Reconnect snapshot lost the primary inserted gem")
        if snapshot[0]["secondary"] != (4262, commerce["uid"]):
            raise AssertionError("Reconnect snapshot lost the secondary inserted gem")
        peer.drain()

        # Restore both units through their respective selectors.
        peer.send(13090, struct.pack(">qBBB", container, occupied_slot, 0, 0))
        _, secondary_remove = peer.until(12451)
        if secondary_remove[0][1] != struct.pack(
            ">qBBB", container, occupied_slot, 0, 0
        ):
            raise AssertionError(
                "Secondary removal ACK did not preserve destination/selector"
            )
        peer.drain()
        peer.send(13090, struct.pack(">qBBB", container, occupied_slot + 1, 1, 1))
        _, primary_remove = peer.until(12451)
        if primary_remove[0][1] != struct.pack(
            ">qBBB", container, occupied_slot + 1, 1, 1
        ):
            raise AssertionError(
                "Primary removal ACK did not preserve destination/selector"
            )

        # Removing the now-empty slot again is harmless and cannot grant a
        # second copy. It returns config, not a false 12451 success.
        peer.drain()
        peer.send(13090, struct.pack(">qBBB", container, occupied_slot + 2, 1, 1))
        _, empty_retry = peer.until(12187)
        if any(opcode == 12451 for opcode, _ in empty_retry):
            raise AssertionError("Empty-slot retry fabricated a removal success")
        with store.connection() as db:
            remaining_gems = db.execute(
                "SELECT count(*) AS n FROM haven_bag_gems WHERE character_id=%s",
                (character_id,),
            ).fetchone()["n"]
            inventory = db.execute(
                "SELECT reference,sum(quantity)::integer AS quantity FROM inventory_items "
                "WHERE character_id=%s GROUP BY reference",
                (character_id,),
            ).fetchall()
        totals = {row["reference"]: row["quantity"] for row in inventory}
        if remaining_gems != 0 or totals.get(4263) != 3 or totals.get(4262) != 1:
            raise AssertionError(
                "Final inventory/layout totals do not conserve both gems"
            )

        print(
            "PASS: candidate TLS 12487/13766 elements; 12177/12234 stack split + secondary; 13090/12451 primary/secondary; protected room0, retry and reconnect; no 13787"
        )
    finally:
        if peer is not None:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
