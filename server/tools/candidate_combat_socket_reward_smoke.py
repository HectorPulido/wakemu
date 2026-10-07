"""Complete one native TLS fight through the disposable candidate world server.

Run with ``python3 -`` inside wakemu-reward-smoke-* after migrations. This
creates a disposable admin account only in the candidate database; it never
connects to the live game service.
"""
import os
import secrets
import socket
import ssl
import struct
import time

from psycopg.conninfo import conninfo_to_dict
from wakfu_server.command_permissions import set_admin
from wakfu_server.monsters import reference as monster_reference
from wakfu_server.store import Store


def _varint(data, offset):
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise AssertionError("Malformed protobuf varint")


def _fields(data):
    rows = []
    offset = 0
    while offset < len(data):
        tag, offset = _varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if number <= 0:
            raise AssertionError("Invalid protobuf field number")
        if wire == 0:
            value, offset = _varint(data, offset)
        elif wire == 2:
            size, offset = _varint(data, offset)
            end = offset + size
            if end > len(data):
                raise AssertionError("Truncated protobuf field")
            value = data[offset:end]
            offset = end
        else:
            raise AssertionError("Unexpected fight-report wire type")
        rows.append((number, wire, value))
    return rows


def _one(rows, field, wire):
    matches = [
        value for number, kind, value in rows if number == field and kind == wire
    ]
    if len(matches) != 1:
        raise AssertionError("Unexpected native fight report layout")
    return matches[0]


def _text(value):
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _frame(opcode, body=b""):
    return struct.pack(">IBH", 7 + len(body), 3, opcode) + body


class Peer:
    def __init__(self):
        raw = socket.create_connection(("127.0.0.1", 15556), timeout=10)
        self.socket = ssl._create_unverified_context().wrap_socket(
            raw, server_hostname="localhost"
        )
        # Test-console !mob may await candidate-world SQL/map publication under
        # cold startup, so leave enough time for the isolated socket workflow.
        self.socket.settimeout(60)
        self.received = []

    def send(self, opcode, body=b""):
        self.socket.sendall(_frame(opcode, body))

    def exact(self, size):
        result = bytearray()
        while len(result) < size:
            chunk = self.socket.recv(size - len(result))
            if not chunk:
                raise AssertionError("World socket closed before fight completion")
            result.extend(chunk)
        return bytes(result)

    def receive(self):
        size = struct.unpack(">I", self.exact(4))[0]
        if not 6 <= size <= 327670:
            raise AssertionError("Invalid native server frame length")
        frame = self.exact(size - 4)
        packet = struct.unpack_from(">H", frame)[0], frame[2:]
        self.received.append(packet)
        return packet

    def until(self, *opcodes):
        seen = []
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            opcode, body = self.receive()
            seen.append((opcode, body))
            if opcode in opcodes:
                return opcode, body, seen
        raise AssertionError("Timed out waiting for candidate world packet")


def _spawned_actors(body):
    """Decode every actor in a native 12608 world group packet."""
    if len(body) < 2 or body[0] != 0 or body[1] == 0:
        raise AssertionError(
            "Unexpected native 12608 group packet: "
            f"length={len(body)} prefix={body[:48].hex()}"
        )
    count = body[1]
    offset = 2
    actors = []
    for _ in range(count):
        if len(body) - offset < 11:
            raise AssertionError("Truncated native monster group member")
        actor_type = body[offset]
        actor_id = struct.unpack_from(">q", body, offset + 1)[0]
        size = struct.unpack_from(">H", body, offset + 9)[0]
        offset += 11
        actor = body[offset : offset + size]
        if len(actor) != size or not actor or actor[0] != 11:
            raise AssertionError("Malformed native monster appearance")
        name_size = struct.unpack_from(">H", actor, 18)[0]
        actor_offset = 20 + name_size
        reference = struct.unpack_from(">h", actor, actor_offset)[0]
        x, y, z = struct.unpack_from(">iih", actor, actor_offset + 2)
        actors.append(
            dict(
                id=actor_id,
                actor_type=actor_type,
                reference=reference,
                position=(x, y, z),
            )
        )
        offset += size
    if offset != len(body):
        raise AssertionError("Trailing bytes in native monster group packet")
    return actors


