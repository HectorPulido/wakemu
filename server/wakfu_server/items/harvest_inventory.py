"""Grant a verified harvest product inside the caller's leased transaction."""
import struct

from .inventory_elements import masks
from .inventory_items import insertion
from .inventory_move import STACKS
from .inventory_uids import allocate


def grant(db, character, reference, quantity):
    """Preserve native stacks and fail before mutation when pockets are full.

    The caller locks the owning session/character and commits the product with
    its resource transition and reward receipt. This helper does not open a
    second transaction or accept a client-selected destination.
    """
    if (
        type(reference) is not int
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid harvest product")
    rule = STACKS.get(reference)
    if rule is None or quantity > rule["maximum"]:
        raise ValueError("Unsupported native harvest stack quantity")
    base = character["inventory_containers"][0]
    existing = next(
        (
            item
            for item in character["inventory_items"]
            if item["container"] == base["uid"]
            and item["reference"] == reference
            and rule["minimal_mergeable"]
            and masks(item) is None
            and "mount" not in item
            and item["quantity"] + quantity <= rule["maximum"]
        ),
        None,
    )
    occupied = {
        item["slot"]
        for item in character["inventory_items"]
        if item["container"] == base["uid"]
    }
    slot = next(
        (value for value in range(base["capacity"]) if value not in occupied), None
    )
    if existing is None and slot is None:
        raise ValueError("Base inventory full")
    item = dict(
        uid=existing["uid"] if existing else allocate(db),
        character_id=character["id"],
        reference=reference,
        quantity=quantity + (existing["quantity"] if existing else 0),
        container=base["uid"],
        slot=existing["slot"] if existing else slot,
    )
    if existing is not None:
        db.execute(
            "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
            (item["quantity"], item["uid"], character["id"]),
        )
        packet = 12470, struct.pack(">qh", item["uid"], quantity)
    else:
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            tuple(
                item[k]
                for k in (
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
    return dict(item=item, packet=packet)
