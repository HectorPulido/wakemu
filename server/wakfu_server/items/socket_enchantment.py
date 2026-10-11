"""Transactional local policy for native socket/enchantment mutations.

The client request shapes are native. Sacrifice, charge costs and random
outcomes remain explicit experiment policy in ``settings``; this module does
not describe those choices as upstream server rules.
"""
from wakfu_server import native_catalog as protocol_catalog
import hashlib
import json
import secrets
import struct

from wakfu_server.wire import proto_field, proto_fields

from .inventory_items import _lease
from .inventory_shards import validate

# Native bqI counts inventory reference 27083 for the common shard reserve.
SHARD_MATERIAL_REFERENCE = 27083

OPS = {
    "add_charges",
    "add_slot",
    "change_slot_color",
    "increase_count",
    "change_colors",
    "change_order",
    "apply_sublimation",
    "remove_sublimation",
}
_BONUS_CATALOG = None


def _bonus_catalog():
    global _BONUS_CATALOG
    if _BONUS_CATALOG is None:
        from wakfu_server.paths import DATA_ROOT

        document = protocol_catalog.load(DATA_ROOT / "item-shard-effects.json")
        source = document.get("source", {})
        rows = document.get("items")
        if (
            source.get("client_jar_sha256")
            != "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
            or source.get("mechanism")
            != "fpN.y(fnO), eVn.a(level), fpG.WA(slotLevel), fpG.gjC()"
            or not isinstance(rows, list)
            or len(rows) != 17
        ):
            raise ValueError("Incomplete native shard bonus catalog")
        bonuses = {}
        for row in rows:
            reference = row.get("reference")
            color = row.get("native_bonus_color")
            costs = row.get("shard_count_by_level")
            levels = row.get("minimum_player_level_by_bonus_level")
            if (
                type(reference) is not int
                or reference <= 0
                or reference in bonuses
                or not isinstance(color, dict)
                or type(color.get("ordinal")) is not int
                or color["ordinal"] not in (1, 2, 3)
                or color.get("name") not in ("RED", "GREEN", "BLUE")
                or type(row.get("selectable")) is not bool
                or not isinstance(costs, list)
                or not costs
                or not isinstance(levels, list)
                or len(levels) != len(costs)
                or any(type(v) is not int or v <= 0 for v in costs)
                or any(type(v) is not int or v < 0 for v in levels)
                or any(a >= b for a, b in zip(costs, costs[1:]))
                or any(a > b for a, b in zip(levels, levels[1:]))
            ):
                raise ValueError("Malformed native shard bonus definition")
            bonuses[reference] = dict(
                reference=reference,
                color=color["ordinal"],
                selectable=row["selectable"],
                costs=costs,
                minimum_levels=levels,
            )
        _BONUS_CATALOG = bonuses
    return _BONUS_CATALOG


def _int32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & (1 << 31) else value


def _put(fields, tag, value):
    """Replace one varint field, preserving unknown protobuf fields."""
    encoded = proto_field(tag, value & 0xFFFFFFFFFFFFFFFF)
    out, inserted = [], False
    for old_tag, old_value in fields:
        if old_tag == tag:
            if not inserted:
                out.append(encoded)
                inserted = True
            continue
        out.append(proto_field(old_tag, old_value))
    if not inserted:
        out.append(encoded)
    return b"".join(out)


def _set_repeated(blob, tag, values):
    fields = list(proto_fields(blob))
    replacement = [proto_field(tag, value) for value in values]
    out, inserted = [], False
    for old_tag, old_value in fields:
        if old_tag == tag:
            if not inserted:
                out.extend(replacement)
                inserted = True
            continue
        out.append(proto_field(old_tag, old_value))
    if not inserted:
        out.extend(replacement)
    return b"".join(out)


def _slots(state):
    rows = []
    for tag, nested in proto_fields(state):
        if tag != 10:
            continue
        data = dict(proto_fields(nested))
        rows.append(
            {
                "position": _int32(data.get(80, 0)),
                "reference": _int32(data.get(88, 0)),
                "color": _int32(data.get(96, 0)),
                "level": _int32(data.get(112, 0)),
                "raw": nested,
            }
        )
    rows.sort(key=lambda row: row["position"])
    if [row["position"] for row in rows] != list(range(len(rows))):
        raise ValueError("Socket slots have invalid native positions")
    return rows


