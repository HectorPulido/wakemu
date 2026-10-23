"""Native fixed rewards, fragment merges, kamas and XP from owned items.

Source consumption and every resulting mutation share one transaction. Native
requests have no nonce: another valid use of a remaining stack unit is allowed.
Packets are returned only after commit; reconnect restores committed state.
"""
import ast
import operator
import struct
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from .inventory_owner import lock_item_owner
from wakfu_server.wire import proto_fields


ACTION_CLASSES = frozenset(("bHI", "bHS", "bHy", "bHK"))
SOURCE_SHA256 = "b938429022d8d616a14d17cb017e086280799d56112e77269381224b7204842b"


CONTEXT_SHA256 = "4fe02414db38333445932cc251d3ecb444cd4851b43b13bf2605ad57cad5d06f"


@lru_cache(maxsize=1)
def native_use_contexts():
    raw = Path(__file__).with_name("native_simple_item_use_contexts.json").read_bytes()
    if sha256(raw).hexdigest() != CONTEXT_SHA256:
        raise ValueError("Conflicting original simple-item USE contexts")
    return {row["action_id"]: row for row in json.loads(raw)["actions"]}


ZERO_MERGE_REASON = (
    "Native merge quantity is zero; no authoritative positive consumption rule"
)


def normalize_source_consumption(rule, context, *, output_present):
    """Apply the explicit Wakemu floor for a zero-count consuming merge.

    Original bHS stores a count of zero for one quest fragment; its separate
    native source-consumption flag is true. We require one owned source unit
    in that case, without guessing an additional debit for positive counts.
    Keep the immutable original descriptor unchanged for audit and provenance.
    """
    if (
        rule.get("native_class") != "bHS"
        or type(rule.get("required_quantity")) is not int
        or rule["required_quantity"] != 0
        or not isinstance(context, dict)
        or context.get("consume_flag_cqa") is not True
        or output_present is not True
        or rule.get("available") is not False
        or rule.get("unavailable_reason") != ZERO_MERGE_REASON
        or context.get("item_ref") != rule.get("item_ref")
        or context.get("action_id") != rule.get("action_id")
        or context.get("native_class") != "bHS"
        or context.get("action_parameters") != rule.get("action_parameters")
        or rule.get("action_parameters") != ["0", str(rule.get("output_ref"))]
        or type(rule.get("output_ref")) is not int
        or rule["output_ref"] <= 0
        or rule.get("output_quantity") != 1
    ):
        return rule
    return dict(rule, required_quantity=1, available=True, unavailable_reason="")


def _grammar(body, action_id):
    context = native_use_contexts().get(action_id)
    if context is None:
        raise ValueError("Missing qualified native simple item context")
    if context["flag_cqc"] is False:
        if len(body) != 12:
            raise ValueError("Invalid native simple item action grammar")
        return
    # Original bHu.aF: byte0 means no cell, byte1 adds X:int/Y:int/Z:short.
    if not ((len(body) == 13 and body[12] == 0) or (len(body) == 23 and body[12] == 1)):
        raise ValueError("Invalid native positional fragment action grammar")


@lru_cache(maxsize=1)
def _action_classes():
    from .haven_bag_furniture_knowledge import _rules

    classes = {}
    for rule in _rules().values():
        action = rule.get("use_action_id")
        if action is not None:
            classes.setdefault(action, set()).add(rule.get("use_action_class"))
    return classes


def action_class(body):
    """Recognize this family without changing the existing learning grammar."""
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native item action request")
    action, uid = struct.unpack_from(">iq", body)
    if action <= 0 or uid <= 0:
        raise ValueError("Invalid native item action identity")
    classes = _action_classes().get(action, set())
    if not classes & ACTION_CLASSES:
        return None
    if len(classes) != 1:
        raise ValueError("Ambiguous native simple item action grammar")
    _grammar(body, action)
    return next(iter(classes))


def _equipped(character, uid):
    return any(
        tag == 10 and dict(proto_fields(value)).get(8) == uid
        for build in character.get("builds", {}).values()
        for tag, value in proto_fields(bytes.fromhex(build["equipment"]))
    )


