"""Native per-item elemental selection authority (opcode 12487).

Socket generation/identification (13787) is intentionally separate: this
module only accepts masks supported by the item's verified elemental effects.
"""
from contextlib import ExitStack
import struct

from .inventory_owner import lock_item_owner
from wakfu_server.equipment_stats import CATALOG
from wakfu_server.wire import proto_fields

VALID_MASK = 30  # bits 1..4; bit 0 and all other bits are invalid.
FIELDS = {1068: "damage_elements", 1069: "resistance_elements"}


def decode_request(body):
    if not isinstance(body, bytes) or len(body) != 10:
        raise ValueError("Invalid native elemental selection length")
    uid, damage, resistance = struct.unpack(">qBB", body)
    if uid <= 0:
        raise ValueError("Invalid elemental selection UID")
    _validate_mask(damage)
    _validate_mask(resistance)
    return dict(uid=uid, damage_elements=damage, resistance_elements=resistance)


def _validate_mask(mask):
    if type(mask) is not int or mask < 0 or mask & ~VALID_MASK:
        raise ValueError("Invalid native elemental mask")


def _required_counts(reference):
    template = CATALOG.get(reference)
    if template is None:
        raise ValueError("Missing native elemental template")
    counts = {"damage_elements": 0, "resistance_elements": 0}
    seen = set()
    for effect in template["effects"]:
        field = FIELDS.get(effect["generic"])
        if field is None:
            continue
        if field in seen:
            raise ValueError("Repeated native elemental effect is unsupported")
        seen.add(field)
        params = effect.get("params", ())
        if len(params) < 3:
            raise ValueError("Incomplete native elemental effect")
        count = params[2]
        if type(count) is int:
            pass
        elif type(count) is float and count.is_integer():
            pass
        else:
            raise ValueError("Invalid native elemental effect count")
        count = int(count)
        if not 0 <= count <= 4:
            raise ValueError("Unsupported native elemental effect count")
        counts[field] = count
    if not any(counts.values()):
        raise ValueError("Item has no selectable native elemental effect")
    return counts


def _validate_selection(reference, damage, resistance):
    _validate_mask(damage)
    _validate_mask(resistance)
    expected = _required_counts(reference)
    if damage.bit_count() != expected["damage_elements"]:
        raise ValueError("Damage mask does not match the native template")
    if resistance.bit_count() != expected["resistance_elements"]:
        raise ValueError("Resistance mask does not match the native template")


def encode_result(uid, damage, resistance, *, status=0, sockets=b""):
    """Encode the verified 13766 result frame for the two independent blobs."""
    if type(uid) is not int or not 0 < uid < (1 << 63):
        raise ValueError("Invalid result UID")
    if type(status) is not int or status not in (0, 1, 2):
        raise ValueError("Invalid native identification status")
    _validate_mask(damage)
    _validate_mask(resistance)
    if not isinstance(sockets, bytes):
        raise ValueError("Invalid socket result blob")
    if sockets:
        from .inventory_shards import initialized_wire_state

        sockets = initialized_wire_state(sockets)
    elements = bytes((damage, resistance))
    return (
        13766,
        struct.pack(">iqB I", status, uid, 0, len(elements))
        + elements
        + struct.pack(">I", len(sockets))
        + sockets,
    )