def _set_slot(row, **changes):
    names = {"position": 80, "reference": 88, "color": 96, "level": 112}
    fields = list(proto_fields(row["raw"]))
    for name, value in changes.items():
        fields = list(proto_fields(_put(fields, names[name], value)))
        # _put preserves unrecognized fields, including nested extensions.
    return b"".join(proto_field(tag, value) for tag, value in fields)


def _replace_slots(state, rows):
    return validate(_set_repeated(state, 10, [row["raw"] for row in rows]))


def _policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='socket_enchantment_policy'"
    ).fetchone()
    if row is None:
        raise ValueError("Socket enchantment policy is unavailable")
    value = row["value"]
    if isinstance(value, str):
        value = json.loads(value)
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != 1
    ):
        raise ValueError("Unsupported socket enchantment policy")
    if value.get("source") != "local_policy_native_enchantment_request":
        raise ValueError("Unrecognized socket enchantment policy source")
    enabled = value.get("enabled_operations")
    if (
        not isinstance(enabled, list)
        or any(not isinstance(op, str) for op in enabled)
        or not set(enabled) <= OPS
        or len(enabled) != len(set(enabled))
    ):
        raise ValueError("Invalid enabled socket mutation set")
    costs = value.get("operation_kamas")
    charges = value.get("charge_costs")
    if (
        not isinstance(costs, dict)
        or set(costs) != OPS
        or any(type(cost) is not int or cost < 0 for cost in costs.values())
        or not isinstance(charges, dict)
        or set(charges) != {"increase_count", "change_colors", "change_order"}
        or any(type(cost) is not int or cost < 0 for cost in charges.values())
        or type(value.get("charge_gain_per_sacrifice")) is not int
        or value["charge_gain_per_sacrifice"] < 0
        or type(value.get("charge_cap")) is not int
        or not 0 <= value["charge_cap"] <= 255
        or type(value.get("sublimation_refund_bp")) is not int
        or value["sublimation_refund_bp"] != 0
        or type(value.get("same_reference_sacrifice")) is not bool
        or type(value.get("request_dedupe_ms")) is not int
        or not 0 <= value["request_dedupe_ms"] <= 60000
    ):
        raise ValueError("Invalid local socket enchantment policy")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return value, hashlib.sha256(encoded).digest()


def _native_pattern_matches(rows, pattern):
    """Mirror fpK.a(fpI, fpP): ordered contiguous colors, white is wildcard."""
    if not pattern:
        return True
    if len(pattern) > len(rows):
        return False
    for start in range(len(rows) - len(pattern) + 1):
        for offset, required in enumerate(pattern):
            actual = rows[start + offset]["color"]
            if actual not in (1, 2, 3, 4):
                break
            if actual != 4 and required != 0 and actual != required:
                break
        else:
            return True
    return False


def _decode(opcode, body):
    if not isinstance(body, bytes):
        raise ValueError("Invalid socket mutation body")
    if opcode == 12365:
        if len(body) == 17:
            uid, action, ingredient = struct.unpack(">qBq", body)
            position = color = None
        elif len(body) == 19:
            uid, action, ingredient, position, color = struct.unpack(">qBqBB", body)
        else:
            raise ValueError("Invalid native socket sacrifice length")
        if action not in (0, 1, 2) or uid <= 0 or ingredient <= 0 or uid == ingredient:
            raise ValueError("Invalid native socket sacrifice request")
        if (action == 2) != (position is not None):
            raise ValueError("Invalid native socket color request")
        return (
            uid,
            ("add_charges", "add_slot", "change_slot_color")[action],
            ingredient,
            position,
            color,
        )
    if opcode == 13257 and len(body) == 9:
        uid, action = struct.unpack(">qB", body)
        if uid <= 0 or action not in (0, 1, 2):
            raise ValueError("Invalid native socket workshop request")
        return (
            uid,
            ("increase_count", "change_colors", "change_order")[action],
            None,
            None,
            None,
        )
    if opcode == 12221 and len(body) == 12:
        uid, reference = struct.unpack(">qi", body)
        if uid <= 0 or reference <= 0:
            raise ValueError("Invalid native sublimation request")
        return uid, "apply_sublimation", None, None, reference
    if opcode == 12364 and len(body) == 9:
        uid, special = struct.unpack(">qB", body)
        if uid <= 0 or special not in (0, 1):
            raise ValueError("Invalid native sublimation removal request")
        return uid, "remove_sublimation", None, special, None
    raise ValueError("Unsupported native socket mutation request")


