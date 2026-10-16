"""Retry-safe local policy adapter for native socket-identification data.

The installed client contains fpK count/color weights, but the original
server-side 13787 policy was not recovered. This module applies those weights
as an explicit, configurable local policy; it does not claim upstream parity.
"""
from wakfu_server import native_catalog as protocol_catalog
from contextlib import ExitStack
import hashlib
import json
import secrets
from contextlib import nullcontext

from wakfu_server.paths import DATA_ROOT
from wakfu_server.wire import proto_field
from .inventory_owner import lock_item_owner
from .inventory_shards import save, validate

CATALOG_PATH = DATA_ROOT / "item-socket-templates.json"
_CATALOG = None
_EXPECTED_CATALOG_HASH = (
    "f1b15107d8156fce1c4e901dadf92e27d7d0cd4f985a5a036c983eddcf128bfa"
)


def _catalog():
    global _CATALOG
    if _CATALOG is None:
        raw = protocol_catalog.read_bytes(CATALOG_PATH)
        if hashlib.sha256(raw).hexdigest() != _EXPECTED_CATALOG_HASH:
            raise ValueError("Native socket eligibility catalog fingerprint mismatch")
        data = json.loads(raw)
        source = data.get("source", {})
        if source.get("client_jar_sha256") != (
            "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
        ):
            raise ValueError("Unexpected native socket catalog source")
        rows = {}
        for row in data.get("templates", []):
            ref = row.get("reference")
            minimum, maximum = row.get("min_sockets"), row.get("max_sockets")
            level = row.get("item_level")
            if (
                type(ref) is not int
                or ref <= 0
                or ref in rows
                or type(minimum) is not int
                or type(maximum) is not int
                or not 0 <= minimum <= maximum <= 4
                or type(level) is not int
                or level < 0
            ):
                raise ValueError("Malformed native socket template")
            rows[ref] = dict(
                reference=ref,
                item_level=level,
                min_sockets=minimum,
                max_sockets=maximum,
            )
        if len(rows) != data.get("count") or not rows:
            raise ValueError("Incomplete native socket catalog")
        _CATALOG = rows
    return _CATALOG


def _policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='socket_identification_policy'"
    ).fetchone()
    if row is None:
        raise ValueError("Socket identification policy is unavailable")
    policy = row["value"]
    if isinstance(policy, str):
        policy = json.loads(policy)
    if (
        not isinstance(policy, dict)
        or type(policy.get("version")) is not int
        or policy["version"] != 1
    ):
        raise ValueError("Unsupported socket identification policy")
    if policy.get("source") != "local_policy_native_fpK_utility":
        raise ValueError("Unrecognized socket identification policy source")
    counts = policy.get("count_weights")
    colors = policy.get("color_weights")
    if (
        not isinstance(counts, dict)
        or set(counts) != {"0", "1", "2", "3"}
        or not isinstance(colors, dict)
        or set(colors) != {"1", "2", "3", "4"}
        or any(
            type(v) is not int or v < 0 for v in (*counts.values(), *colors.values())
        )
        or sum(counts.values()) <= 0
        or sum(colors.values()) <= 0
        or type(policy.get("cost_kamas")) is not int
        or policy["cost_kamas"] < 0
        or policy.get("minimum_level") != "item_level"
        or type(policy.get("charge")) is not int
        or policy["charge"] != 0
    ):
        raise ValueError("Invalid socket identification policy")
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
    return policy, hashlib.sha256(canonical).digest()


def _weighted(weights, randbelow):
    total = sum(weights.values())
    draw = randbelow(total)
    if type(draw) is not int or not 0 <= draw < total:
        raise ValueError("Random source returned an invalid draw")
    # jsonb does not preserve object key order; native numeric enum order is
    # the stable draw mapping across database reloads.
    for value in sorted(weights, key=int):
        weight = weights[value]
        if draw < weight:
            return int(value)
        draw -= weight
    raise ValueError("Invalid weighted selection")


def _shard_state(template, policy, randbelow):
    # fpK.a clamps a native QG result to the template's cpR..cpS bounds.
    requested = _weighted(policy["count_weights"], randbelow)
    count = min(template["max_sockets"], max(template["min_sockets"], requested))
    slots = []
    for position in range(count):
        color = _weighted(policy["color_weights"], randbelow)
        # Native slot fields: position=10, item ref=11 (empty), color=12,
        # attached shard quantity=14 (empty). ProtoShard repeated slots=1.
        row = proto_field(80, position) + proto_field(88, 0) + proto_field(96, color)
        slots.append(proto_field(10, row))
    return validate(b"".join(slots))


def _current_elements(db, uid):
    row = db.execute(
        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
        (uid,),
    ).fetchone()
    if row is None:
        return b""
    damage, resistance = row["damage_elements"], row["resistance_elements"]
    if (
        type(damage) is not int
        or type(resistance) is not int
        or not 0 <= damage <= 30
        or not 0 <= resistance <= 30
    ):
        raise ValueError("Invalid persisted elemental selection")
    return bytes((damage, resistance))


