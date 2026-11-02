"""Pure product placement into owned, natively supported ordinary containers."""
from copy import deepcopy


def containers(character):
    from wakfu_server.combat_drop_delivery import _container_can_hold

    return [
        bag
        for bag in sorted(
            character["inventory_containers"], key=lambda row: (row["kind"], row["uid"])
        )
        if _container_can_hold(bag, character["id"])
    ]


def plain_stack(item):
    """A fresh plain product must not absorb an instance's richer attributes."""
    from .inventory_elements import masks

    return (
        masks(item) is None
        and not item.get("bound", False)
        and not item.get("appearance_ref", 0)
        and not item.get("_custody_metadata")
        and item.get("shard_state") is None
        and all(key not in item for key in ("mount", "pet", "companion_xp"))
    )


def equipped_uids(character):
    from wakfu_server.wire import proto_fields

    result = set()
    for build in character.get("builds", {}).values():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 10:
                uid = dict(proto_fields(value)).get(8)
                if type(uid) is not int or uid <= 0:
                    raise ValueError("Invalid owned equipment UID")
                result.add(uid)
    return result


def plan(
    character,
    products,
    *,
    stack_rules,
    mergeable,
    excluded_uids=(),
    whole_quantity=False
):
    """Validate all products before allocation, writes or source consumption."""
    bags = containers(character)
    items = deepcopy(character["inventory_items"])
    excluded_uids = set(excluded_uids) | equipped_uids(character)
    placements = []
    for reference in sorted(products):
        remaining = products[reference]
        rule = stack_rules.get(reference)
        if (
            type(reference) is not int
            or reference <= 0
            or type(remaining) is not int
            or remaining < 0
            or rule is None
            or (whole_quantity and remaining > rule["maximum"])
        ):
            raise ValueError("Unsupported native product stack quantity")
        maximum = rule["maximum"]
        while remaining:
            resident = next(
                (
                    item
                    for bag in bags
                    for item in sorted(items, key=lambda row: (row["slot"], row["uid"]))
                    if item["container"] == bag["uid"]
                    and item["character_id"] == character["id"]
                    and 0 <= item["slot"] < bag["capacity"]
                    and item["reference"] == reference
                    and item["uid"] not in excluded_uids
                    and rule["minimal_mergeable"]
                    and mergeable(item)
                    and 0 < item["quantity"] < maximum
                    and (not whole_quantity or item["quantity"] + remaining <= maximum)
                ),
                None,
            )
            if resident is not None:
                amount = min(remaining, maximum - resident["quantity"])
                resident["quantity"] += amount
                placements.append(
                    dict(
                        uid=resident["uid"],
                        reference=reference,
                        container=resident["container"],
                        slot=resident["slot"],
                        quantity=resident["quantity"],
                        added=amount,
                    )
                )
            else:
                destination = None
                for bag in bags:
                    occupied = {
                        item["slot"]
                        for item in items
                        if item["container"] == bag["uid"]
                    }
                    slot = next(
                        (
                            slot
                            for slot in range(bag["capacity"])
                            if slot not in occupied
                        ),
                        None,
                    )
                    if slot is not None:
                        destination = bag["uid"], slot
                        break
                if destination is None:
                    raise ValueError(
                        "Base inventory full: no supported ordinary bag space"
                    )
                amount = min(remaining, maximum)
                placement = dict(
                    uid=None,
                    reference=reference,
                    container=destination[0],
                    slot=destination[1],
                    quantity=amount,
                    added=amount,
                )
                placements.append(placement)
                items.append(
                    dict(placement, uid=-len(placements), character_id=character["id"])
                )
            remaining -= amount
    return placements