def _decode_bonus_install(body):
    if not isinstance(body, bytes) or len(body) < 18:
        raise ValueError("Invalid native socket bonus installation body")
    uid, count = struct.unpack_from(">qB", body)
    if uid <= 0 or not 1 <= count <= 4 or len(body) != 9 + count * 9:
        raise ValueError("Invalid native socket bonus installation length")
    updates = {}
    offset = 9
    for _ in range(count):
        position = body[offset]
        reference, amount = struct.unpack_from(">ii", body, offset + 1)
        offset += 9
        if position > 3 or position in updates:
            raise ValueError("Invalid or duplicate native socket bonus position")
        if reference < 0 or amount < 0 or ((reference == 0) != (amount == 0)):
            raise ValueError("Invalid native socket bonus reference/amount pair")
        updates[position] = (reference, amount)
    return uid, updates


def _wallet(db, account_id):
    row = db.execute(
        "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Socket mutation wallet is unavailable")
    return row["kamas"]


def _guard(db, character_id):
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Socket mutation is unavailable during combat")
    if db.execute(
        "SELECT 1 FROM player_exchange_members WHERE character_id=%s LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Socket mutation is unavailable during exchange")


def _equipped(store, db, account_id, character_id, uid):
    from wakfu_server.wire import proto_fields

    for build in store.character(account_id, character_id, db)["builds"].values():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 10 and dict(proto_fields(value)).get(8) == uid:
                return True
    return False


def _published_state(
    store,
    db,
    account_id,
    character_id,
    uid,
    operation,
    state,
    *,
    cost_kamas,
    consumed_uid,
    applied
):
    from wakfu_server.inventory_move import synchronization
    from wakfu_server.inventory_items import equipment_inventory

    character = store.character(account_id, character_id, db)
    packet = synchronization(character)
    result = dict(
        uid=uid,
        operation=operation,
        shard_state=state,
        wallet_kamas=character["kamas"],
        cost_kamas=cost_kamas,
        consumed_uid=consumed_uid,
        inventory_packet=packet,
        equipment_packet=equipment_inventory(character),
        inventory_items=character["inventory_items"],
        inventory_containers=character["inventory_containers"],
        applied=applied,
    )
    # Construct every outbound frame while the database transaction is still
    # open. In particular, the native carrier has a signed-short ProtoShard
    # length; a failure must roll back a charge, cost, or consumed ingredient.
    from wakfu_server.socket_enchantment_wire import packets

    packets(character["id"], result)
    return result


def _consume(
    store,
    db,
    account_id,
    character_id,
    uid,
    *,
    expected_reference=None,
    allow_stack=False
):
    item = db.execute(
        "SELECT quantity,reference FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
        (uid, character_id),
    ).fetchone()
    if item is None:
        raise ValueError("Socket sacrifice item is unavailable or foreign")
    if item["quantity"] < 1 or (item["quantity"] != 1 and not allow_stack):
        raise ValueError("Socket sacrifice requires an unstacked item UID")
    if expected_reference is not None and item["reference"] != expected_reference:
        raise ValueError("Socket sacrifice reference is incompatible")
    if db.execute(
        "SELECT 1 FROM player_exchange_items WHERE uid=%s LIMIT 1", (uid,)
    ).fetchone():
        raise ValueError("Socket sacrifice item is offered in an exchange")
    if _equipped(store, db, account_id, character_id, uid):
        raise ValueError("Unequip socket sacrifice before consuming it")
    if item["quantity"] == 1:
        db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
    else:
        db.execute(
            "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s", (uid,)
        )