def _wallet_balance(db, account_id):
    row = db.execute(
        "SELECT kamas FROM account_wallets WHERE account_id=%s", (account_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Socket identification wallet is unavailable")
    return row["kamas"]


def identify(
    store, account_id, generation, character_id, body, *, randbelow=None, db=None
):
    """Apply local 13787 policy once to one owned, unstacked inventory UID.

    `status` uses only the client-confirmed 13766 ordinals: 0 success and 2
    identification outcomes. Successful operations separate one unit when necessary,
    keeping the requested UID and publishing the remainder through the native
    bag snapshot. Capacity failures raise a domain error without charging or
    changing inventory.
    """
    if not isinstance(body, bytes) or len(body) != 8:
        raise ValueError("Invalid native socket identification request")
    uid = int.from_bytes(body, "big", signed=True)
    if uid <= 0:
        raise ValueError("Invalid native socket identification UID")
    randbelow = secrets.randbelow if randbelow is None else randbelow
    # Element selection also identifies sockets. Share its transaction so
    # the choice, sockets, receipt, and optional charge commit together.
    transaction = store.connection() if db is None else nullcontext(db)
    with transaction as db, ExitStack() as mutation_scopes:
        character_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        from wakfu_server.item_mutation import refresh_equipment_after_mutation

        mutation_scopes.enter_context(
            refresh_equipment_after_mutation(store, db, account_id, character_id, uid)
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
            raise ValueError("Socket identification is unavailable during combat")
        if (
            db.execute(
                "SELECT 1 FROM player_exchange_members WHERE character_id=%s LIMIT 1",
                (character_id,),
            ).fetchone()
            is not None
        ):
            raise ValueError("Socket identification is unavailable during exchange")

        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Socket identification item is unavailable or foreign")
        if (
            db.execute(
                "SELECT 1 FROM player_exchange_items WHERE uid=%s LIMIT 1", (uid,)
            ).fetchone()
            is not None
        ):
            raise ValueError("Socket identification item is offered in an exchange")
        # Serialize duplicates on the owned item row. A receipt never grants
        # access after the UID transfers or is deleted, and current socket
        # state wins over the historical first-identification bytes.
        prior = db.execute(
            "SELECT id,cost_kamas FROM inventory_socket_identification_receipts "
            "WHERE account_id=%s AND character_id=%s AND uid=%s FOR UPDATE",
            (account_id, character_id, uid),
        ).fetchone()
        if prior is not None:
            shard_row = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s FOR UPDATE",
                (uid,),
            ).fetchone()
            if shard_row is None:
                raise ValueError(
                    "Socket identification receipt has no current shard state"
                )
            state = validate(bytes(shard_row["shard_state"]))
            from wakfu_server.equipment_stacks import ensure_singleton

            ensure_singleton(db, character_id, uid)
            return dict(
                character_id=character_id,
                uid=uid,
                status=0,
                shard_state=state,
                applied=False,
                elements=_current_elements(db, uid),
                cost_kamas=prior["cost_kamas"],
                wallet_kamas=_wallet_balance(db, account_id),
                receipt_id=prior["id"],
            )
        existing = db.execute(
            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s FOR UPDATE",
            (uid,),
        ).fetchone()
        if existing is not None:
            # Already identified state may arrive from an exchange or a legacy
            # owner. Return it unchanged rather than generating or charging.
            state = validate(bytes(existing["shard_state"]))
            from wakfu_server.equipment_stacks import ensure_singleton

            ensure_singleton(db, character_id, uid)
            return dict(
                character_id=character_id,
                uid=uid,
                status=0,
                shard_state=state,
                applied=False,
                elements=_current_elements(db, uid),
                cost_kamas=0,
                wallet_kamas=_wallet_balance(db, account_id),
                receipt_id=None,
            )
        template = _catalog().get(item["reference"])
        if template is None:
            raise ValueError("Item is not eligible for native socket identification")
        character = db.execute(
            "SELECT level FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if character is None:
            raise ValueError("Socket identification owner is unavailable")
        policy, policy_hash = _policy(db)
        cost = policy["cost_kamas"]
        wallet = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if wallet is None or wallet["kamas"] < cost:
            # 13766 status 1 is named NO_ENOUGH_SPACE, not insufficient funds;
            # do not mislabel an economic failure with that native status.
            raise ValueError("Insufficient local-policy kamas")
        from wakfu_server.equipment_stacks import ensure_singleton

        item = ensure_singleton(db, character_id, uid)
        state = _shard_state(template, policy, randbelow)
        if cost:
            db.execute(
                "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s",
                (cost, account_id),
            )
        save(db, uid, state)
        receipt = db.execute(
            "INSERT INTO inventory_socket_identification_receipts "
            "(account_id,character_id,uid,reference,policy_version,policy_hash,shard_state,cost_kamas,applied_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                account_id,
                character_id,
                uid,
                item["reference"],
                policy["version"],
                policy_hash,
                state,
                cost,
                store.now(),
            ),
        ).fetchone()
        return dict(
            character_id=character_id,
            uid=uid,
            status=0,
            shard_state=state,
            applied=True,
            elements=_current_elements(db, uid),
            cost_kamas=cost,
            wallet_kamas=wallet["kamas"] - cost,
            receipt_id=receipt["id"],
        )
