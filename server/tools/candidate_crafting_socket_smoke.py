"""Exercise native crafting packets against one disposable candidate world.

Run inside an isolated candidate container with stdin. The database guard
rejects every database except ``wakemu_candidate_smoke_*``.
"""
import os
import secrets
import socket
import ssl
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server import inventory_items
from wakfu_server.craft_station import resolve_current
from wakfu_server.inventory_move import STACKS
from wakfu_server.items.craft_catalog import load_catalog
from wakfu_server.profession_store import ensure_learned
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
        self.socket.settimeout(35)

    def send(self, opcode, body=b""):
        self.socket.sendall(_frame(opcode, body))

    def exact(self, size):
        output = bytearray()
        while len(output) < size:
            chunk = self.socket.recv(size - len(output))
            if not chunk:
                raise AssertionError("World closed the crafting smoke socket")
            output.extend(chunk)
        return bytes(output)

    def receive(self):
        size = struct.unpack(">I", self.exact(4))[0]
        if not 6 <= size <= 327670:
            raise AssertionError("Invalid native server frame size")
        frame = self.exact(size - 4)
        return struct.unpack_from(">H", frame)[0], frame[2:]

    def until(self, *opcodes):
        wanted = set(opcodes)
        deadline = time.monotonic() + 40
        seen = []
        while time.monotonic() < deadline:
            packet = self.receive()
            seen.append(packet)
            if packet[0] in wanted:
                return packet, seen
        raise AssertionError(f"Missing candidate packet among {sorted(wanted)}")

    def close(self):
        self.socket.close()


def _connect(store, account_id, generation, ticket, character):
    peer = Peer()
    peer.send(426, _text(ticket) + _text("isolated-crafting-smoke"))
    peer.until(13873)
    peer.send(23664, struct.pack(">q", character["id"]) + _text(character["name"]))
    peer.until(630)
    peer.until(711)
    peer.send(12449)
    (_, join_body), join_packets = peer.until(12436)
    return peer, join_packets


def _wait_canceled(store, account_id, character_id, expected):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        _, _, states = _totals(store, account_id, character_id)
        if states.get("canceled", 0) >= expected:
            return
        time.sleep(0.05)
    raise AssertionError("Craft movement/cancel did not terminate the occupation")


def _complete(peer, batch, duration_ms):
    peer.send(13429, b"\x02\x00\x08")
    seen = []
    received = set()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not {13479, 12916}.issubset(received):
        packet = peer.receive()
        seen.append(packet)
        received.add(packet[0])
    if not {13479, 12916}.issubset(received):
        raise AssertionError("Native craft result or profession XP packet missing")
    result = next(body for opcode, body in seen if opcode == 13479)
    xp_packet = next(body for opcode, body in seen if opcode == 12916)
    if (
        len(result) != 7
        or result[0] != 0
        or struct.unpack_from(">h", result, 5)[0] != batch
    ):
        raise AssertionError("Native crafting result did not report the expected batch")
    if len(xp_packet) < 8:
        raise AssertionError("Malformed native profession XP packet")
    return seen


def _totals(store, account_id, character_id):
    with store.connection() as db:
        items = {
            row["reference"]: row["quantity"]
            for row in db.execute(
                "SELECT reference,sum(quantity)::integer AS quantity "
                "FROM inventory_items WHERE character_id=%s GROUP BY reference",
                (character_id,),
            )
        }
        profession = db.execute(
            "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=73",
            (account_id,),
        ).fetchone()
        occupations = db.execute(
            "SELECT state,count(*)::integer AS count FROM craft_occupations "
            "WHERE character_id=%s GROUP BY state",
            (character_id,),
        ).fetchall()
    return (
        items,
        None if profession is None else profession["xp"],
        {row["state"]: row["count"] for row in occupations},
    )