def mutate(
    store, account_id, generation, character_id, opcode, body, *, randbelow=None
):
    """Apply a native socket mutation under versioned local policy.

    Returns the committed ProtoShard and wallet amount for the adapter to
    encode. The caller owns the surrounding network response publication.
    """
    if opcode not in (12365, 13257, 12221, 12364):
        raise ValueError("Unsupported native socket mutation opcode")
    uid, operation, ingredient, selector, extra = _decode(opcode, body)
    if opcode == 12365 and operation not in {
        "add_charges",
        "add_slot",
        "change_slot_color",
    }:
        raise ValueError("Native socket action/opcode mismatch")
    if opcode == 13257 and operation not in {
        "increase_count",
        "change_colors",
        "change_order",
    }:
        raise ValueError("Native workshop action/opcode mismatch")
    if (
        opcode == 12221
        and operation != "apply_sublimation"
        or opcode == 12364
        and operation != "remove_sublimation"
    ):
        raise ValueError("Native sublimation action/opcode mismatch")
    randbelow = secrets.randbelow if randbelow is None else randbelow
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        _guard(db, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        if item is None or item["quantity"] != 1:
            raise ValueError("Socket mutation requires one owned unstacked item")
        from .shard_identification import _catalog
        from .sublimation_eligibility import pattern, special_target

        attachment = pattern(db, extra) if operation == "apply_sublimation" else None
        special = (attachment is not None and attachment["tag"] == 32) or (
            operation == "remove_sublimation" and selector
        )
        template = _catalog().get(item["reference"])
        if special:
            authority = special_target(
                db,
                item["reference"],
                kind=None if attachment is None else attachment["kind"],
            )
            # Native bqV.dHp accepts an unstacked matching-rarity target even
            # without fpI. Special attachments do not require socket colors.
            template = dict(item_level=authority["item_level"])
        if template is None:
            raise ValueError("Socket target is not natively eligible")
        character_level = db.execute(
            "SELECT level FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if character_level is None or character_level["level"] < template["item_level"]:
            raise ValueError(
                "Socket mutation target exceeds the local character-level gate"
            )
        if db.execute(
            "SELECT 1 FROM player_exchange_items WHERE uid=%s LIMIT 1", (uid,)
        ).fetchone():
            raise ValueError("Socket target is offered in an exchange")
        if _equipped(store, db, account_id, character_id, uid):
            raise ValueError("Unequip socket target before mutation")
        shard = db.execute(
            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s FOR UPDATE",
            (uid,),
        ).fetchone()
        if shard is None and not (special and operation == "apply_sublimation"):
            raise ValueError("Socket target has no identified shard state")
        state = validate(
            proto_field(72, 0) if shard is None else bytes(shard["shard_state"])
        )
        policy, policy_hash = _policy(db)
        if operation not in policy["enabled_operations"]:
            raise ValueError("Socket operation disabled by local policy")
        request_hash = hashlib.sha256(struct.pack(">I", opcode) + body).digest()
        before_hash = hashlib.sha256(state).digest()
        if ingredient is not None:
            prior = db.execute(
                "SELECT result_state,cost_kamas,consumed_uid FROM inventory_socket_enchantment_receipts "
                "WHERE character_id=%s AND uid=%s AND operation=%s AND request_hash=%s "
                "AND consumed_uid IS NOT NULL ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (character_id, uid, operation, request_hash),
            ).fetchone()
        else:
            prior = db.execute(
                "SELECT result_state,cost_kamas,consumed_uid FROM inventory_socket_enchantment_receipts "
                "WHERE character_id=%s AND uid=%s AND operation=%s AND request_hash=%s "
                "AND applied_at >= %s - (%s * interval '1 millisecond') "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (
                    character_id,
                    uid,
                    operation,
                    request_hash,
                    store.now(),
                    policy["request_dedupe_ms"],
                ),
            ).fetchone()
        if prior is not None:
            # Sacrifices key retries permanently by consumed UID. Requests
            # without an ingredient use the policy's short retry window.
            return _published_state(
                store,
                db,
                account_id,
                character_id,
                uid,
                operation,
                state,
                cost_kamas=prior["cost_kamas"],
                consumed_uid=prior["consumed_uid"],
                applied=False,
            )

        if operation == "apply_sublimation":
            # The native request names a scroll reference, not a unique unit.
            # Replaying an already-installed scroll must not consume another
            # copy, including after the short transport retry window expires.
            if any(
                tag == attachment["tag"] and value == extra
                for tag, value in proto_fields(state)
            ):
                return _published_state(
                    store,
                    db,
                    account_id,
                    character_id,
                    uid,
                    operation,
                    state,
                    cost_kamas=0,
                    consumed_uid=None,
                    applied=False,
                )
            scrolls = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s AND reference=%s "
                "AND uid<>%s ORDER BY uid FOR UPDATE",
                (character_id, extra, uid),
            ).fetchall()
            # A reference-only request does not select a specific stack. A
            # protected first UID must not hide another consumable owned copy.
            scroll = next(
                (
                    candidate
                    for candidate in scrolls
                    if candidate["quantity"] > 0
                    and not db.execute(
                        "SELECT 1 FROM player_exchange_items WHERE uid=%s LIMIT 1",
                        (candidate["uid"],),
                    ).fetchone()
                    and not _equipped(
                        store, db, account_id, character_id, candidate["uid"]
                    )
                ),
                None,
            )
            if scroll is None:
                raise ValueError("Owned sublimation item is unavailable")
            if scroll["quantity"] < 1:
                raise ValueError("Sublimation item stack is empty")
            ingredient = scroll["uid"]

        rows = _slots(state)
        if (
            not special
            and not template["min_sockets"] <= len(rows) <= template["max_sockets"]
        ):
            raise ValueError(
                "Persisted socket count is outside the native template bounds"
            )
        cost = policy["operation_kamas"][operation]
        wallet = _wallet(db, account_id)
        if wallet < cost:
            raise ValueError("Insufficient kamas for local socket policy")
        if cost:
            db.execute(
                "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s",
                (cost, account_id),
            )

        charges = 0
        for tag, value in proto_fields(state):
            if tag == 72:
                charges = _int32(value)
        if not 0 <= charges <= 255:
            raise ValueError("Invalid persisted socket charge count")
        if operation in ("add_charges", "add_slot", "change_slot_color"):
            if ingredient is None:
                raise ValueError("Native sacrifice UID missing")
            # The sacrifice count/gain is a documented local policy.
            if operation == "add_charges":
                charges = min(
                    policy["charge_cap"], charges + policy["charge_gain_per_sacrifice"]
                )
                if charges == _int32(
                    next((v for t, v in proto_fields(state) if t == 72), 0)
                ):
                    raise ValueError("Socket charge cap reached")
            elif operation == "add_slot":
                if len(rows) >= template["max_sockets"]:
                    raise ValueError("Socket slot cap reached")
                color = randbelow(4) + 1
                if type(color) is not int or color not in (1, 2, 3, 4):
                    raise ValueError("Random source returned invalid socket color")
                newrow = {
                    "position": len(rows),
                    "reference": 0,
                    "color": color,
                    "level": 0,
                    "raw": b"",
                }
                newrow["raw"] = b"".join(
                    (proto_field(80, len(rows)), proto_field(96, color))
                )
                rows.append(newrow)
            else:
                if selector >= len(rows) or extra not in (1, 2, 3, 4):
                    raise ValueError("Invalid native socket color selection")
                rows[selector]["raw"] = _set_slot(rows[selector], color=extra)
            _consume(
                store,
                db,
                account_id,
                character_id,
                ingredient,
                expected_reference=item["reference"]
                if policy["same_reference_sacrifice"]
                else None,
            )
        else:
            charge_cost = policy["charge_costs"].get(operation, 0)
            if charges < charge_cost:
                raise ValueError("Insufficient local socket charges")
            charges -= charge_cost
            if operation == "increase_count":
                if len(rows) >= template["max_sockets"]:
                    raise ValueError("Socket slot cap reached")
                color = randbelow(4) + 1
                if type(color) is not int or color not in (1, 2, 3, 4):
                    raise ValueError("Random source returned invalid socket color")
                rows.append(
                    {
                        "position": len(rows),
                        "reference": 0,
                        "color": color,
                        "level": 0,
                        "raw": proto_field(80, len(rows)) + proto_field(96, color),
                    }
                )
            elif operation == "change_colors":
                for row in rows:
                    color = randbelow(4) + 1
                    if type(color) is not int or color not in (1, 2, 3, 4):
                        raise ValueError("Random source returned invalid socket color")
                    row["raw"] = _set_slot(row, color=color)
            elif operation == "change_order":
                colors = [row["color"] for row in rows]
                for i in range(len(colors) - 1, 0, -1):
                    j = randbelow(i + 1)
                    if type(j) is not int or not 0 <= j <= i:
                        raise ValueError("Random source returned invalid socket order")
                    colors[i], colors[j] = colors[j], colors[i]
                for row, color in zip(rows, colors):
                    row["raw"] = _set_slot(row, color=color)

        result = _replace_slots(state, rows)
        if operation == "apply_sublimation":
            if not _native_pattern_matches(rows, attachment["colors"]):
                raise ValueError(
                    "Target sockets do not match the native sublimation pattern"
                )
            _consume(
                store,
                db,
                account_id,
                character_id,
                ingredient,
                expected_reference=extra,
                allow_stack=True,
            )
            result = validate(
                _put(list(proto_fields(result)), attachment["tag"], extra)
            )
        elif operation == "remove_sublimation":
            tag = 32 if selector else 24
            if not any(
                field == tag and value != 0 for field, value in proto_fields(result)
            ):
                raise ValueError("Target has no matching sublimation")
            result = validate(_put(list(proto_fields(result)), tag, 0))
        result = validate(_put(list(proto_fields(result)), 72, charges))
        from .inventory_shards import save

        save(db, uid, result)
        db.execute(
            "INSERT INTO inventory_socket_enchantment_receipts "
            "(account_id,character_id,uid,operation,request_hash,prior_state_hash,policy_version,policy_hash,result_state,consumed_uid,cost_kamas,applied_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                account_id,
                character_id,
                uid,
                operation,
                request_hash,
                before_hash,
                policy["version"],
                policy_hash,
                result,
                ingredient,
                cost,
                store.now(),
            ),
        )
        return _published_state(
            store,
            db,
            account_id,
            character_id,
            uid,
            operation,
            result,
            cost_kamas=cost,
            consumed_uid=ingredient,
            applied=True,
        )


