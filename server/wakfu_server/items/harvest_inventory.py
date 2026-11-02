"""Grant verified harvest products inside the caller's leased transaction."""
import struct

from .inventory_items import insertion
from .inventory_move import STACKS
from .inventory_uids import allocate


def grant_products(db, character, products):
    """Plan every ordinary output before writes; preserve each native packet."""
    from . import quest_inventory
    from .inventory_product_placement import plan, plain_stack

    if not isinstance(products, dict) or not products:
        raise ValueError("Invalid harvest products")
    ordinary, quests = {}, {}
    for reference, quantity in products.items():
        if (
            type(reference) is not int
            or reference <= 0
            or type(quantity) is not int
            or not 1 <= quantity <= 32767
        ):
            raise ValueError("Invalid harvest product")
        if reference in quest_inventory.REFERENCES:
            quests[reference] = quantity
        else:
            if reference not in STACKS:
                raise ValueError("Unsupported native harvest stack quantity")
            ordinary[reference] = quantity
    placements = (
        plan(
            character,
            ordinary,
            stack_rules=STACKS,
            mergeable=plain_stack,
        )
        if ordinary
        else []
    )
    items, packets, grants = [], [], []
    original = {item["uid"]: item for item in character["inventory_items"]}
    for placement in placements:
        existing = original.get(placement["uid"])
        item = dict(
            uid=existing["uid"] if existing else allocate(db),
            character_id=character["id"],
            reference=placement["reference"],
            quantity=placement["quantity"],
            container=placement["container"],
            slot=placement["slot"],
        )
        if existing is not None:
            db.execute(
                "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
                (item["quantity"], item["uid"], character["id"]),
            )
            packet = 12470, struct.pack(">qh", item["uid"], placement["added"])
        else:
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
        items.append(item)
        packets.append(packet)
        grants.append(dict(item, added=placement["added"]))
    for reference, quantity in sorted(quests.items()):
        item = quest_inventory.grant(db, character["id"], reference, quantity)
        items.append(item)
        packets.append(item["quest_packet"])
        grants.append(
            {
                key: value
                for key, value in dict(item, added=quantity).items()
                if key != "quest_packet"
            }
        )
    return dict(items=items, packets=packets, grants=grants)


def grant(db, character, reference, quantity):
    """Legacy single-product keys accompany complete packet/item/grant lists."""
    result = grant_products(db, character, {reference: quantity})
    return dict(result, item=result["items"][0], packet=result["packets"][0])
