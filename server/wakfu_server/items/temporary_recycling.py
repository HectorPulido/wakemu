"""Transactional recycle path for temporary combat inventory (cxf/13447)."""
import hashlib
import json
import math
import secrets
import struct

from psycopg.types.json import Jsonb

from wakfu_server import recycling, recycling_wire


OPCODE = 13447


def decode_request(opcode, body):
    if opcode != OPCODE:
        raise ValueError("Unsupported temporary recycling opcode")
    if not isinstance(body, bytes) or len(body) < 10:
        raise ValueError("Invalid temporary recycling request length")
    character_id, count = struct.unpack_from(">qh", body)
    if character_id <= 0 or count <= 0 or len(body) != 10 + count * 8:
        raise ValueError("Invalid temporary recycling request fields")
    uids = list(struct.unpack_from(f">{count}q", body, 10))
    if any(uid <= 0 for uid in uids) or len(set(uids)) != count:
        raise ValueError("Invalid temporary recycling UIDs")
    return {"character_id": character_id, "uids": uids}


def request(character_id, uids):
    if (
        type(character_id) is not int
        or not 0 < character_id < 2**63
        or not isinstance(uids, (list, tuple))
        or not 1 <= len(uids) <= 32767
    ):
        raise ValueError("Invalid temporary recycling request")
    checked = []
    for uid in uids:
        if type(uid) is not int or not 0 < uid < 2**63:
            raise ValueError("Invalid temporary recycling UID")
        checked.append(uid)
    if len(set(checked)) != len(checked):
        raise ValueError("Duplicate temporary recycling UID")
    return OPCODE, struct.pack(">qh", character_id, len(checked)) + b"".join(
        struct.pack(">q", uid) for uid in checked
    )


def _canonical_body(character_id, uids):
    return request(character_id, sorted(uids))[1]


def _result_packets(store, db, account_id, character_id, recovered, destroyed):
    from wakfu_server import combat_drop_delivery, inventory_items, inventory_move

    character = store.character(account_id, character_id, db)
    return character, [
        inventory_move.synchronization(character),
        inventory_items.equipment_inventory(character),
        combat_drop_delivery.temporary_update(db, character_id),
        recycling_wire.result(recovered, destroyed),
    ]


def recycle(store, account_id, generation, character_id, body, *, rng=None):
    """Consume selected temporary SHARD sources, grant product, and receipt atomically.

    Yield selection and item filters reuse the native-catalog policy used by
    normal inventory recycling. Stochastic rounding remains explicit local
    server policy; retrying the same canonical request never draws again.
    """
    request_data = decode_request(OPCODE, body)
    if request_data["character_id"] != character_id:
        raise ValueError("Temporary recycling character does not match session")
    uids = sorted(request_data["uids"])
    canonical_body = _canonical_body(character_id, uids)
    digest = hashlib.sha256(b"temporary-recycle\0" + canonical_body).digest()
    random_draw = secrets.SystemRandom().random if rng is None else rng

    from wakfu_server.inventory_items import _lease

    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM temporary_item_recycling_receipts "
            "WHERE account_id=%s AND character_id=%s AND request_hash=%s",
            (account_id, character_id, digest),
        ).fetchone()
        if prior is not None:
            if (
                bytes(prior["request_body"]) != canonical_body
                or prior["request_uids"] != uids
            ):
                raise ValueError("Temporary recycling receipt hash collision")
            character, packets = _result_packets(
                store,
                db,
                account_id,
                character_id,
                prior["recovered_resources"],
                prior["destroyed_items"],
            )
            return dict(
                character=character, packets=packets, applied=False, receipt=dict(prior)
            )

        if (
            db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                (character_id,),
            ).fetchone()
            is not None
        ):
            raise ValueError("Items cannot be recycled during combat")

        _, disabled = recycling._policy(db)
        rows = db.execute(
            "SELECT * FROM temporary_combat_items WHERE character_id=%s AND uid=ANY(%s) "
            "ORDER BY uid FOR UPDATE",
            (character_id, uids),
        ).fetchall()
        if len(rows) != len(uids):
            raise ValueError(
                "Temporary recycling selection contains a foreign or missing item"
            )
        character = store.character(account_id, character_id, db)

        validated = []
        for item in rows:
            row = recycling.CATALOG.get(str(item["reference"]))
            if not isinstance(row, dict) or row.get("reference") != item["reference"]:
                raise ValueError("Unknown native temporary recycling item reference")
            if (
                row.get("recycling_kind") != "SHARD"
                or row.get("recycling_product_reference") != 27083
                or type(row.get("not_recyclable_feature")) is not bool
                or row["not_recyclable_feature"]
                or item["reference"] in disabled
            ):
                raise ValueError("Temporary item is not eligible for shard recycling")
            if not recycling._delete_criterion_allows(
                row.get("raw_criteria", {}).get("DELETE"), character["instance_id"]
            ):
                raise ValueError("Native DELETE criterion forbids recycling")
            from wakfu_server.inventory_move import STACKS

            stack = STACKS.get(item["reference"])
            if (
                stack is None
                or type(item["quantity"]) is not int
                or not 1 <= item["quantity"] <= stack["maximum"]
            ):
                raise ValueError("Invalid temporary recycling stack")
            # The temporary ProtoItem has no installed-option map; it therefore
            # cannot represent sockets. Variable-yield state follows the same
            # native template default as the live client item.
            if row.get("variable_yield"):
                recycling._native_unidentified(row, None)
            validated.append((item, row))

        totals = {}
        for item, row in validated:
            amount = recycling._factor(row, item["quantity"], None)
            product = row["recycling_product_reference"]
            totals[product] = totals.get(product, 0.0) + amount

        products = {}
        draws = {}
        for product, amount in sorted(totals.items()):
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Invalid aggregate temporary recycling yield")
            fraction = amount - math.floor(amount)
            if fraction:
                draw = random_draw()
                products[product] = recycling.stochastic_round(amount, draw)
                draws[str(product)] = draw
            else:
                products[product] = math.floor(amount)
        recovered = sum(products.values())
        # The client preview counts stack quantity, not merely selected UIDs.
        destroyed = sum(item["quantity"] for item, _ in validated)
        if recovered > 2**31 - 1 or destroyed > 2**31 - 1:
            raise ValueError("Temporary recycling result exceeds protocol bounds")

        db.execute(
            "DELETE FROM temporary_combat_items WHERE character_id=%s AND uid=ANY(%s)",
            (character_id, uids),
        )
        offered = recycling._offered_uids(db, character_id)
        equipped = recycling._equipped_uids(character)
        product_packets, grants = recycling._grant_products(
            db, character, products, offered_uids=offered, equipped_uids=equipped
        )
        # Product deltas are deliberately omitted: the complete permanent
        # inventory snapshots below replace state without double-applying them.
        db.execute(
            "INSERT INTO temporary_item_recycling_receipts "
            "(account_id,character_id,request_hash,request_body,request_uids,recovered_resources,"
            "destroyed_items,products,rounding_draws,applied_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                character_id,
                digest,
                canonical_body,
                Jsonb(uids),
                recovered,
                destroyed,
                Jsonb({str(key): value for key, value in products.items()}),
                Jsonb(draws),
                store.now(),
            ),
        )
        updated, packets = _result_packets(
            store, db, account_id, character_id, recovered, destroyed
        )
        return dict(
            character=updated,
            packets=packets,
            applied=True,
            receipt=dict(
                recovered_resources=recovered,
                destroyed_items=destroyed,
                products={str(key): value for key, value in products.items()},
                rounding_draws=draws,
            ),
            product_grants=grants,
        )