def install_bonus(store, account_id, generation, character_id, body):
    """Install the changed native socket bonuses from opcode 13269.

    The request carries each changed slot's bonus reference and cumulative
    shard count. Inventory consumption is an explicit local policy: only the
    additional count for an unchanged bonus is charged; changing or clearing a
    bonus does not refund previously consumed shards.
    """
    target_uid, updates = _decode_bonus_install(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        _guard(db, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (target_uid, character_id),
        ).fetchone()
        if item is None or item["quantity"] != 1:
            raise ValueError("Socket bonus target must be one owned item")
        from .shard_identification import _catalog as socket_catalog, _current_elements

        template = socket_catalog().get(item["reference"])
        if template is None:
            raise ValueError("Socket bonus target is not natively eligible")
        level_row = db.execute(
            "SELECT level FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if level_row is None or level_row["level"] < template["item_level"]:
            raise ValueError(
                "Socket bonus target exceeds the local character-level gate"
            )
        if db.execute(
            "SELECT 1 FROM player_exchange_items WHERE uid=%s LIMIT 1", (target_uid,)
        ).fetchone():
            raise ValueError("Socket bonus target is offered in an exchange")
        if _equipped(store, db, account_id, character_id, target_uid):
            raise ValueError("Unequip socket bonus target before mutation")
        shard = db.execute(
            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s FOR UPDATE",
            (target_uid,),
        ).fetchone()
        if shard is None:
            raise ValueError("Socket bonus target has no identified shard state")
        state = validate(bytes(shard["shard_state"]))
        rows = _slots(state)
        if not template["min_sockets"] <= len(rows) <= template["max_sockets"]:
            raise ValueError(
                "Persisted socket count is outside the native template bounds"
            )
        for row in rows:
            if (
                row["color"] not in (1, 2, 3, 4)
                or row["reference"] < 0
                or row["level"] < 0
                or ((row["reference"] == 0) != (row["level"] == 0))
            ):
                raise ValueError("Persisted native socket bonus state is malformed")
        if any(position >= len(rows) for position in updates):
            raise ValueError("Socket bonus position is outside the identified item")

        settings = db.execute(
            "SELECT value FROM settings WHERE name='socket_bonus_installation_policy'"
        ).fetchone()
        if settings is None:
            raise ValueError("Socket bonus installation policy is unavailable")
        policy = settings["value"]
        if isinstance(policy, str):
            policy = json.loads(policy)
        if (
            not isinstance(policy, dict)
            or type(policy.get("version")) is not int
            or policy["version"] != 1
            or policy.get("source") != "local_policy_native_bonus_installation"
            or policy.get("enabled") is not True
            or type(policy.get("cost_kamas")) is not int
            or policy["cost_kamas"] < 0
            or type(policy.get("request_dedupe_ms")) is not int
            or not 0 <= policy["request_dedupe_ms"] <= 60000
            or policy.get("refund_on_decrease") is not False
        ):
            raise ValueError("Invalid local socket bonus installation policy")

        request_hash = hashlib.sha256(struct.pack(">I", 13269) + body).digest()
        prior = db.execute(
            "SELECT result_state,cost_kamas,consumed FROM inventory_socket_bonus_installation_receipts "
            "WHERE character_id=%s AND uid=%s AND request_hash=%s "
            "AND applied_at >= %s - (%s * interval '1 millisecond') "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE",
            (
                character_id,
                target_uid,
                request_hash,
                store.now(),
                policy["request_dedupe_ms"],
            ),
        ).fetchone()
        if prior is not None:
            state = validate(bytes(shard["shard_state"]))
            applied = False
            cost = prior["cost_kamas"]
            consumed = prior["consumed"]
        else:
            catalog = _bonus_catalog()
            requirements = {}
            changed = False
            for position, (reference, amount) in updates.items():
                row = rows[position]
                old_reference, old_amount = row["reference"], row["level"]
                if (reference, amount) == (old_reference, old_amount):
                    continue
                changed = True
                if reference == 0:
                    if amount != 0:
                        raise ValueError(
                            "Empty native socket bonuses require zero amount"
                        )
                    row["raw"] = _set_slot(row, reference=0, level=0)
                    row["reference"], row["level"] = 0, 0
                    continue
                bonus = catalog.get(reference)
                if bonus is None or not bonus["selectable"]:
                    raise ValueError(
                        "Socket bonus reference is not natively selectable"
                    )
                if row["color"] != 4 and bonus["color"] != row["color"]:
                    raise ValueError(
                        "Socket bonus color is incompatible with the native slot"
                    )
                costs = bonus["costs"]
                eligible_amounts = [
                    cost
                    for cost, minimum in zip(costs, bonus["minimum_levels"])
                    if minimum <= template["item_level"]
                ]
                if not eligible_amounts or amount not in eligible_amounts:
                    raise ValueError(
                        "Socket bonus amount exceeds the native item-level gate"
                    )
                charge = (
                    max(0, amount - old_amount)
                    if old_reference == reference
                    else amount
                )
                if charge:
                    requirements[SHARD_MATERIAL_REFERENCE] = (
                        requirements.get(SHARD_MATERIAL_REFERENCE, 0) + charge
                    )
                row["raw"] = _set_slot(row, reference=reference, level=amount)
                row["reference"], row["level"] = reference, amount

            if not changed:
                # Unchanged confirmations can arrive after the retry window.
                # Publish authoritative state without another receipt or fee.
                character = store.character(account_id, character_id, db)
                from wakfu_server.inventory_move import synchronization
                from wakfu_server.inventory_items import equipment_inventory

                return dict(
                    uid=target_uid,
                    operation="install_bonus",
                    shard_state=state,
                    elements=_current_elements(db, target_uid),
                    inventory_packet=synchronization(character),
                    equipment_packet=equipment_inventory(character),
                    inventory_items=character["inventory_items"],
                    inventory_containers=character["inventory_containers"],
                    wallet_kamas=character["kamas"],
                    cost_kamas=0,
                    consumed=[],
                    applied=False,
                )

            # Validate aggregate inventory availability before consuming any
            # stack. Offer/trade rows are excluded, and all candidate stacks
            # are locked in deterministic UID order.
            consumed = []
            if requirements:
                owned = db.execute(
                    "SELECT uid,reference,quantity FROM inventory_items "
                    "WHERE character_id=%s AND reference=ANY(%s) ORDER BY reference,uid FOR UPDATE",
                    (character_id, list(requirements)),
                ).fetchall()
                blocked = (
                    {
                        row["uid"]
                        for row in db.execute(
                            "SELECT uid FROM player_exchange_items WHERE uid=ANY(%s)",
                            ([item["uid"] for item in owned],),
                        )
                    }
                    if owned
                    else set()
                )
                available = {}
                for row in owned:
                    if row["uid"] in blocked or _equipped(
                        store, db, account_id, character_id, row["uid"]
                    ):
                        continue
                    available[row["reference"]] = (
                        available.get(row["reference"], 0) + row["quantity"]
                    )
                if any(
                    available.get(reference, 0) < amount
                    for reference, amount in requirements.items()
                ):
                    raise ValueError(
                        "Insufficient owned shard items for socket bonus installation"
                    )
                remaining = dict(requirements)
                for row in owned:
                    reference, uid = row["reference"], row["uid"]
                    if uid in blocked or not remaining.get(reference):
                        continue
                    if _equipped(store, db, account_id, character_id, uid):
                        continue
                    take = min(row["quantity"], remaining[reference])
                    if take == row["quantity"]:
                        db.execute("DELETE FROM inventory_items WHERE uid=%s", (uid,))
                    else:
                        db.execute(
                            "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                            (take, uid),
                        )
                    remaining[reference] -= take
                    consumed.append(
                        {"reference": reference, "quantity": take, "uid": uid}
                    )

            cost = policy["cost_kamas"]
            wallet = _wallet(db, account_id)
            if wallet < cost:
                raise ValueError(
                    "Insufficient kamas for local socket bonus installation"
                )
            if cost:
                db.execute(
                    "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s",
                    (cost, account_id),
                )
            result = _replace_slots(state, rows)
            from .inventory_shards import save

            save(db, target_uid, result)
            db.execute(
                "INSERT INTO inventory_socket_bonus_installation_receipts "
                "(account_id,character_id,uid,request_hash,policy_version,result_state,consumed,cost_kamas,applied_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    account_id,
                    character_id,
                    target_uid,
                    request_hash,
                    policy["version"],
                    result,
                    json.dumps(consumed),
                    cost,
                    store.now(),
                ),
            )
            state, applied = result, True

        character = store.character(account_id, character_id, db)
        from wakfu_server.inventory_move import synchronization
        from wakfu_server.inventory_items import equipment_inventory

        inventory_packet = synchronization(character)
        publication = dict(
            uid=target_uid,
            operation="install_bonus",
            shard_state=state,
            elements=_current_elements(db, target_uid),
            inventory_packet=inventory_packet,
            equipment_packet=equipment_inventory(character),
            inventory_items=character["inventory_items"],
            inventory_containers=character["inventory_containers"],
            wallet_kamas=character["kamas"],
            cost_kamas=cost,
            consumed=consumed,
            applied=applied,
        )

        # Validate the native response before committing material consumption.
        from wakfu_server.socket_enchantment_wire import bonus_installation_packets

        bonus_installation_packets(character_id, publication)
        return publication
