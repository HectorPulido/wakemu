"""Transactional recycling using the installed native item catalogue.

The client/server result does not reveal the authoritative yield RNG. This
service therefore labels stochastic rounding as local policy, captures its
draws in the receipt, and fails closed when required per-item state is absent.
"""
from wakfu_server import native_catalog as protocol_catalog
import hashlib
import json
import math
import secrets
import struct

from psycopg.types.json import Jsonb

from .paths import DATA_ROOT
from . import recycling_wire


_CATALOG_DOCUMENT = protocol_catalog.load(DATA_ROOT / "item-recycling-metadata.json")
if (
    _CATALOG_DOCUMENT.get("record_count") != 20230
    or _CATALOG_DOCUMENT.get("error_count") != 0
    or _CATALOG_DOCUMENT.get("record_count") != len(_CATALOG_DOCUMENT.get("items", {}))
):
    raise ValueError("Incomplete native recycling metadata")
CATALOG = _CATALOG_DOCUMENT["items"]


def _policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='recycling_policy'"
    ).fetchone()
    value = row["value"] if row else None
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != 1
        or value.get("rounding_mode") != "stochastic_round"
        or value.get("aggregation_mode") != "sum_per_product_then_round"
        or not isinstance(value.get("disabled_item_refs"), list)
    ):
        raise ValueError("Invalid recycling policy")
    disabled = value["disabled_item_refs"]
    if any(
        type(reference) is not int or reference <= 0 for reference in disabled
    ) or len(disabled) != len(set(disabled)):
        raise ValueError("Invalid disabled native recycling references")
    return value, set(disabled)


def stochastic_round(value, draw):
    """Local policy: floor(value), then add one with probability its fraction."""
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
        or type(draw) not in (int, float)
        or not math.isfinite(draw)
        or not 0 <= draw < 1
    ):
        raise ValueError("Invalid stochastic recycling input")
    floor_value = math.floor(value)
    return floor_value + int(draw < value - floor_value)


def _float32(value):
    try:
        return struct.unpack(">f", struct.pack(">f", float(value)))[0]
    except (OverflowError, struct.error):
        raise ValueError("Invalid native recycling factor") from None