def select(store, account_id, generation, character_id, body):
    """Commit a single UID's 12487 choice, returning a retry-safe receipt.

    The user may choose a different valid selection while the item remains
    unidentified for another reason. The receipt records the latest successful
    SET request, making the immediate network retry idempotent without treating
    elemental choices as permanently immutable.
    """
    request = decode_request(body)
    uid = request["uid"]
    damage = request["damage_elements"]
    resistance = request["resistance_elements"]
    with store.connection() as db, ExitStack() as mutation_scopes:
        character_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        if (
            db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
                "ON f.id=p.fight_id WHERE p.character_id=%s "
                "AND f.status IN ('placement','active') LIMIT 1",
                (character_id,),
            ).fetchone()
            is not None
        ):
            raise ValueError("Elemental selection is unavailable during combat")
        from wakfu_server.item_mutation import refresh_equipment_after_mutation

        mutation_scopes.enter_context(
            refresh_equipment_after_mutation(store, db, account_id, character_id, uid)
        )
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Elemental selection item is unavailable or foreign")
        _validate_selection(item["reference"], damage, resistance)

        # Exchange membership blocks concurrent changes even if this item has
        # not yet been offered. A UID already in an offer is checked separately.
        if (
            db.execute(
                "SELECT 1 FROM player_exchange_members WHERE character_id=%s",
                (character_id,),
            ).fetchone()
            or db.execute(
                "SELECT 1 FROM player_exchange_items WHERE uid=%s", (uid,)
            ).fetchone()
        ):
            raise ValueError("Cannot select elements during an active exchange")

        from .shard_identification import _catalog as socket_templates, identify

        socket_result = None
        if item["reference"] in socket_templates():
            socket_result = identify(
                store,
                account_id,
                generation,
                character_id,
                struct.pack(">q", uid),
                db=db,
            )
            if socket_result["status"] != 0:
                from .shard_identification_wire import response

                return dict(
                    character_id=character_id,
                    uid=uid,
                    applied=False,
                    status=socket_result["status"],
                    packet=response(socket_result),
                    cost_kamas=0,
                    damage_elements=damage,
                    resistance_elements=resistance,
                    shard_state=None,
                )

        from wakfu_server.equipment_stacks import ensure_singleton

        item = ensure_singleton(db, character_id, uid)

        prior = db.execute(
            "SELECT damage_elements,resistance_elements FROM inventory_element_selection_receipts "
            "WHERE character_id=%s AND uid=%s FOR UPDATE",
            (character_id, uid),
        ).fetchone()
        current = db.execute(
            "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s FOR UPDATE",
            (uid,),
        ).fetchone()
        if (
            prior is not None
            and (prior["damage_elements"], prior["resistance_elements"])
            == (damage, resistance)
            and current is not None
            and (current["damage_elements"], current["resistance_elements"])
            == (damage, resistance)
        ):
            applied = False
        else:
            if current is None:
                db.execute(
                    "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                    "VALUES(%s,%s,%s)",
                    (uid, damage, resistance),
                )
            else:
                db.execute(
                    "UPDATE inventory_item_elements SET damage_elements=%s,resistance_elements=%s "
                    "WHERE uid=%s",
                    (damage, resistance, uid),
                )
            db.execute(
                "INSERT INTO inventory_element_selection_receipts "
                "(account_id,character_id,uid,damage_elements,resistance_elements,applied_at) "
                "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,uid) DO UPDATE SET "
                "account_id=EXCLUDED.account_id,damage_elements=EXCLUDED.damage_elements,"
                "resistance_elements=EXCLUDED.resistance_elements,applied_at=EXCLUDED.applied_at",
                (account_id, character_id, uid, damage, resistance, store.now()),
            )
            applied = True

        shard_row = db.execute(
            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s", (uid,)
        ).fetchone()
        if shard_row is None:
            shard_state = None
        else:
            from .inventory_shards import validate

            shard_state = validate(bytes(shard_row["shard_state"]))

        return dict(
            character_id=character_id,
            uid=uid,
            damage_elements=damage,
            resistance_elements=resistance,
            shard_state=shard_state,
            packet=encode_result(
                uid,
                damage,
                resistance,
                sockets=b"" if shard_state is None else shard_state,
            ),
            applied=applied,
            status=0,
            cost_kamas=(
                socket_result["cost_kamas"]
                if socket_result is not None and socket_result["applied"]
                else 0
            ),
            wallet_kamas=None
            if socket_result is None
            else socket_result["wallet_kamas"],
        )
