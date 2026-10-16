"""Native exchange-machine purchases in one owned inventory transaction."""
from collections import defaultdict
from functools import lru_cache
import struct

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def catalog():
    document = native_catalog.load(DATA_ROOT / "native-croupier-catalog.json")
    if document.get("version") != 1:
        raise ValueError("Unsupported native exchange-machine catalog")
    return document


def decode(body):
    """coJ/13057: catalog, world object, offer, quantity, inventory actor."""
    if len(body) != 26:
        raise ValueError("Invalid exchange-machine request length")
    values = struct.unpack(">iqihq", body)
    if any(value <= 0 for value in values):
        raise ValueError("Invalid exchange-machine request identity or quantity")
    return dict(
        zip(("catalog_id", "object_id", "offer_id", "quantity", "actor_id"), values)
    )


def station(character, request, *, document=None):
    """Resolve the installed machine with the shared local interaction policy.

    Four Manhattan cells and one height unit are server policy, not a claim
    about the native client's interaction radius.
    """
    document = catalog() if document is None else document
    rows = [
        row
        for row in document["placements"]
        if row["map_id"] == character["map_id"] and row["id"] == request["object_id"]
    ]
    if (
        len(rows) != 1
        or type(character.get("instance_id")) is not int
        or character["instance_id"] < 0
    ):
        raise ValueError("Unknown exchange machine in current map instance")
    row = rows[0]
    if (
        row["machine_id"] != request["catalog_id"]
        or abs(character["z"] - row["z"]) > 1
        or abs(character["x"] - row["x"]) + abs(character["y"] - row["y"]) > 4
    ):
        raise ValueError("Exchange machine is foreign or out of reach")
    return dict(
        object_id=row["id"],
        catalog_id=row["machine_id"],
        map_id=row["map_id"],
        instance_id=character["instance_id"],
        in_range=True,
    )


def _offer(document, request):
    machines = [
        row for row in document["machines"] if row["id"] == request["catalog_id"]
    ]
    if len(machines) != 1:
        raise ValueError("Unknown native exchange machine")
    offers = [row for row in machines[0]["offers"] if row["id"] == request["offer_id"]]
    if len(offers) != 1:
        raise ValueError("Offer does not belong to the native exchange machine")
    return offers[0]


def _costs(db, character, rows, count):
    from . import quest_inventory
    from wakfu_server.craft_planner import _equipped_uids
    from wakfu_server.recycling import _offered_uids

    required = defaultdict(int)
    for row in rows:
        reference, quantity = row["reference"], row["quantity"]
        if (
            type(reference) is not int
            or reference <= 0
            or type(quantity) is not int
            or quantity <= 0
        ):
            raise ValueError("Invalid native exchange cost")
        required[reference] += quantity * count
    protected = _equipped_uids(character["builds"]) | _offered_uids(db, character["id"])
    bags = {
        row["uid"]
        for row in character["inventory_containers"]
        if row["kind"] in (0, 1, 2, 3)
    }
    for reference, quantity in required.items():
        if reference in quest_inventory._SOURCE["account_quest_property_references"]:
            raise ValueError(
                "Spendable native account-quest inventory is not implemented"
            )
        if reference in quest_inventory.REFERENCES:
            current = db.execute(
                "SELECT quantity FROM character_quest_items WHERE character_id=%s AND reference=%s FOR UPDATE",
                (character["id"], reference),
            ).fetchone()
            if current is None or current["quantity"] < quantity:
                raise ValueError("Insufficient native quest-item exchange cost")
            if current["quantity"] == quantity:
                db.execute(
                    "DELETE FROM character_quest_items WHERE character_id=%s AND reference=%s",
                    (character["id"], reference),
                )
            else:
                db.execute(
                    "UPDATE character_quest_items SET quantity=quantity-%s WHERE character_id=%s AND reference=%s",
                    (quantity, character["id"], reference),
                )
            continue
        items = [
            row
            for row in character["inventory_items"]
            if row["reference"] == reference
            and row["container"] in bags
            and row["uid"] not in protected
        ]
        if sum(row["quantity"] for row in items) < quantity:
            raise ValueError("Insufficient native inventory exchange cost")
        for item in sorted(items, key=lambda row: row["uid"]):
            used = min(quantity, item["quantity"])
            if used == item["quantity"]:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], character["id"]),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s AND character_id=%s",
                    (used, item["uid"], character["id"]),
                )
            quantity -= used
            if not quantity:
                break


def purchase(
    store,
    account_id,
    generation,
    main_id,
    body,
    *,
    location,
    blocked=False,
    document=None,
    station=None
):
    """Spend native costs and grant rewards; identical requests are distinct buys.

    ``station`` is a trusted world-adapter result, never client request data.
    It must identify the registered machine and certify native reachability.
    """
    from wakfu_server.inventory_items import _lease
    from wakfu_server.inventory_owner import lock_inventory_character
    from . import quest_inventory
    from wakfu_server.achievements import rewards
    from .exchange_machine_criteria import evaluate

    request = decode(body)
    if blocked:
        raise ValueError("Exchange machine is unavailable during the current activity")
    document = catalog() if document is None else document
    offer = _offer(document, request)
    if (
        not isinstance(station, dict)
        or station.get("in_range") is not True
        or station.get("object_id") != request["object_id"]
        or station.get("catalog_id") != request["catalog_id"]
        or station.get("map_id") != location.get("map_id")
        or station.get("instance_id") != location.get("instance_id")
    ):
        raise ValueError("Missing authorized native exchange-machine station")
    if offer["alternate_currency_cost"] or offer["offer_flag"]:
        raise ValueError(
            "Native exchange currency or offer requirement is not implemented"
        )
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        _lease(store, db, account_id, generation, main_id)
        lock_inventory_character(store, db, account_id, generation, request["actor_id"])
        main = store.character(account_id, main_id, db)
        if (
            location.get("id") != main_id
            or location.get("account_id") != account_id
            or any(
                location.get(key) != main.get(key)
                for key in ("map_id", "instance_id", "x", "y", "z")
            )
        ):
            raise ValueError("Exchange-machine location changed")
        owner = request["actor_id"]
        character = store.character(account_id, owner, db)
        if db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
            (owner,),
        ).fetchone():
            raise ValueError("Exchange machine is unavailable during combat")
        if not evaluate(db, store, character, offer["criteria"]):
            raise ValueError("Native exchange offer criterion is not satisfied")
        price = offer["kamas_cost"] * request["quantity"]
        if type(price) is not int or not 0 <= price < 2**63:
            raise ValueError("Invalid native exchange currency cost")
        wallet = db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if wallet is None or wallet["kamas"] < price:
            raise ValueError("Insufficient kamas for native exchange")
        _costs(db, character, offer["costs"], request["quantity"])
        if price:
            db.execute(
                "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s",
                (price, account_id),
            )
        for reward in offer["rewards"]:
            if reward["raw_cnH"]:
                raise ValueError(
                    "Native exchange reward four-white-slot transformation is not implemented"
                )
            # Explicit local policy: ignore offer-level binding overrides and
            # retain the reward item's ordinary native template binding.
            quantity = reward["quantity"] * request["quantity"]
            rewards.validate({"aeV": 5, "ckl": [reward["reference"], quantity]})
            rewards._item(db, store, character, reward["reference"], quantity)
        after = store.character(account_id, owner, db)
        packets = quest_inventory.changes(character, after)
        if price:
            from wakfu_server.wire import account_kamas_update

            packets.append((12753, account_kamas_update(wallet["kamas"] - price)))
        return dict(character=after, packets=packets, request=request)