def _idle(db, character_id, now):
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Sal del combate para utilizar este objeto")
    if db.execute(
        "SELECT 1 FROM player_exchange_members m JOIN player_exchanges e ON e.id=m.exchange_id "
        "WHERE m.character_id=%s AND (e.state='active' OR "
        "(e.state='invitation' AND e.expires_at>%s)) LIMIT 1",
        (character_id, now),
    ).fetchone():
        raise ValueError("Termina el intercambio para utilizar este objeto")
    if (
        db.execute(
            "SELECT 1 FROM resource_harvest_occupations WHERE character_id=%s "
            "AND expires_at>%s LIMIT 1",
            (character_id, now),
        ).fetchone()
        or db.execute(
            "SELECT 1 FROM craft_occupations WHERE character_id=%s AND state='active' LIMIT 1",
            (character_id,),
        ).fetchone()
    ):
        raise ValueError(
            "Termina la recolección o fabricación para utilizar este objeto"
        )


def criterion_world_identity(character, native_map_id=None):
    """Resolve signed HW identity only from the owned server projection.

    Positive explicit maps retain the ordinary live-scene override contract.
    A private world's positive terrain ID is not its native signed world ID.
    """
    from wakfu_server.guild_haven_world import world_identity

    if (
        type(native_map_id) is int
        and 0 < native_map_id < (1 << 63)
        and "native_world_id" not in character
    ):
        return native_map_id
    actual = world_identity(character)
    if native_map_id is None:
        value = actual
    elif type(native_map_id) is not int or not -(1 << 63) <= native_map_id < (1 << 63):
        raise ValueError("Invalid native item world identity")
    elif actual < 0:
        if native_map_id in (actual, character["map_id"]):
            value = actual
        elif native_map_id > 0:
            # A trusted positive live scene may be a Haven Bag while SQL keeps
            # its physical Haven World origin. Preserve that existing override.
            value = native_map_id
        else:
            raise ValueError("Item world identity differs from owned Haven World")
    elif native_map_id > 0:
        value = native_map_id
    else:
        raise ValueError("Missing owned signed item world identity")
    if value == 0:
        raise ValueError("Missing native item world identity")
    return value


