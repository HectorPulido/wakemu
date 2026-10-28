"""Native exploration artifact access, independently of quest rewards.

The installed client stores all eleven artifacts in ACCOUNT_QUEST inventory
(type 21), not character QUEST inventory. The global policy is projected on
canonical character loads, covering old and newly created characters alike.
"""
import struct

SETTING = "exploration_secret_access_policy"
# Native table 133/aNp -> bOM: secret ID, suggested level, account item ref.
SECRETS = (
    (6, 10, 18722),
    (9, 45, 20784),
    (4, 50, 18384),
    (8, 65, 19434),
    (10, 80, 21598),
    (11, 90, 21599),
    (1, 115, 18103),
    (3, 120, 18385),
    (5, 140, 18591),
    (7, 170, 19113),
    (12, 185, 22087),
)
ITEM_REFS = tuple(record[2] for record in SECRETS)
# eHQ native enum; all have no fight-property fallback (fxg == -1).
MOVEMENT_PROPERTIES = (85, 105, 117, 118)


def validate_policy(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "unlock_all"}
        or type(value.get("version")) is not int
        or value["version"] != 1
        or type(value.get("unlock_all")) is not bool
    ):
        raise ValueError("Invalid exploration secret access policy")
    return value["unlock_all"]


def load(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    enabled = validate_policy(None if row is None else row["value"])
    return {
        "account_item_refs": ITEM_REFS if enabled else (),
        "world_properties": MOVEMENT_PROPERTIES if enabled else (),
    }


def world_properties(character):
    """Owned rK/rN/wU/wV component, with one reference per exploration power."""
    state = character.get("exploration_secrets")
    if state is None:
        return None
    selected = state.get("world_properties")
    if (
        not isinstance(selected, (tuple, list))
        or any(
            type(identity) is not int or identity not in MOVEMENT_PROPERTIES
            for identity in selected
        )
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("Invalid owned exploration movement properties")
    if not selected:
        return b"\x00"
    return (
        b"\x01"
        + struct.pack(">H", len(selected))
        + bytes(value for identity in selected for value in (identity, 1))
    )


def account_packet(db, account_id=None):
    """13873/eDS.INVENTORY/flY absolute account quest-item snapshot.

    Projected exploration artifacts and persisted owned account quest items
    share the native snapshot. Neither uses bag slots or equipment sheets.
    """
    selected = load(db)["account_item_refs"]
    quantities = {identity: 1 for identity in selected}
    if account_id is not None:
        from wakfu_server.items.account_quest_inventory import load as load_owned

        for item in load_owned(db, account_id):
            quantities[item["reference"]] = max(
                quantities.get(item["reference"], 0), item["quantity"]
            )
    rows = []
    for identity, quantity in quantities.items():
        row = b"\x08" + _varint(identity) + b"\x10" + _varint(quantity)
        rows.append(b"\x0a" + _varint(len(row)) + row)
    proto = b"".join(rows)
    return 13873, struct.pack(">III", 1, 4, len(proto)) + proto


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def account_quantity(character, references):
    """Native eKE adds account quantities once per requested int32 reference."""
    if character is None:
        return 0
    state = character.get("exploration_secrets")
    owned = () if state is None else state.get("account_item_refs")
    if (
        not isinstance(owned, (tuple, list))
        or any(
            type(identity) is not int or identity not in ITEM_REFS for identity in owned
        )
        or len(set(owned)) != len(owned)
    ):
        raise ValueError("Invalid owned exploration account items")
    quantities = {identity: 1 for identity in owned}
    from wakfu_server.items.account_quest_inventory import validate

    seen = set()
    for row in character.get("account_quest_items", ()):
        if not isinstance(row, dict) or row.get("reference") in seen:
            raise ValueError("Invalid owned native account quest items")
        validate(row.get("account_id"), row.get("reference"), row.get("quantity"))
        if row["account_id"] != character.get("account_id"):
            raise ValueError("Foreign native account quest item")
        quantities[row["reference"]] = max(
            quantities.get(row["reference"], 0), row["quantity"]
        )
        seen.add(row["reference"])
    total = 0
    for reference in references:
        if type(reference) is not int or not -(2**63) <= reference < 2**63:
            raise ValueError("Native item reference requires signed long")
        narrowed = ((reference + 2**31) % 2**32) - 2**31
        total += quantities.get(narrowed, 0)
    return ((total + 2**31) % 2**32) - 2**31


def projected_transport_access(character, reference, quantity):
    """Projected exploration powers authorize travel without spending an item."""
    if reference not in ITEM_REFS:
        return False
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("Invalid exploration transport quantity")
    state = character.get("exploration_secrets")
    if state is not None and not isinstance(state, dict):
        raise ValueError("Invalid owned exploration account items")
    available = account_quantity(character, (reference,))
    selected = () if state is None else state["account_item_refs"]
    return reference in selected and available >= quantity
