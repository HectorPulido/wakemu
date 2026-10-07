"""Pure ordinary-craft material and output planner.

This module does not authorize recipes or interpret native criteria, flags,
fees, secret-discovery rules, or crafting outcomes. Callers must perform those
checks before using its plan. It only computes deterministic ingredient
consumption and default product placement against one owned character's bags.
"""
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
import json

from wakfu_server.paths import DATA_ROOT

STACKS = {
    row["reference"]: row
    for row in json.loads((DATA_ROOT / "item-stack-rules.json").read_text())["items"]
}


_BAG_KINDS = frozenset((0, 1, 2, 3))
_BASE_ITEM_FIELDS = frozenset(
    ("uid", "character_id", "reference", "quantity", "container", "slot")
)


def _positive_int(value):
    return type(value) is int and value > 0


def _equipped_uids(builds):
    from wakfu_server.wire import proto_fields

    try:
        rows = list(builds.values() if isinstance(builds, Mapping) else builds)
    except TypeError:
        raise ValueError("Invalid crafting equipment builds") from None
    if isinstance(builds, (str, bytes)):
        raise ValueError("Invalid crafting equipment builds")

    equipped = set()
    for build in rows:
        if not isinstance(build, dict) or not isinstance(build.get("equipment"), str):
            raise ValueError("Invalid crafting equipment build")
        try:
            equipment = bytes.fromhex(build["equipment"])
            fields = proto_fields(equipment)
            for tag, value in fields:
                if tag != 10:
                    continue
                uid = dict(proto_fields(value)).get(8)
                if not _positive_int(uid):
                    raise ValueError
                equipped.add(uid)
        except (ValueError, TypeError):
            raise ValueError("Invalid crafting equipment snapshot") from None
    return equipped


def _recipe(catalog, recipe_id):
    if type(recipe_id) is not int or recipe_id <= 0:
        raise ValueError("Invalid crafting recipe identity")
    recipes = getattr(catalog, "recipes", catalog)
    if not isinstance(recipes, Mapping):
        raise ValueError("Invalid crafting recipe catalog")
    recipe = recipes.get(recipe_id)
    if not isinstance(recipe, dict) or recipe.get("recipe_id") != recipe_id:
        raise ValueError("Unknown native crafting recipe")
    return recipe