def _spawned_actor(body):
    actors = _spawned_actors(body)
    if len(actors) != 1:
        raise AssertionError(f"Expected one test monster, received {len(actors)}")
    return actors[0]


def _placement_positions(body):
    if len(body) < 7:
        raise AssertionError("Truncated native combat placement positions")
    fight_id, count = struct.unpack_from(">ih", body)
    expected = 6 + count * 18 + 1
    if count < 2 or len(body) != expected:
        raise AssertionError("Malformed native combat placement positions")
    actors = {}
    offset = 6
    for _ in range(count):
        actor_id, x, y, z = struct.unpack_from(">qiih", body, offset)
        actors[actor_id] = (x, y, z)
        offset += 18
    return fight_id, actors


def _report(fight_id, body):
    if len(body) < 12 or struct.unpack_from(">i", body)[0] != fight_id:
        raise AssertionError("Fight report belongs to another fight")
    report = _fields(body[12:])
    if _one(report, 1, 0) != fight_id or _one(report, 4, 0) != 0:
        raise AssertionError("Fight report does not record a player victory")
    team = _fields(_one(report, 5, 2))
    player = _fields(_one(team, 2, 2))
    xp = _fields(_one(player, 8, 2))
    loots = []
    for number, wire, value in player:
        if number == 7 and wire == 2:
            loot = _fields(value)
            loots.append((_one(loot, 1, 0), _one(loot, 2, 0)))
    return {
        "character_id": _one(player, 1, 0),
        "won_xp": _one(xp, 2, 0),
        "kamas": _one(player, 9, 0),
        "loots": loots,
    }


def _seed_receipt_backed_temporary(store, fight_id, character_id, reference, quantity):
    """Add a valid temporary-inventory fixture to this disposable DB.

    Combat drops in the frozen native catalog contain no shard-recyclable
    references. This helper creates the same award → attempt → delivery → temp
    receipt chain used by production, allowing socket coverage of 13447/12561
    without inventing an item template or touching a non-candidate database.
    """
    with store.connection() as db:
        if (
            db.execute(
                "SELECT 1 FROM fight_drop_awards WHERE fight_id=%s AND character_id=%s",
                (fight_id, character_id),
            ).fetchone()
            is None
        ):
            raise AssertionError("Fixture requires a committed drop award")
        ordinal = db.execute(
            "SELECT count(*) AS n FROM fight_drop_attempt_receipts "
            "WHERE fight_id=%s AND character_id=%s AND defeated_actor_id=-900000001",
            (fight_id, character_id),
        ).fetchone()["n"]
        actor_id = -900000001
        drop_index = ordinal
        db.execute(
            "INSERT INTO fight_drop_attempt_receipts "
            "(fight_id,character_id,defeated_actor_id,monster_reference,drop_row_index,attempt_index,"
            "item_reference,success,quantity,quantity_min,quantity_max,base_probability,raw_probability,"
            "effective_probability,draw_numerator,quantity_draw_numerator,roll_count,native_roll_max,"
            "native_min_prospection) VALUES(%s,%s,%s,4196,%s,0,%s,true,%s,%s,%s,1,1,1,0,0,1,100,0)",
            (
                fight_id,
                character_id,
                actor_id,
                drop_index,
                reference,
                quantity,
                quantity,
                quantity,
            ),
        )
        db.execute(
            "INSERT INTO fight_drop_delivery_receipts "
            "(fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index,item_reference,"
            "awarded_quantity,inventory_quantity,temporary_quantity) "
            "VALUES(%s,%s,%s,%s,0,%s,%s,0,%s)",
            (
                fight_id,
                character_id,
                actor_id,
                drop_index,
                reference,
                quantity,
                quantity,
            ),
        )
        return db.execute(
            "INSERT INTO temporary_combat_items(character_id,reference,quantity,fight_id,"
            "defeated_actor_id,drop_row_index,attempt_index) VALUES(%s,%s,%s,%s,%s,%s,0) "
            "RETURNING uid",
            (character_id, reference, quantity, fight_id, actor_id, drop_index),
        ).fetchone()["uid"]