def _criterion(store, db, account_id, character, text, native_map_id):
    """Evaluate only native predicates supported by this item's server context."""
    if not text.strip():
        return True
    from wakfu_server.combat_local_criteria import parse_local_criterion

    tree = parse_local_criterion(text)
    comparisons = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.GtE: operator.ge,
        ast.Gt: operator.gt,
        ast.LtE: operator.le,
        ast.Lt: operator.lt,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool, str):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [visit(value) for value in node.values]
            if any(type(value) is not bool for value in values):
                raise ValueError("Invalid native item criterion Boolean")
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = visit(node.operand)
            if type(value) is bool:
                return not value
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            result = True
            for operation, right_node in zip(node.ops, node.comparators):
                right = visit(right_node)
                if (
                    type(left) is not int
                    or type(right) is not int
                    or type(operation) not in comparisons
                ):
                    raise ValueError("Invalid native item criterion comparison")
                result = comparisons[type(operation)](left, right) and result
                left = right
            return result
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name, args = node.func.id, [visit(arg) for arg in node.args]
            if name == "GetItemQuantity" and len(args) == 1 and type(args[0]) is int:
                return sum(
                    item["quantity"]
                    for item in character["inventory_items"]
                    if item["reference"] == args[0]
                )
            if name == "GetPlayerMaxLevel" and not args:
                # Original eKW reads the server PLAYER_LEVEL_CAP configuration.
                from wakfu_server.combat_max_level_conditions import player_max_level
                from wakfu_server.combat_system_conditions import (
                    fresh_system_configuration,
                )

                return player_max_level(
                    SimpleNamespace(
                        native_system_configuration=fresh_system_configuration()
                    )
                )
            if name == "GetRealLevel" and not args:
                value = character.get("level")
                if type(value) is int and value > 0:
                    return value
            if name == "GetInstanceId" and not args:
                # Native arM is the signed world identity, not terrain/private UID.
                return criterion_world_identity(character, native_map_id)
            if name == "IsAdmin" and not args:
                row = db.execute(
                    "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
                ).fetchone()
                return bool(row and row["is_admin"])
            if name == "GetBooleanSystemConfiguration" and len(args) == 1:
                from wakfu_server.combat_system_conditions import (
                    boolean_system_configuration,
                    fresh_system_configuration,
                )

                return boolean_system_configuration(
                    SimpleNamespace(
                        native_system_configuration=fresh_system_configuration()
                    ),
                    args[0],
                )
        raise ValueError("Unsupported native item criterion")

    value = visit(tree)
    if type(value) is not bool:
        raise ValueError("Native item criterion did not return a Boolean")
    return value


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    """Consume exactly the native quantity and apply one authorized operation."""
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Sal del combate para utilizar este objeto")
    native_class = action_class(body)
    if native_class is None:
        raise ValueError("Unsupported native simple item action")
    action_id, source_uid = struct.unpack_from(">iq", body)
    with store.connection() as db:
        # Match account-wide inventory/cosmetic writers before session locks.
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner_id),
        ).fetchone()
        if item is None:
            raise ValueError("El objeto ya no está disponible")
        rule = db.execute(
            "SELECT * FROM native_simple_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["native_class"] != native_class
            or rule["source_sha256"] != SOURCE_SHA256
        ):
            raise ValueError("El objeto no corresponde a esta acción")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_id") != action_id
            or published.get("use_action_class") != native_class
        ):
            raise ValueError("La acción no coincide con el catálogo activo")
        context = native_use_contexts().get(action_id)
        if context is not None and (
            context["item_ref"] != item["reference"]
            or context["native_class"] != native_class
            or context["action_parameters"] != rule["action_parameters"]
            or context["action_criterion"] != rule["criterion"]
        ):
            raise ValueError("The simple action differs from its original USE context")
        rule = normalize_source_consumption(
            rule, context, output_present=rule["output_ref"] in _rules()
        )
        if not rule["available"]:
            raise ValueError(
                "Este objeto antiguo no tiene una conversión válida en el catálogo actual"
            )
        required = rule["required_quantity"]
        if type(required) is not int or required <= 0 or item["quantity"] < required:
            raise ValueError("No tienes suficientes unidades para utilizar este objeto")
        character = store.character(account_id, owner_id, db)
        if _equipped(character, source_uid):
            raise ValueError("Desequipa el objeto antes de utilizarlo")
        if context is not None and not _criterion(
            store, db, account_id, character, context["use_criterion"], native_map_id
        ):
            raise ValueError("No cumples las condiciones originales de este objeto")
        if not _criterion(
            store, db, account_id, character, rule["criterion"], native_map_id
        ):
            raise ValueError("No cumples las condiciones de este objeto")
        # Fixed rewards honor the original reusable-source flag. Merge actions
        # independently encode their required input count and keep that contract.
        consumed = (
            0
            if native_class == "bHI" and context["consume_flag_cqa"] is False
            else required
        )
        if consumed and item["quantity"] == consumed:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (source_uid, owner_id),
            )
        elif consumed:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s AND character_id=%s",
                (consumed, source_uid, owner_id),
            )
        packets = (
            [(12470, struct.pack(">qh", source_uid, -consumed))] if consumed else []
        )
        if native_class in ("bHI", "bHS"):
            from .item_action_delivery import grant_outputs

            result = grant_outputs(
                store,
                db,
                account_id,
                generation,
                character,
                {rule["output_ref"]: rule["output_quantity"]},
            )
        elif native_class == "bHy":
            from wakfu_server.wire import account_kamas_update

            amount = rule["amount"]
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
                (account_id,),
            ).fetchone()
            if (
                wallet is None
                or type(amount) is not int
                or amount <= 0
                or not 0 <= wallet["kamas"] + amount < 2**63
            ):
                raise ValueError("El saldo de kamas excede el límite permitido")
            balance = wallet["kamas"] + amount
            db.execute(
                "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                (balance, account_id),
            )
            result = dict(
                character=store.character(account_id, owner_id, db),
                packets=[(12753, account_kamas_update(balance))],
            )
        else:
            from wakfu_server.item_progression import award_item_xp

            result = award_item_xp(
                store, db, account_id, generation, owner_id, rule["amount"]
            )
        return dict(
            character=result["character"],
            packets=packets + result["packets"],
            applied=True,
            native_class=native_class,
            consumed=consumed,
        )
