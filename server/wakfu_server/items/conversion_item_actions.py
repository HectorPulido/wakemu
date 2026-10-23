"""Exact native bHF refunds/conversions without discarding enhanced item state."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle

SOURCE_SHA256 = "7551d129a4b5c95a9e83a298727a051cd5edf00fe56e264f1a05818736b74f6d"


@lru_cache(maxsize=1)
def descriptors():
    payload = Path(__file__).with_name("native_item_conversions.json").read_bytes()
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native conversion descriptors")
    return json.loads(payload)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native conversion action header")
    action_id, uid = struct.unpack_from(">iq", body)
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native conversion grammar")
    return "bHF"


def main_product_contract(plan):
    """Require one designated main with the same physical equipment contract."""
    from .equipment import RULES

    source, target = plan["item_ref"], plan["main_reference"]
    if target <= 0 or plan["products"].get(str(target)) != 1:
        raise ValueError("Enhanced conversion requires one designated main product")
    source_rule, target_rule = RULES.get(source), RULES.get(target)
    if (
        source_rule is None
        or target_rule is None
        or not isinstance(source_rule.get("slots"), list)
        or not source_rule["slots"]
        or not isinstance(source_rule.get("occupied_slots"), list)
        or any(
            source_rule.get(key) != target_rule.get(key)
            for key in ("slots", "occupied_slots")
        )
    ):
        raise ValueError("Enhanced conversion equipment contracts differ")
    return target


def identified_contract(plan):
    """Structural authority for the explicit Wakemu chosen-element policy."""
    from .element_selection import _required_counts
    from .equipment_stats import CATALOG

    target = main_product_contract(plan)
    source = plan["item_ref"]
    source_counts, target_counts = _required_counts(source), _required_counts(target)
    source_families = {
        row["generic"]
        for row in CATALOG[source]["effects"]
        if row["generic"] in (1068, 1069)
    }
    target_families = {
        row["generic"]
        for row in CATALOG[target]["effects"]
        if row["generic"] in (1068, 1069)
    }
    if source_counts != target_counts or source_families != target_families:
        raise ValueError("Identified conversion elemental contracts differ")
    return target


def _source_selection(db, item, plan):
    # The chosen-mask branch below is explicit Wakemu preservation policy,
    # not a recovered official bHF inheritance algorithm. Other state remains
    # rejected rather than being discarded or assigned to refund materials.
    for table in ("inventory_mounts", "inventory_pets", "inventory_item_companions"):
        if db.execute(f"SELECT 1 FROM {table} WHERE uid=%s", (item["uid"],)).fetchone():
            raise ValueError(
                "This enhanced item requires a qualified conversion inheritance contract"
            )
    if db.execute(
        "SELECT 1 FROM random_item_use_counters WHERE source_uid=%s", (item["uid"],)
    ).fetchone():
        raise ValueError(
            "A random-use identity requires a qualified conversion inheritance contract"
        )
    elements = db.execute(
        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s FOR UPDATE",
        (item["uid"],),
    ).fetchone()
    if elements and (elements["damage_elements"] or elements["resistance_elements"]):
        if item["quantity"] != 1:
            raise ValueError(
                "Identified conversion requires a single physical source unit"
            )
        from .element_selection import _validate_selection
        from .item_action_delivery import validate_selections

        _validate_selection(
            item["reference"],
            elements["damage_elements"],
            elements["resistance_elements"],
        )
        target = identified_contract(plan)
        return validate_selections(
            {int(ref): quantity for ref, quantity in plan["products"].items()},
            {target: dict(elements)},
        )
    return {}


def _source_shards(db, item, plan):
    row = db.execute(
        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s FOR UPDATE",
        (item["uid"],),
    ).fetchone()
    if row is None:
        return {}
    if item["quantity"] != 1:
        raise ValueError("Socket conversion requires a single physical source")
    target = main_product_contract(plan)
    from .conversion_shard_policy import validate_target

    state = bytes(row["shard_state"])
    validate_target(db, item["reference"], state)
    validate_target(db, target, state)
    return {target: state}


def _source_appearance(db, item, plan):
    row = db.execute(
        "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s FOR UPDATE",
        (item["uid"],),
    ).fetchone()
    if row is None:
        return {}
    target = plan["main_reference"]
    if item["quantity"] != 1 or target <= 0 or plan["products"].get(str(target)) != 1:
        raise ValueError(
            "Appearance conversion requires singleton source and main product"
        )
    from .conversion_appearance_policy import validate_target

    return {
        target: validate_target(db, item["reference"], target, row["appearance_ref"])
    }


def _source_observations(db, item, plan):
    row = db.execute(
        "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s FOR UPDATE",
        (item["uid"],),
    ).fetchone()
    if row is None:
        return {}
    target = plan["main_reference"]
    if target <= 0 or plan["products"].get(str(target)) != 1:
        # Retain the existing ordinary false/false refund-source behavior.
        # There is no compatible physical main for a positive/partial marker.
        if row["unidentified"] is False and row["socketed"] is False:
            return {}
        raise ValueError(
            "Recycling observations require a compatible designated main product"
        )
    from .conversion_observation_policy import validate_pair

    return {target: validate_pair(item["reference"], target, dict(row))}


def use(store, account_id, generation, character_id, body, *, in_fight):
    """Debit one qualified source and grant all native products in one transaction.

    Every resulting physical item inherits an effective source binding. Existing
    typed acquisition providers initialize products; capacity or provider failure
    rolls the complete source debit back. Identified singleton main products
    preserve exact masks under explicit Wakemu policy; other rich state rejects.
    """
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Convert this item outside combat")
    if action_class(body) != "bHF":
        raise ValueError("Unsupported native item conversion")
    action_id, uid = struct.unpack(">iq", body)
    plan = next(row for row in descriptors()["items"] if row["action_id"] == action_id)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, owner_id),
        ).fetchone()
        if (
            item is None
            or item["quantity"] < 1
            or item["reference"] != plan["item_ref"]
        ):
            raise ValueError("The source does not match this native conversion")
        rule = db.execute(
            "SELECT * FROM native_conversion_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["source_sha256"] != SOURCE_SHA256
            or rule["products"] != plan["products"]
            or rule["main_reference"] != plan["main_reference"]
        ):
            raise ValueError("The native conversion authority has changed")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_class") != "bHF"
            or published.get("use_action_id") != action_id
        ):
            raise ValueError("The conversion differs from the active native catalog")
        character = store.character(account_id, owner_id, db)
        from .exchange_rules import ITEMS
        from .simple_item_actions import _criterion

        template = ITEMS.get(str(item["reference"]))
        if template is None or not isinstance(template.get("raw_criteria"), dict):
            raise ValueError("Missing native conversion USE authority")
        use_criterion = template["raw_criteria"].get("USE")
        if use_criterion is not None and not isinstance(use_criterion, str):
            raise ValueError("Invalid native conversion USE criterion")
        for criterion in (use_criterion or "", plan["criterion"]):
            if not _criterion(
                store, db, account_id, character, criterion, character["map_id"]
            ):
                raise ValueError(
                    "The native conversion use conditions are not satisfied"
                )
        if _equipped(character, uid):
            raise ValueError("Unequip this item in every build before converting it")
        if db.execute(
            "SELECT 1 FROM inventory_containers WHERE uid=%s AND character_id=%s",
            (uid, owner_id),
        ).fetchone():
            raise ValueError("Remove the equipped container before converting it")
        selections = _source_selection(db, item, plan)
        shards = _source_shards(db, item, plan)
        appearances = _source_appearance(db, item, plan)
        observations = _source_observations(db, item, plan)
        from wakfu_server.combat_drop_delivery import _binding_rows, _effective_bound

        source = dict(item, bound=_binding_rows(db, [item]).get(uid, False))
        bound = _effective_bound(source)
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (uid, owner_id),
            )
        from .item_action_delivery import grant_outputs

        result = grant_outputs(
            store,
            db,
            account_id,
            generation,
            character,
            {int(ref): quantity for ref, quantity in plan["products"].items()},
            force_bound=bound,
            selections_by_reference=selections or None,
            shards_by_reference=shards or None,
            appearances_by_reference=appearances or None,
            observations_by_reference=observations or None,
        )
        return dict(
            result,
            packets=[(12470, struct.pack(">qh", uid, -1)), *result["packets"]],
            native_class="bHF",
            applied=True,
            consumed=1,
            source_uid=uid,
            source_reference=item["reference"],
            products=plan["products"],
            main_reference=plan["main_reference"],
            binding_inherited=bound,
            preserved_selections=selections,
            preserved_shards=shards,
            preserved_appearances=appearances,
            preserved_observations=observations,
        )