def plan(
    catalog,
    recipe_id,
    batch_count,
    *,
    character_id,
    items,
    containers,
    builds,
    protected_uids=()
):
    """Plan material use and product placement without mutating inputs.

    Items may be consumed only from this character's regular inventory bags
    (native container kinds 0..3), and are selected deterministically by bag
    kind, slot, then UID. A UID equipped by *any* saved build or explicitly
    protected by an active transfer/offer cannot be used. Consumed item rows
    remain intact in the returned ``final_items`` until their whole quantity
    is removed; all non-consumed metadata is copied through unchanged.

    Output products are merged only into bare, mergeable stacks. New product
    stacks are placed in the first free bag slots after ingredient consumption.
    The planner allocates no UIDs and performs no writes.
    """
    if not _positive_int(character_id):
        raise ValueError("Invalid crafting inventory owner")
    if type(batch_count) is not int or not 1 <= batch_count <= 32767:
        raise ValueError("Invalid crafting batch quantity")
    if not isinstance(items, (list, tuple)) or not isinstance(
        containers, (list, tuple)
    ):
        raise ValueError("Crafting inventory snapshot is unavailable")
    if not isinstance(protected_uids, (set, frozenset, list, tuple)):
        raise ValueError("Invalid protected crafting item identities")
    protected = set(protected_uids)
    if any(not _positive_int(uid) for uid in protected):
        raise ValueError("Invalid protected crafting item identity")

    recipe = _recipe(catalog, recipe_id)
    ingredients, products = recipe.get("ingredients"), recipe.get("products")
    if (
        not isinstance(ingredients, list)
        or not ingredients
        or not isinstance(products, list)
        or not products
    ):
        raise ValueError("Incomplete native crafting recipe")

    required = defaultdict(int)
    for ingredient in ingredients:
        if (
            not isinstance(ingredient, dict)
            or not _positive_int(ingredient.get("item_id"))
            or not _positive_int(ingredient.get("quantity"))
        ):
            raise ValueError("Invalid native crafting ingredient")
        required[ingredient["item_id"]] += ingredient["quantity"] * batch_count

    product_totals = defaultdict(int)
    for product in products:
        if (
            not isinstance(product, dict)
            or not _positive_int(product.get("item_id"))
            or not _positive_int(product.get("quantity"))
        ):
            raise ValueError("Invalid native crafting product")
        product_totals[product["item_id"]] += product["quantity"] * batch_count

    bag_by_uid = {}
    seen_kinds = set()
    for bag in containers:
        if not isinstance(bag, dict):
            raise ValueError("Invalid crafting inventory container")
        uid, owner, kind, capacity = (
            bag.get(key) for key in ("uid", "character_id", "kind", "capacity")
        )
        if (
            not _positive_int(uid)
            or uid in bag_by_uid
            or type(owner) is not int
            or owner != character_id
            or type(kind) is not int
            or kind < 0
            or kind > 127
            or type(capacity) is not int
            or not 1 <= capacity <= 32767
        ):
            raise ValueError("Invalid owned crafting inventory container")
        if kind in seen_kinds:
            raise ValueError("Duplicate owned crafting inventory container kind")
        seen_kinds.add(kind)
        bag_by_uid[uid] = dict(bag)

    equipped = _equipped_uids(builds)
    original = {}
    eligible = []
    seen_slots = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid owned crafting item")
        uid, owner, reference, quantity = (
            item.get(key) for key in ("uid", "character_id", "reference", "quantity")
        )
        container, slot = item.get("container"), item.get("slot")
        bag = bag_by_uid.get(container)
        if (
            not _positive_int(uid)
            or uid in original
            or type(owner) is not int
            or owner != character_id
            or not _positive_int(reference)
            or type(quantity) is not int
            or quantity <= 0
            or type(container) is not int
            or type(slot) is not int
            or slot < 0
            or bag is None
        ):
            raise ValueError("Invalid owned crafting item row")
        stack = STACKS.get(reference)
        if stack is None or quantity > stack["maximum"]:
            raise ValueError("Unknown or oversized native crafting stack")
        if slot >= bag["capacity"]:
            raise ValueError("Crafting item is outside its owned bag")
        if (container, slot) in seen_slots:
            raise ValueError("Duplicate occupied crafting inventory slot")
        seen_slots.add((container, slot))
        original[uid] = deepcopy(item)
        if bag["kind"] in _BAG_KINDS:
            eligible.append((bag["kind"], slot, uid, reference, quantity))

    protected.update(equipped)
    final_items = deepcopy(original)
    consumed = []
    for reference, amount in sorted(required.items()):
        available = 0
        candidates = [
            row for row in eligible if row[3] == reference and row[2] not in protected
        ]
        for _, _, uid, _, quantity in candidates:
            available += quantity
        if available < amount:
            raise ValueError("Insufficient unprotected crafting ingredients")
        remaining = amount
        for _, _, uid, _, _ in candidates:
            if remaining == 0:
                break
            current = final_items[uid]["quantity"]
            used = min(current, remaining)
            remaining -= used
            after = current - used
            consumed.append(dict(uid=uid, quantity=used))
            if after:
                final_items[uid]["quantity"] = after
            else:
                del final_items[uid]

    by_product = []
    occupancy = defaultdict(set)
    for item in final_items.values():
        occupancy[item["container"]].add(item["slot"])
    ordered_bags = sorted(
        (bag for bag in bag_by_uid.values() if bag["kind"] in _BAG_KINDS),
        key=lambda bag: (bag["kind"], bag["uid"]),
    )
    for reference, total in sorted(product_totals.items()):
        rule = STACKS.get(reference)
        if rule is None or type(rule.get("maximum")) is not int or rule["maximum"] <= 0:
            raise ValueError("Unknown native crafting product stack rule")
        remaining = total
        if rule.get("minimal_mergeable") is True:
            for _, _, uid, existing_ref, _ in sorted(eligible):
                target = final_items.get(uid)
                if (
                    target is None
                    or existing_ref != reference
                    or uid in protected
                    or set(target) - _BASE_ITEM_FIELDS
                ):
                    continue
                moved = min(remaining, rule["maximum"] - target["quantity"])
                if moved <= 0:
                    continue
                target["quantity"] += moved
                by_product.append(
                    dict(
                        reference=reference,
                        quantity=moved,
                        container=target["container"],
                        slot=target["slot"],
                        merge_uid=uid,
                    )
                )
                remaining -= moved
                if not remaining:
                    break
        while remaining:
            destination = None
            for bag in ordered_bags:
                slot = next(
                    (
                        candidate
                        for candidate in range(bag["capacity"])
                        if candidate not in occupancy[bag["uid"]]
                    ),
                    None,
                )
                if slot is not None:
                    destination = (bag["uid"], slot)
                    break
            if destination is None:
                raise ValueError("Crafting product inventory is full")
            amount = min(remaining, rule["maximum"])
            remaining -= amount
            container, slot = destination
            occupancy[container].add(slot)
            by_product.append(
                dict(
                    reference=reference,
                    quantity=amount,
                    container=container,
                    slot=slot,
                    merge_uid=None,
                )
            )

    return dict(
        recipe_id=recipe_id,
        batch_count=batch_count,
        consumed=consumed,
        product_placements=by_product,
        final_items=sorted(final_items.values(), key=lambda row: row["uid"]),
    )