def _factor(row, quantity, state):
    low, high = row.get("yield_low"), row.get("yield_high")
    variable = row.get("variable_yield")
    if (
        type(low) not in (int, float)
        or not math.isfinite(low)
        or type(high) not in (int, float)
        or not math.isfinite(high)
        or type(variable) is not bool
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid native recycling factor metadata")
    # Native fpB.n picks high if it is nonnegative; -1 is the low-factor sentinel.
    factor = _float32(high if high >= 0 else low)
    if factor < 0:
        raise ValueError("Negative native recycling factor")
    if variable:
        unidentified = _native_unidentified(row, state)
        if unidentified:
            # fpB's verified unidentified bonus is 1.2f, rounded back to float.
            factor = _float32(float(factor) * _float32(1.2))
    amount = _float32(_float32(quantity) * factor)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("Invalid native recycling amount")
    return amount


def _native_unidentified(row, state):
    template_default = row.get("template_gjv")
    if type(template_default) is not bool:
        raise ValueError("Native item template state is unknown")
    saved_state = None if state is None else state.get("unidentified")
    if saved_state is not None and type(saved_state) is not bool:
        raise ValueError("Invalid persisted unidentified-bonus state")
    # The current ProtoItem carries no fpI slot map. Native fnR.ghe therefore
    # derives the value from fpC.gjv; an explicit conflicting value cannot be
    # represented by the packets this server emits and must fail closed.
    if saved_state is not None and saved_state is not template_default:
        raise ValueError("Unidentified-bonus state conflicts with emitted ProtoItem")
    return template_default


def _native_socketed(state):
    """Read the socket state represented by the ProtoItem we emit.

    inventory_items.item_proto does not publish the fpI installed-option map;
    the native fpI.gjH check therefore sees no installed UID when it is absent.
    A persisted positive observation remains a conservative server-side block.
    """
    saved_state = None if state is None else state.get("socketed")
    if saved_state is not None and type(saved_state) is not bool:
        raise ValueError("Invalid persisted socket state")
    return saved_state is True


def _delete_criterion_allows(expression, instance_id):
    if expression is None:
        return True
    if expression == "False":
        return False
    normalized = expression.replace(" ", "")
    if normalized == "GetInstanceId()!=702":
        return instance_id != 702
    if normalized == "GetInstanceId()<>1076andGetInstanceId()<>1073":
        return instance_id not in (1076, 1073)
    # Achievement state is not persisted by this server; unknown predicates
    # cannot authorize deletion of an item.
    raise ValueError("Unsupported native recycling DELETE criterion")


def _template_binding(reference):
    from .exchange_rules import ITEMS as BINDING_CATALOG

    row = BINDING_CATALOG.get(str(reference))
    if not isinstance(row, dict) or row.get("reference") != reference:
        raise ValueError("Missing native recycling binding metadata")
    template = row.get("binding_template")
    if (
        not isinstance(template, dict)
        or template.get("enum")
        not in (
            "NOT_BOUND",
            "BOUND_ON_PICKUP_TO_ACCOUNT",
            "BOUND_ON_PICKUP_TO_CHARACTER",
        )
        or type(template.get("default_eKo")) is not bool
    ):
        raise ValueError("Unsupported native recycling binding metadata")
    return template["default_eKo"]


def _instance_bound(db, item):
    from .exchange_rules import ITEMS as BINDING_CATALOG

    row = BINDING_CATALOG.get(str(item["reference"]))
    if not isinstance(row, dict) or row.get("reference") != item["reference"]:
        raise ValueError("Missing native recycling binding metadata")
    template = row.get("binding_template")
    if (
        not isinstance(template, dict)
        or type(template.get("default_eKo")) is not bool
        or template.get("enum")
        not in (
            "NOT_BOUND",
            "BOUND_ON_PICKUP_TO_ACCOUNT",
            "BOUND_ON_PICKUP_TO_CHARACTER",
        )
    ):
        raise ValueError("Unsupported native recycling binding metadata")
    state = db.execute(
        "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
        (item["uid"],),
    ).fetchone()
    if state is None:
        return template["default_eKo"]
    if (
        type(state["bound"]) is not bool
        or state["template_reference"] != item["reference"]
    ):
        raise ValueError("Invalid owned item binding metadata")
    return template["default_eKo"] or state["bound"]


def _equipped_uids(character):
    from wakfu_server.wire import proto_fields

    result = set()
    for build in character.get("builds", {}).values():
        equipment = bytes.fromhex(build["equipment"])
        for tag, value in proto_fields(equipment):
            if tag == 10:
                fields = dict(proto_fields(value))
                uid = fields.get(8)
                if type(uid) is not int or uid <= 0:
                    raise ValueError("Invalid owned equipment UID")
                result.add(uid)
    return result


def _guard_item(store, db, character, item, state, disabled):
    uid, reference = item["uid"], item["reference"]
    row = CATALOG.get(str(reference))
    if not isinstance(row, dict) or row.get("reference") != reference:
        raise ValueError("Unknown native recycling item reference")
    if (
        row.get("recycling_kind") not in ("SHARD", "POWDER")
        or type(row.get("not_recyclable_feature")) is not bool
        or row["not_recyclable_feature"]
        or reference in disabled
    ):
        raise ValueError("Native item is not recyclable")
    if not _delete_criterion_allows(
        row.get("raw_criteria", {}).get("DELETE"), character["instance_id"]
    ):
        raise ValueError("Native DELETE criterion forbids recycling")

    if _template_binding(reference):
        raise ValueError("Native bound item cannot be recycled")
    binding = db.execute(
        "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s FOR UPDATE",
        (uid,),
    ).fetchone()
    if binding is not None:
        if (
            type(binding["bound"]) is not bool
            or binding["template_reference"] != reference
        ):
            raise ValueError("Invalid owned item binding metadata")
        if binding["bound"]:
            raise ValueError("Bound item cannot be recycled")

    if item["quantity"] > 32767:
        raise ValueError("Invalid owned recycling stack")
    from .inventory_move import STACKS

    stack = STACKS.get(reference)
    if stack is None or not 1 <= item["quantity"] <= stack.get(
        "native_maximum", stack["maximum"]
    ):
        raise ValueError("Unknown or oversized native recycling stack")

    offered = db.execute(
        "SELECT 1 FROM player_exchange_items i JOIN player_exchanges e ON e.id=i.exchange_id "
        "WHERE i.uid=%s AND e.state IN ('invitation','active') LIMIT 1",
        (uid,),
    ).fetchone()
    if offered is not None:
        raise ValueError("Exchange-offered item cannot be recycled")

    if (
        db.execute(
            "SELECT 1 FROM inventory_containers WHERE uid=%s AND character_id=%s",
            (uid, character["id"]),
        ).fetchone()
        is not None
        or db.execute(
            "SELECT 1 FROM inventory_items WHERE container=%s LIMIT 1", (uid,)
        ).fetchone()
        is not None
    ):
        raise ValueError("Container item or nonempty bag cannot be recycled")
    if uid in _equipped_uids(character):
        raise ValueError("Desequip item from every build before recycling")

    equipment_slots = row.get("equipment_slots")
    if not isinstance(equipment_slots, list):
        raise ValueError("Missing native recycling slot metadata")
    item_state = db.execute(
        "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s FOR UPDATE",
        (uid,),
    ).fetchone()
    if _native_socketed(item_state):
        raise ValueError("Socketed item cannot be recycled")
    if row["variable_yield"]:
        _native_unidentified(row, item_state)
    return row, item_state


def _offered_uids(db, character_id):
    return {
        row["uid"]
        for row in db.execute(
            "SELECT i.uid FROM player_exchange_items i JOIN player_exchanges e ON e.id=i.exchange_id "
            "WHERE i.character_id=%s AND e.state IN ('invitation','active')",
            (character_id,),
        )
    }


def _grant_products(db, character, products, *, offered_uids, equipped_uids):
    from .inventory_elements import masks
    from .inventory_items import insertion
    from .inventory_move import ACQUISITION_STACKS as STACKS
    from .inventory_uids import allocate

    packets = []
    granted = []
    base = character["inventory_containers"][0]
    for reference in sorted(products):
        remaining = products[reference]
        stack = STACKS.get(reference)
        if stack is None or type(remaining) is not int or remaining < 0:
            raise ValueError("Unsupported native recycling product")
        maximum = stack["maximum"]
        while remaining:
            amount = min(remaining, maximum)
            resident = next(
                (
                    item
                    for item in character["inventory_items"]
                    if item["container"] == base["uid"]
                    and item["reference"] == reference
                    and item["uid"] not in offered_uids
                    and item["uid"] not in equipped_uids
                    and stack["minimal_mergeable"]
                    and masks(item) is None
                    and "mount" not in item
                    and item["quantity"] < maximum
                    and not _instance_bound(db, item)
                ),
                None,
            )
            if resident is not None:
                amount = min(remaining, maximum - resident["quantity"])
                item = dict(resident, quantity=resident["quantity"] + amount)
                db.execute(
                    "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
                    (item["quantity"], item["uid"], character["id"]),
                )
                packet = (12470, struct.pack(">qh", item["uid"], amount))
                index = next(
                    i
                    for i, value in enumerate(character["inventory_items"])
                    if value["uid"] == item["uid"]
                )
                character["inventory_items"][index] = item
            else:
                occupied = {
                    item["slot"]
                    for item in character["inventory_items"]
                    if item["container"] == base["uid"]
                }
                slot = next(
                    (
                        value
                        for value in range(base["capacity"])
                        if value not in occupied
                    ),
                    None,
                )
                if slot is None:
                    raise ValueError("Base inventory full")
                item = dict(
                    uid=allocate(db),
                    character_id=character["id"],
                    reference=reference,
                    quantity=min(remaining, maximum),
                    container=base["uid"],
                    slot=slot,
                )
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    tuple(
                        item[key]
                        for key in (
                            "uid",
                            "character_id",
                            "reference",
                            "quantity",
                            "container",
                            "slot",
                        )
                    ),
                )
                packet = insertion(item, notification=True)
                character["inventory_items"].append(item)
            packets.append(packet)
            granted.append(
                {
                    key: item[key]
                    for key in ("uid", "reference", "quantity", "container", "slot")
                }
            )
            remaining -= amount
    return packets, granted


