"""Authenticated native resource facts for the private Incarnam tutorial."""
from . import rewards, storage, incarnam_tutorial

MAP_ID = 1361
TREE_REFERENCE = 824
TREE_ACTION = 2266
SEED_REFERENCE = 30938
BROKEN_KEY_REFERENCE = 30941
WOOD_REFERENCE = 30939
WORKBENCH = 34582
KEY_RECIPE = 9323
KEY_REFERENCE = 30940
GATE = 34612


def owned_scene(character):
    from wakfu_server.intro_cinematic import private_instance_id

    try:
        return character.get("map_id") == MAP_ID and character.get(
            "instance_id"
        ) == private_instance_id(character["id"])
    except (KeyError, TypeError, ValueError):
        return False


def active(db, character, quest):
    return (
        owned_scene(character)
        and quest in storage.load_locked(db, character["id"])["running"]
    )


def give_seed(db, store, character):
    """Observed ten saplings are granted once when the wood quest begins."""
    if not active(db, character, 5136):
        return []
    if not storage.record_event(
        db,
        character["id"],
        "incarnam-seeds:5136",
        {"kind": "incarnam_seed_grant", "reference": SEED_REFERENCE, "quantity": 10},
    ):
        return []
    packets = rewards._item(db, store, character, SEED_REFERENCE, 10)
    packets.extend(rewards._item(db, store, character, BROKEN_KEY_REFERENCE, 1))
    return packets


def harvested(db, store, character, resource, rule, *, token, product_reference):
    if (
        not active(db, character, 5136)
        or resource.get("resource_reference") != TREE_REFERENCE
        or resource.get("map_id") != MAP_ID
        or resource.get("instance_id") != character["instance_id"]
        or rule.get("action_id") != TREE_ACTION
        or product_reference != WOOD_REFERENCE
    ):
        return []
    return incarnam_tutorial.settle(
        db, store, character, event="wood_harvest", token=str(token)
    )


def crafted(db, store, character, occupation, products, *, token):
    if (
        not active(db, character, 5137)
        or occupation.get("table_uid") != WORKBENCH
        or occupation.get("recipe_id") != KEY_RECIPE
        or occupation.get("map_id") != MAP_ID
        or occupation.get("instance_id") != character["instance_id"]
        or not any(
            row.get("reference", row.get("item_id")) == KEY_REFERENCE
            for row in products
        )
    ):
        return []
    return incarnam_tutorial.settle(
        db, store, character, event="key_crafted", token=str(token)
    )


def is_gate_request(character, body):
    import struct

    return (
        owned_scene(character)
        and isinstance(body, bytes)
        and len(body) == 12
        and struct.unpack(">qHH", body) == (GATE, 0, 0)
    )


def gate_state_packets(character, state):
    """Replay private portal state after the client's objects are hydrated."""
    if not owned_scene(character) or 5138 not in state["completed"]:
        return []
    return [
        (12344, bytes.fromhex(data))
        for data in (
            "0000000000008732001301020000000602000001010000000000000000",
            "0000000000008733001301020000000602000001010000000000000000",
            "0000000000008734001301020000000602000100010000010000000000",
        )
    ]


def first_barrier_packets(character, state):
    """Restore the five native collision tiles removed after the first fight."""
    import struct

    if not owned_scene(character) or 5135 not in state["completed"]:
        return []
    payload = bytes.fromhex("01020000000602000001010000000000000000")
    return [
        (12344, struct.pack(">qH", identity, len(payload)) + payload)
        for identity in range(34577, 34582)
    ]


def interact_gate(store, account_id, generation, location, body, *, loaded, blocked):
    """Consume the crafted key and open this owner's native tutorial gate."""
    from wakfu_server.inventory_items import _lease
    from wakfu_server.environment_interactions import _guard
    from wakfu_server.native_generic_rewards import _payment

    if not loaded or blocked or not is_gate_request(location, body):
        raise ValueError("Incarnam gate interaction unavailable")
    with store.connection() as db:
        _lease(store, db, account_id, generation, location["id"])
        _guard(db, location["id"])
        character = store.character(account_id, location["id"], db)
        if (
            not owned_scene(character)
            or not active(db, character, 5138)
            or abs(character["z"] + 13) > 1
            or abs(character["x"] - 12) + abs(character["y"] + 35) > 4
        ):
            raise ValueError("Incarnam gate unavailable or outside interaction range")
        character, payment, consumed = _payment(
            db, store, character, {"group_cod": KEY_REFERENCE, "group_coe": 1}
        )
        if not consumed:
            raise ValueError("Incarnam gate key was not consumed")
        packets = list(payment)
        # Native 12344 state observed for each portal tile and the gate itself.
        for data in (
            "0000000000008732001301020000000602000001010000000000000000",
            "0000000000008733001301020000000602000001010000000000000000",
            "0000000000008734001301020000000602000101010000010000000000",
            "0000000000008734001301020000000602000100010000010000000000",
        ):
            packets.append((12344, bytes.fromhex(data)))
        packets.extend(
            incarnam_tutorial.settle(
                db, store, character, event="portal_opened", token="gate-34612"
            )
        )
        return {
            "character": store.character(account_id, location["id"], db),
            "packets": packets,
        }