def main():
    url = os.environ["WAKFU_DATABASE_URL"]
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError(
            "Socket fight smoke requires the disposable candidate database"
        )
    store = Store(url, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    peer = None
    try:
        account = store.register(
            "socket_reward_" + secrets.token_hex(5), secrets.token_urlsafe(24)
        )
        account_id = account["id"]
        set_admin(
            store,
            account_id,
            True,
            operator="candidate-smoke",
            reason="isolated socket fight",
        )
        name = "Socket " + "".join(
            secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)
        )
        character = store.create_character(account_id, name, breed=8)
        character_id = character["id"]
        with store.connection() as db:
            containers = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s "
                "AND kind IN (0,1,2,3) ORDER BY uid",
                (character_id,),
            ).fetchall()
            for container in containers:
                occupied = {
                    row["slot"]
                    for row in db.execute(
                        "SELECT slot FROM inventory_items WHERE container=%s",
                        (container["uid"],),
                    ).fetchall()
                }
                for slot in range(container["capacity"]):
                    if slot not in occupied:
                        db.execute(
                            "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                            "VALUES(%s,2021,1,%s,%s)",
                            (character_id, container["uid"], slot),
                        )

        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = Peer()
        peer.send(426, _text(ticket) + _text("candidate-combat-reward-smoke"))
        peer.until(13873)
        peer.send(23664, struct.pack(">q", character_id) + _text(name))
        peer.until(630)
        peer.until(711)
        peer.send(12449)
        peer.until(12436)
        peer.until(711)
        peer.send(12449)
        peer.until(711)

        ref, level = 4196, 1
        monster_reference(ref)  # Fail before interacting if the frozen catalog differs.
        peer.send(
            12366,
            struct.pack(">H", len(f"!mob {ref} {level} 1"))
            + f"!mob {ref} {level} 1".encode(),
        )
        _, spawn_body, _ = peer.until(12608)
        monster = _spawned_actor(spawn_body)
        if monster["reference"] != ref:
            raise AssertionError(
                "Candidate console spawned an unexpected monster reference"
            )
        peer.until(674)

        x, y, z = monster["position"]
        peer.send(13130, struct.pack(">qiihB", monster["id"], x, y, z, 1))
        _, _, placement_packets = peer.until(13026)
        positions = next(body for opcode, body in placement_packets if opcode == 13652)
        fight_id, actors = _placement_positions(positions)
        if character_id not in actors or monster["id"] not in actors:
            raise AssertionError("Fight placement omitted a native participant")
        peer.send(12523, b"\x01")

        _, _, start_packets = peer.until(13482)
        current_actor = next(
            struct.unpack_from(">q", body, 4)[0]
            for opcode, body in reversed(start_packets)
            if opcode == 12873 and len(body) >= 12
        )
        if current_actor == monster["id"]:
            _, _, ai_packets = peer.until(12502)
            if not any(opcode == 12502 for opcode, _ in ai_packets):
                raise AssertionError("Native AI turn did not reach end-turn delivery")
            peer.send(13510, struct.pack(">i", 1))
            _, _, player_packets = peer.until(13482)
            current_actor = next(
                struct.unpack_from(">q", body, 4)[0]
                for opcode, body in reversed(player_packets)
                if opcode == 12873 and len(body) >= 12
            )
        if current_actor != character_id:
            raise AssertionError(
                "Socket smoke did not reach the controlled player turn"
            )

        target = actors[monster["id"]]
        attack = struct.pack(">qqbiih", character_id, -1, 15, *target)
        peer.send(12889, attack)
        _, report_body, _ = peer.until(12755)
        report = _report(fight_id, report_body)
        if (
            report["character_id"] != character_id
            or report["won_xp"] <= 0
            or report["kamas"] <= 0
        ):
            raise AssertionError(
                "Native socket fight did not publish positive committed rewards"
            )
        if (12325, 3) not in report["loots"]:
            raise AssertionError(
                "Native socket FightReport omitted the guaranteed catalog drop"
            )
        with store.connection() as db:
            reward = db.execute(
                "SELECT xp,kamas FROM fight_rewards WHERE fight_id=%s AND character_id=%s",
                (fight_id, character_id),
            ).fetchone()
            delivery = db.execute(
                "SELECT awarded_quantity,inventory_quantity,temporary_quantity "
                "FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s "
                "AND item_reference=12325",
                (fight_id, character_id),
            ).fetchone()
            temporary = db.execute(
                "SELECT quantity FROM temporary_combat_items WHERE fight_id=%s AND character_id=%s "
                "AND reference=12325",
                (fight_id, character_id),
            ).fetchone()
            from wakfu_server.combat_drop_delivery import temporary_section

            durable_temporary_section = temporary_section(db, character_id)
        if (
            reward is None
            or reward["xp"] != report["won_xp"]
            or reward["kamas"] != report["kamas"]
        ):
            raise AssertionError(
                "Native FightReport differs from durable reward receipt"
            )
        if (
            delivery is None
            or delivery["awarded_quantity"] != 3
            or delivery["temporary_quantity"] != 3
        ):
            raise AssertionError(
                "Native victory did not deliver guaranteed drop to overflow inventory"
            )
        if temporary is None or temporary["quantity"] != 3:
            raise AssertionError(
                "Temporary inventory did not retain the native socket drop"
            )

        # The UI groups identical temporary rows and sends the displayed total
        # while retaining one representative UID. Exercise that native packet
        # across two durable UID rows with fully linked award receipts.
        grouped_uid = _seed_receipt_backed_temporary(
            store, fight_id, character_id, 12325, 3
        )

        # The client only returns control to exploration after its native aUH
        # cleanup and matching coQ12925 continuation. Keep this in the socket
        # smoke: victory/report alone does not exercise HP reconciliation or
        # the world bootstrap.
        peer.send(12925, struct.pack(">iB", fight_id, 0))
        _, _, returned_packets = peer.until(13974)
        return_payloads = {}
        for opcode, body in returned_packets:
            return_payloads.setdefault(opcode, body)
        if not all(opcode in return_payloads for opcode in (12436, 13021, 13873)):
            raise AssertionError("Native return omitted health or currency refresh")
        with store.connection() as db:
            returned_character = store.character(account_id, character_id, db)
        health_actor, health_value, _ = struct.unpack(">qii", return_payloads[12436])
        if health_actor != character_id or health_value != returned_character["hp"]:
            raise AssertionError(
                "Native return health differs from durable post-level-up HP"
            )
        peer.socket.close()
        peer = None

        # Begin a fresh lease and verify that the temporary overflow item is
        # present in the actual character entity bootstrap after reconnect.
        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = Peer()
        peer.send(426, _text(ticket) + _text("candidate-combat-reward-reconnect"))
        peer.until(13873)
        peer.send(23664, struct.pack(">q", character_id) + _text(name))
        peer.until(630)
        peer.until(711)
        peer.send(12449)
        peer.until(12436)
        peer.until(711)
        peer.send(12449)
        peer.until(711)
        reconnect_packets = peer.received
        if not any(
            durable_temporary_section[2:] in body for _, body in reconnect_packets
        ):
            raise AssertionError(
                "Reconnect entity omitted durable temporary drop "
                f"(section={len(durable_temporary_section)} bytes, "
                f"packets={[(opcode, len(body)) for opcode, body in reconnect_packets]}, "
                f"section_prefix={durable_temporary_section[:12].hex()}, "
                f"item_payload_present=False)"
            )

        # Keep the bag full but give it a compatible stack, then claim all six
        # displayed units through one native 13993 representative UID.
        with store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()
            filler = db.execute(
                "SELECT uid,slot FROM inventory_items WHERE character_id=%s AND container=%s "
                "AND reference=2021 "
                "ORDER BY uid LIMIT 1 FOR UPDATE",
                (character_id, None if bag is None else bag["uid"]),
            ).fetchone()
            source = db.execute(
                "SELECT uid,quantity FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=12325 ORDER BY uid LIMIT 1",
                (character_id,),
            ).fetchone()
            group_rows = db.execute(
                "SELECT uid,quantity FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=12325 ORDER BY uid",
                (character_id,),
            ).fetchall()
            if (
                filler is None
                or bag is None
                or source is None
                or len(group_rows) != 2
                or sum(row["quantity"] for row in group_rows) != 6
                or grouped_uid not in {row["uid"] for row in group_rows}
            ):
                raise AssertionError(
                    "Candidate claim fixture is missing a bag slot or source"
                )
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (filler["uid"],))
            db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,12325,21,%s,%s)",
                (character_id, bag["uid"], filler["slot"]),
            )
            claim_body = struct.pack(">qh b q h", source["uid"], 6, -1, bag["uid"], -1)

        peer.send(13993, claim_body)
        _, _, claim_packets = peer.until(12691)
        claim_by_opcode = {}
        for opcode, body in claim_packets:
            claim_by_opcode.setdefault(opcode, body)
        if not all(opcode in claim_by_opcode for opcode in (13713, 13078, 12691)):
            raise AssertionError(
                "Native 13993 claim omitted inventory/equipment/temp snapshots"
            )
        with store.connection() as db:
            from wakfu_server import combat_drop_delivery

            claimed_character = store.character(account_id, character_id, db)
            claimed_rows = db.execute(
                "SELECT uid,quantity,container FROM inventory_items "
                "WHERE character_id=%s AND reference=12325 ORDER BY uid",
                (character_id,),
            ).fetchall()
            remaining_temporary = db.execute(
                "SELECT quantity FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=12325",
                (character_id,),
            ).fetchone()
            transfer_receipts = db.execute(
                "SELECT count(*) AS count FROM temporary_inventory_transfer_receipts "
                "WHERE source_character_id=%s AND operation=1",
                (character_id,),
            ).fetchone()["count"]
            expected_temporary_update = combat_drop_delivery.temporary_update(
                db, character_id
            )[1]
        if (
            len(claimed_rows) != 1
            or claimed_rows[0]["quantity"] != 27
            or claimed_rows[0]["container"] != bag["uid"]
        ):
            raise AssertionError(
                "Native grouped claim did not merge into the compatible full-bag stack"
            )
        if remaining_temporary is not None or transfer_receipts != 1:
            raise AssertionError(
                "Grouped native claim did not consume both compatible UIDs exactly once"
            )
        if claim_by_opcode[12691] != expected_temporary_update:
            raise AssertionError(
                "Claim temporary snapshot differs from committed overflow"
            )
        from wakfu_server.inventory import bags

        claimed_bags = bags(claimed_character)
        if (
            claim_by_opcode[13713]
            != struct.pack(">qB", character_id, 35) + claimed_bags
        ):
            raise AssertionError(
                "13993 response bag snapshot differs from committed inventory"
            )

        # Native Get All sends the current character as both cpX source and
        # destination. Move the remaining units back into the now-full bag,
        # merging into the existing full-bag stack.
        bulk_uid = _seed_receipt_backed_temporary(
            store, fight_id, character_id, 12325, 3
        )
        bulk_body = struct.pack(">qqhq", character_id, character_id, 1, bulk_uid)
        peer.send(12294, bulk_body)
        _, _, bulk_packets = peer.until(12691)
        with store.connection() as db:
            source_after_bulk = db.execute(
                "SELECT count(*) AS stacks,coalesce(sum(quantity),0) AS quantity "
                "FROM inventory_items WHERE character_id=%s AND reference=12325",
                (character_id,),
            ).fetchone()
            source_rows_after_bulk = db.execute(
                "SELECT uid,quantity,container FROM inventory_items "
                "WHERE character_id=%s AND reference=12325 ORDER BY uid",
                (character_id,),
            ).fetchall()
            source_remainder = db.execute(
                "SELECT uid FROM temporary_combat_items "
                "WHERE character_id=%s AND reference=12325",
                (character_id,),
            ).fetchone()
            source_after_snapshot = store.character(account_id, character_id, db)
            bulk_receipts = db.execute(
                "SELECT count(*) AS count FROM temporary_inventory_transfer_receipts "
                "WHERE source_character_id=%s AND operation=2",
                (character_id,),
            ).fetchone()["count"]
            expected_after_bulk_temp = combat_drop_delivery.temporary_update(
                db, character_id
            )[1]
        if (
            source_after_bulk["stacks"] != 1
            or source_after_bulk["quantity"] != 30
            or len(source_rows_after_bulk) != 1
            or source_rows_after_bulk[0]["container"] != bag["uid"]
        ):
            raise AssertionError(
                "12294 Get All did not merge into the same-character full-bag stack"
            )
        if source_remainder is not None or bulk_receipts != 1:
            raise AssertionError(
                "12294 did not consume its temporary source exactly once"
            )
        bulk_sync = [body for opcode, body in bulk_packets if opcode == 13713]
        if bulk_sync != [
            struct.pack(">qB", character_id, 35) + bags(source_after_snapshot)
        ]:
            raise AssertionError(
                "12294 self-transfer did not publish exactly one committed bag snapshot"
            )
        bulk_temp = [body for opcode, body in bulk_packets if opcode == 12691]
        if bulk_temp != [expected_after_bulk_temp]:
            raise AssertionError(
                "12294 temporary snapshot differs from committed overflow"
            )

        # A fresh session replays the merged item in the normal bag section;
        # retrying both exact requests after reconnect must only replay current
        # snapshots and must not create another stack or transfer receipt.
        peer.socket.close()
        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = Peer()
        peer.send(426, _text(ticket) + _text("candidate-combat-reward-claim-reconnect"))
        peer.until(13873)
        peer.send(23664, struct.pack(">q", character_id) + _text(name))
        peer.until(630)
        peer.until(711)
        peer.send(12449)
        peer.until(12436)
        peer.until(711)
        peer.send(12449)
        peer.until(711)
        with store.connection() as db:
            final_character = store.character(account_id, character_id, db)
        final_bags = bags(final_character)
        if not any(final_bags in body for _, body in peer.received):
            raise AssertionError("Reconnect bootstrap omitted the merged bag contents")
        peer.send(13993, claim_body)
        _, _, claim_retry_packets = peer.until(12691)
        if not all(
            opcode in [opcode for opcode, _ in claim_retry_packets]
            for opcode in (13713, 13078, 12691)
        ):
            raise AssertionError(
                "Reconnect claim retry omitted current inventory snapshots"
            )
        peer.send(12294, bulk_body)
        _, _, bulk_retry_packets = peer.until(12691)
        if len([1 for opcode, _ in bulk_retry_packets if opcode == 13713]) != 1:
            raise AssertionError(
                "Reconnect self-bulk retry did not return exactly one bag snapshot"
            )
        with store.connection() as db:
            after_claim_retry = db.execute(
                "SELECT count(*) AS stacks,coalesce(sum(quantity),0) AS quantity "
                "FROM inventory_items WHERE character_id=%s AND reference=12325",
                (character_id,),
            ).fetchone()
            after_bulk_retry = db.execute(
                "SELECT count(*) AS stacks,coalesce(sum(quantity),0) AS quantity "
                "FROM inventory_items WHERE character_id=%s AND reference=12325",
                (character_id,),
            ).fetchone()
            receipts_after_retries = db.execute(
                "SELECT count(*) AS count FROM temporary_inventory_transfer_receipts "
                "WHERE source_character_id=%s",
                (character_id,),
            ).fetchone()["count"]
        if (
            after_claim_retry["stacks"] != 1
            or after_claim_retry["quantity"] != 30
            or after_bulk_retry["stacks"] != 1
            or after_bulk_retry["quantity"] != 30
            or receipts_after_retries != 2
        ):
            raise AssertionError(
                "Reconnect retry duplicated claimed inventory or transfer receipts"
            )

        # 13447 is a distinct native temporary-inventory recycle action. The
        # native monster drop table has no SHARD-recyclable row, so seed one
        # receipt-backed item in the isolated DB and exercise the real socket.
        recyclable_uid = _seed_receipt_backed_temporary(
            store, fight_id, character_id, 2021, 1
        )
        with store.connection() as db:
            recyclable_slot = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=2021 "
                "ORDER BY uid LIMIT 1",
                (character_id,),
            ).fetchone()
            if recyclable_slot is None:
                raise AssertionError(
                    "Candidate recycle fixture cannot free a product slot"
                )
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s", (recyclable_slot["uid"],)
            )
        from wakfu_server.items.temporary_recycling import request as recycle_request

        recycle_opcode, recycle_body = recycle_request(character_id, [recyclable_uid])
        if recycle_opcode != 13447:
            raise AssertionError(
                "Temporary recycling encoder returned a different native opcode"
            )
        peer.send(recycle_opcode, recycle_body)
        _, recycle_result, recycle_packets = peer.until(12890)
        if len(recycle_result) != 8 or not all(
            opcode in {number for number, _ in recycle_packets}
            for opcode in (13713, 13078, 12691)
        ):
            raise AssertionError(
                "Native 13447 omitted its durable inventory/temp response"
            )
        peer.send(recycle_opcode, recycle_body)
        _, recycle_retry_result, _ = peer.until(12890)
        if recycle_retry_result != recycle_result:
            raise AssertionError("13447 retry changed its durable result")
        with store.connection() as db:
            if (
                db.execute(
                    "SELECT 1 FROM temporary_combat_items WHERE uid=%s",
                    (recyclable_uid,),
                ).fetchone()
                is not None
            ):
                raise AssertionError("13447 left its consumed temporary UID in storage")
            if (
                db.execute(
                    "SELECT count(*) AS n FROM temporary_item_recycling_receipts "
                    "WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["n"]
                != 1
            ):
                raise AssertionError("13447 retry duplicated its recycling receipt")

        # 12561 closes the overflow window by discarding its exact visible
        # snapshot; prove the empty state survives a new world lease/bootstrap.
        discarded_uid = _seed_receipt_backed_temporary(
            store, fight_id, character_id, 12325, 3
        )
        with store.connection() as db:
            from wakfu_server.combat_drop_delivery import temporary_section

            before_discard = temporary_section(db, character_id)
            expected_clear = struct.pack(">qB", character_id, 3)
        peer.send(12561, b"")
        _, discard_body, _ = peer.until(12691)
        if discard_body != expected_clear:
            raise AssertionError(
                "Native 12561 did not clear the committed temporary snapshot"
            )
        with store.connection() as db:
            if (
                db.execute(
                    "SELECT 1 FROM temporary_combat_items WHERE uid=%s",
                    (discarded_uid,),
                ).fetchone()
                is not None
            ):
                raise AssertionError(
                    "12561 did not durably delete the visible temporary item"
                )
            if (
                db.execute(
                    "SELECT count(*) AS n FROM temporary_inventory_transfer_receipts "
                    "WHERE source_character_id=%s AND operation=3",
                    (character_id,),
                ).fetchone()["n"]
                != 1
            ):
                raise AssertionError(
                    "12561 did not persist exactly one snapshot discard receipt"
                )

        peer.socket.close()
        generation = store.begin_session(account_id)
        ticket = store.issue_token(
            account_id, "ticket", generation=generation, realm_id=10
        )
        peer = Peer()
        peer.send(426, _text(ticket) + _text("candidate-temporary-discard-reconnect"))
        peer.until(13873)
        peer.send(23664, struct.pack(">q", character_id) + _text(name))
        peer.until(630)
        peer.until(711)
        peer.send(12449)
        peer.until(12436)
        peer.until(711)
        peer.send(12449)
        peer.until(711)
        if len(before_discard) < 3 or any(
            before_discard[2:] in body for _, body in peer.received
        ):
            raise AssertionError(
                "Discarded temporary snapshot reappeared after re-entry"
            )
        with store.connection() as db:
            if temporary_section(db, character_id) != b"\x00\x00":
                raise AssertionError("Discarded overflow was not empty after re-entry")

        print(
            "PASS: native TLS fight/return → grouped 13993 across two UIDs → full-bag same-character 12294 → reconnect retries → 13447 recycle → 12561 durable discard/re-entry"
        )
    finally:
        if peer is not None:
            peer.socket.close()
        store.close()


if __name__ == "__main__":
    main()