def recycle(store, account_id, generation, character_id, body, *, fight=None, rng=None):
    """Validate a full selection, consume it, grant products and receipt atomically.

    `rng` is a test seam. Production callers must omit it. A fight runtime
    supplied by the dispatcher is rejected in addition to durable fight state.
    """
    request = recycling_wire.decode_request(12787, body)
    if fight is not None:
        raise ValueError("Items cannot be recycled during combat")
    uids = sorted(request["uids"])
    request_uids = Jsonb(uids)
    digest = hashlib.sha256(
        b"recycle\0" + b"".join(struct.pack(">q", uid) for uid in uids)
    ).digest()
    random_draw = secrets.SystemRandom().random if rng is None else rng

    with store.connection() as db:
        from .inventory_owner import (
            InventoryItemOwnershipError,
            lock_inventory_character,
            lock_item_owner,
        )

        lock_inventory_character(store, db, account_id, generation, character_id)
        prior = db.execute(
            "SELECT * FROM item_recycling_receipts WHERE account_id=%s "
            "AND request_hash=%s",
            (account_id, digest),
        ).fetchone()
        if prior is not None:
            character_id = lock_inventory_character(
                store, db, account_id, generation, prior["character_id"]
            )
            if prior["request_uids"] != uids:
                raise ValueError("Recycling receipt hash collision")
            character = store.character(account_id, character_id, db)
            packet = recycling_wire.result(
                prior["recovered_resources"], prior["destroyed_items"]
            )
            return dict(
                character=character,
                packets=[packet],
                applied=False,
                receipt=dict(prior),
            )

        try:
            character_id = lock_item_owner(
                store, db, account_id, generation, character_id, uids
            )
        except InventoryItemOwnershipError as error:
            raise ValueError(
                "Recycling selection contains a foreign or missing item"
            ) from error
        if (
            db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
                (character_id,),
            ).fetchone()
            is not None
        ):
            raise ValueError("Items cannot be recycled during combat")

        _, disabled = _policy(db)
        items = list(
            db.execute(
                "SELECT * FROM inventory_items WHERE uid=ANY(%s) AND character_id=%s "
                "ORDER BY uid FOR UPDATE",
                (uids, character_id),
            )
        )
        if len(items) != len(uids):
            raise ValueError("Recycling selection contains a foreign or missing item")
        character = store.character(account_id, character_id, db)
        character_items = {item["uid"]: item for item in character["inventory_items"]}
        if not set(uids).issubset(character_items):
            raise ValueError("Recycling selection is absent from owned inventory")

        validated = []
        for item in items:
            if item["character_id"] != character_id:
                raise ValueError("Foreign recycling item")
            row, state = _guard_item(store, db, character, item, None, disabled)
            validated.append((item, row, state))

        # Aggregate preview float32 factors by product first, then apply the
        # explicitly local stochastic-round policy once per resulting stack.
        totals = {}
        for item, row, state in validated:
            amount = _factor(row, item["quantity"], state)
            product = row["recycling_product_reference"]
            if type(product) is not int or product <= 0:
                raise ValueError("Invalid native recycling product reference")
            from .inventory_move import STACKS

            if product not in STACKS:
                raise ValueError("Native recycling product has no stack rule")
            totals[product] = totals.get(product, 0.0) + amount

        draws = {}
        products = {}
        for reference, amount in sorted(totals.items()):
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Invalid aggregate native recycling yield")
            floor_value = math.floor(amount)
            fraction = amount - floor_value
            if fraction:
                draw = random_draw()
                products[reference] = stochastic_round(amount, draw)
                draws[str(reference)] = draw
            else:
                products[reference] = floor_value
        recovered = sum(products.values())
        # The native preview/result counts units (`fnR.bfh()`), not selected
        # stack UIDs. A selected stack of quantity N contributes N destroyed.
        destroyed = sum(item["quantity"] for item, _, _ in validated)
        if recovered > 2**31 - 1 or destroyed > 2**31 - 1:
            raise ValueError("Native recycling result exceeds protocol bounds")

        # Prove every granted product fits before deleting a source item. Product
        # grants use the permanent bag only and may split across its native stacks.
        from .inventory_move import ACQUISITION_STACKS as STACKS
        from .inventory_elements import masks

        base = character["inventory_containers"][0]
        offered_uids = _offered_uids(db, character_id)
        equipped_uids = _equipped_uids(character)
        selected = set(uids)
        remaining_slots = base["capacity"] - sum(
            item["container"] == base["uid"] and item["uid"] not in selected
            for item in character["inventory_items"]
        )
        for reference, amount in sorted(products.items()):
            if amount == 0:
                continue
            stack = STACKS[reference]
            maximum = stack["maximum"]
            residents = [
                item
                for item in character["inventory_items"]
                if item["uid"] not in selected
                and item["container"] == base["uid"]
                and item["reference"] == reference
                and stack["minimal_mergeable"]
                and item["uid"] not in offered_uids
                and item["uid"] not in equipped_uids
                and "mount" not in item
                and masks(item) is None
                and not _instance_bound(db, item)
            ]
            room = sum(maximum - item["quantity"] for item in residents)
            new_stacks = math.ceil(max(0, amount - room) / maximum)
            if new_stacks > remaining_slots:
                raise ValueError("Base inventory cannot hold recycling products")
            remaining_slots -= new_stacks

        db.execute(
            "DELETE FROM inventory_items WHERE uid=ANY(%s) AND character_id=%s",
            (uids, character_id),
        )
        character["inventory_items"] = [
            item
            for item in character["inventory_items"]
            if item["uid"] not in set(uids)
        ]
        product_packets, grants = _grant_products(
            db,
            character,
            products,
            offered_uids=offered_uids,
            equipped_uids=equipped_uids,
        )
        receipt = dict(
            db.execute(
                "INSERT INTO item_recycling_receipts(account_id,character_id,request_hash,request_uids,"
                "recovered_resources,destroyed_items,products,rounding_draws,applied_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    account_id,
                    character_id,
                    digest,
                    request_uids,
                    recovered,
                    destroyed,
                    Jsonb({str(key): value for key, value in products.items()}),
                    Jsonb(draws),
                    store.now(),
                ),
            ).fetchone()
        )
        updated = store.character(account_id, character_id, db)
        return dict(
            character=updated,
            packets=product_packets + [recycling_wire.result(recovered, destroyed)],
            applied=True,
            receipt=receipt,
            product_grants=grants,
        )