def main():
    url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError("Crafting socket smoke requires the disposable candidate DB")
    store = Store(url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    peer = None
    try:
        account = store.register(
            "craftsmoke_" + secrets.token_hex(4), secrets.token_urlsafe(24)
        )
        account_id = account["id"]
        character = store.create_character(
            account_id,
            "Craft Smoke " + "".join(secrets.choice("abcdef") for _ in range(5)),
        )
        character_id = character["id"]
        generation = store.begin_session(account_id)
        store.select_character(account_id, generation, character_id)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-19,y=10,z=-4 "
                "WHERE id=%s AND account_id=%s",
                (character_id, account_id),
            )
        character = store.character(account_id, character_id)
        station = resolve_current(character, 31515)
        if station["profession_id"] != 73:
            raise AssertionError("Native table profession did not resolve")
        ensure_learned(store, account_id, generation, character_id, [73])

        catalog = load_catalog()
        recipe = catalog.recipes[2475]
        if not catalog.authorize_recipe(113, 2475, profession_id=73):
            raise AssertionError(
                "Candidate recipe is not in the native table allowlist"
            )
        container = character["inventory_containers"][0]["uid"]
        for slot, ingredient in enumerate(recipe["ingredients"], start=1):
            inventory_items.grant(
                store,
                account_id,
                generation,
                character_id,
                reference=ingredient["item_id"],
                quantity=ingredient["quantity"] * 3,
                container=container,
                slot=slot,
                allowed_references=set(STACKS),
            )
        before_items, before_xp, _ = _totals(store, account_id, character_id)
        if before_xp is None:
            raise AssertionError("Native profession learning did not persist")

        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer, _ = _connect(store, account_id, generation, ticket, character)

        ordinary_request = struct.pack(">qii", 31515, 2475, 1)
        peer.send(12231, ordinary_request)
        (opcode, started), _ = peer.until(13989)
        if opcode != 13989 or struct.unpack(">qibqq", started) != (
            31515,
            2475,
            0,
            1000,
            0,
        ):
            raise AssertionError("Native 13989 craft occupation start mismatch")
        peer.send(13429, b"\x03\x00\x08")
        _wait_canceled(store, account_id, character_id, 1)
        canceled_items, canceled_xp, _ = _totals(store, account_id, character_id)
        if (canceled_items, canceled_xp) != (before_items, before_xp):
            raise AssertionError(
                "Canceled occupation changed materials or profession XP"
            )

        # A real outside-combat 13331 step must also release an occupation.
        peer.send(12231, ordinary_request)
        (_, started), _ = peer.until(13989)
        if struct.unpack(">qibqq", started)[3] != 1000:
            raise AssertionError("Unexpected movement-cancel test duration")
        peer.send(13331, struct.pack(">iiihBB", 0, -19, 10, -4, 1, 7 << 5))
        peer.until(12789, 13948)
        _wait_canceled(store, account_id, character_id, 2)
        moved_items, moved_xp, _ = _totals(store, account_id, character_id)
        if (moved_items, moved_xp) != (before_items, before_xp):
            raise AssertionError("Movement-canceled craft changed materials or XP")
        peer.send(13331, struct.pack(">iiihBB", 0, -19, 9, -4, 1, 3 << 5))
        peer.until(12789, 13948)

        peer.send(12231, ordinary_request)
        (_, started), _ = peer.until(13989)
        duration = struct.unpack(">qibqq", started)[3]
        time.sleep(duration / 1000 + 0.15)
        peer.send(13429, b"\x02\x00\x08")
        _complete(peer, batch=1, duration_ms=duration)

        after_items, after_xp, states = _totals(store, account_id, character_id)
        if after_xp - before_xp != 200 or states.get("completed") != 1:
            raise AssertionError("Crafting did not durably award XP and completion")
        for ingredient in recipe["ingredients"]:
            reference = ingredient["item_id"]
            if (
                after_items.get(reference, 0)
                != before_items.get(reference, 0) - ingredient["quantity"]
            ):
                raise AssertionError(
                    "Crafting did not consume its exact native ingredients"
                )
        product = recipe["products"][0]
        if after_items.get(product["item_id"], 0) < product["quantity"]:
            raise AssertionError("Crafting did not grant the native recipe product")

        # The tokenless completion request is safely replayed as absolute
        # inventory/profession snapshots. It cannot award the delta twice.
        peer.send(13429, b"\x02\x00\x08")
        replay_packets = []
        replayed = set()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not {13713, 13873}.issubset(replayed):
            packet = peer.receive()
            replay_packets.append(packet)
            replayed.add(packet[0])
        if not {13713, 13873}.issubset(replayed):
            raise AssertionError("Craft completion replay omitted absolute snapshots")
        if any(opcode == 12916 for opcode, _ in replay_packets):
            raise AssertionError("Craft completion replay repeated XP delta")
        if _totals(store, account_id, character_id)[:2] != (after_items, after_xp):
            raise AssertionError("Craft completion retry duplicated durable rewards")

        peer.close()
        peer = None
        generation = store.begin_session(account_id)
        store.select_character(account_id, generation, character_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer, _ = _connect(store, account_id, generation, ticket, character)
        (_, profession_snapshot), _ = peer.until(13873)
        if not profession_snapshot:
            raise AssertionError(
                "Reconnect bootstrap omitted absolute profession state"
            )
        if _totals(store, account_id, character_id)[:2] != (after_items, after_xp):
            raise AssertionError("Reconnect changed durable crafting rewards")

        batch = 2
        occupation_body = struct.pack(">qib", 31515, 2475, 0) + b"".join(
            struct.pack(">ih", item["item_id"], item["quantity"] * batch)
            for item in recipe["ingredients"]
        )
        peer.send(13382, occupation_body)
        (_, started), _ = peer.until(13989)
        table, recipe_id, mode, duration, extra = struct.unpack(">qibqq", started)
        if (table, recipe_id, mode, duration, extra) != (31515, 2475, 0, 2000, 0):
            raise AssertionError(
                "13382 batch2 occupation did not use sequential 2-second timing"
            )
        time.sleep(duration / 1000 + 0.15)
        _complete(peer, batch=2, duration_ms=duration)
        final_items, final_xp, states = _totals(store, account_id, character_id)
        if final_xp - after_xp != 400 or states.get("completed") != 2:
            raise AssertionError("13382 batch2 did not award exactly 400 XP")
        for ingredient in recipe["ingredients"]:
            reference = ingredient["item_id"]
            if (
                final_items.get(reference, 0)
                != before_items.get(reference, 0) - 3 * ingredient["quantity"]
            ):
                raise AssertionError(
                    "13382 batch2 did not consume exact component totals"
                )
        if final_items.get(product["item_id"], 0) != 3 * product["quantity"]:
            raise AssertionError("13382 batch2 did not grant exact product quantity")
        print(
            "PASS: TLS craft cancellation + movement cancel, 12231 completion/replay/reconnect, 13382 batch2 (2000ms/400 XP)"
        )
    finally:
        if peer is not None:
            peer.close()
        store.close()


if __name__ == "__main__":
    main()
