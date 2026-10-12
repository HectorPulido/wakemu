"""Native Ranch bridge activators with durable owner-scoped state and item cost."""
import struct

POLICY = "haven_ranch_bridge_policy"


def _policy(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (POLICY,)).fetchone()
    policy = None if row is None else row["value"]
    if (
        not isinstance(policy, dict)
        or policy.get("schema_version") != 1
        or policy.get("map_id") != 1440
        or policy.get("biome_id") != 1
    ):
        raise ValueError("Missing accredited native Ranch bridge policy")
    slots, activators = policy.get("slots"), policy.get("activators")
    if (
        not isinstance(slots, list)
        or not slots
        or any(
            not isinstance(slot, dict)
            or type(slot.get("id")) is not int
            or slot["id"] <= 0
            for slot in slots
        )
    ):
        raise ValueError("Malformed native Ranch bridge slots")
    ids = {slot["id"] for slot in slots}
    if len(ids) != len(slots) or not isinstance(activators, list) or not activators:
        raise ValueError("Malformed native Ranch bridge activators")
    objects = set()
    for action in activators:
        if (
            not isinstance(action, dict)
            or type(action.get("object_id")) is not int
            or action["object_id"] <= 0
            or action["object_id"] in objects
            or action.get("slot_id") not in ids
            or action.get("selector") != 0
            or type(action.get("item_ref")) is not int
            or action["item_ref"] <= 0
            or action.get("quantity") != 1
            or action.get("consumed") is not True
            or any(type(action.get(k)) is not int for k in ("x", "y", "z"))
        ):
            raise ValueError("Malformed native Ranch bridge activator")
        objects.add(action["object_id"])
    return policy


def snapshot(db, owner_character_id):
    """All installed slots: absence is ABSENT, never an automatic bridge grant."""
    policy = _policy(db)
    states = {slot["id"]: 0 for slot in policy["slots"]}
    for row in db.execute(
        "SELECT slot_id,present FROM haven_ranch_bridges WHERE owner_character_id=%s",
        (owner_character_id,),
    ):
        if row["slot_id"] not in states or type(row["present"]) is not bool:
            raise ValueError("Unknown durable Ranch bridge state")
        states[row["slot_id"]] = int(row["present"])
    return [dict(slot_id=slot, state=states[slot]) for slot in sorted(states)]


def state_packet(scene_map_id, slot_id, present):
    if (
        type(scene_map_id) is not int
        or scene_map_id <= 0
        or type(slot_id) is not int
        or slot_id <= 0
        or type(present) is not bool
    ):
        raise ValueError("Invalid native Ranch bridge publication")
    return 13080, struct.pack(">qiB", scene_map_id, slot_id, int(present))


def activate(store, account_id, generation, character, body, *, session):
    """Execute only the two original deterministic BUILD_RANCH_BRIDGE actions."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Ranch bridge activation requires exactly 12 bytes")
    identity, selector, parameter = struct.unpack(">qHH", body)
    if selector != 0 or parameter != 0:
        raise ValueError("Unsupported native Ranch bridge activation")
    if character.get("map_id") != 1440 or session is None or session.biome_id != 1:
        raise ValueError(
            "Bridge activation requires the installed original Ranch biome"
        )
    from wakfu_server.haven_ranch_furniture import _authorize
    from wakfu_server import world_static
    from wakfu_server.haven_bag_furniture_transfer import _plain_item
    from wakfu_server.wire import proto_fields

    with store.connection() as db:
        bag_id = _authorize(store, db, account_id, generation, character, session)
        policy = _policy(db)
        actions = [a for a in policy["activators"] if a["object_id"] == identity]
        if len(actions) != 1:
            raise ValueError("Unknown original Ranch bridge activator")
        action = actions[0]
        originals = [obj for obj in world_static.objects(1440) if obj["id"] == identity]
        if (
            len(originals) != 1
            or originals[0]["type"] != "GenericActivableInteractiveElement"
            or any(originals[0].get(k) != action[k] for k in ("x", "y", "z"))
        ):
            raise ValueError(
                "Ranch bridge activator differs from installed native identity"
            )
        # Preserve the server's general environment interaction range policy.
        if (
            abs(character["z"] - action["z"]) > 1
            or abs(character["x"] - action["x"]) + abs(character["y"] - action["y"]) > 4
        ):
            raise ValueError("Ranch bridge activator is out of reach")
        previous = db.execute(
            "SELECT present FROM haven_ranch_bridges WHERE owner_character_id=%s AND slot_id=%s FOR UPDATE",
            (bag_id, action["slot_id"]),
        ).fetchone()
        applied = previous is None or not previous["present"]
        private = []
        if applied:
            item = db.execute(
                "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s AND quantity>=1 ORDER BY uid LIMIT 1 FOR UPDATE",
                (character["id"], action["item_ref"]),
            ).fetchone()
            if item is None:
                raise ValueError("Missing native bridge construction item")
            saved = store.character(account_id, character["id"], db)
            for build in saved.get("builds", {}).values():
                for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                    if tag == 10 and dict(proto_fields(value)).get(8) == item["uid"]:
                        raise ValueError(
                            "Unequip the bridge construction item before activation"
                        )
            _plain_item(db, item["uid"])
            if item["quantity"] == 1:
                db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                    (item["uid"],),
                )
            db.execute(
                "INSERT INTO haven_ranch_bridges(owner_character_id,slot_id,present,consumed_uid,consumed_ref,actor_id) "
                "VALUES(%s,%s,true,%s,%s,%s) ON CONFLICT(owner_character_id,slot_id) DO UPDATE "
                "SET present=true,consumed_uid=EXCLUDED.consumed_uid,consumed_ref=EXCLUDED.consumed_ref,actor_id=EXCLUDED.actor_id",
                (
                    bag_id,
                    action["slot_id"],
                    item["uid"],
                    action["item_ref"],
                    character["id"],
                ),
            )
            private = [(12470, struct.pack(">qh", item["uid"], -1))]
        return dict(
            character=store.character(account_id, character["id"], db),
            applied=applied,
            private_packets=private,
            scene_packets=[state_packet(character["map_id"], action["slot_id"], True)],
            states=snapshot(db, bag_id),
        )


def blocked_cells(db, owner_character_id):
    """Original ABSENT-building collision cells; construction clears only its slot."""
    policy = _policy(db)
    states = {row["slot_id"]: row["state"] for row in snapshot(db, owner_character_id)}
    result = set()
    for slot in policy["slots"]:
        footprint = slot.get("footprint")
        if (
            not isinstance(footprint, list)
            or not footprint
            or any(
                not isinstance(cell, list)
                or len(cell) != 2
                or any(type(axis) is not int for axis in cell)
                for cell in footprint
            )
        ):
            raise ValueError("Malformed native Ranch bridge collision cells")
        if states[slot["id"]] == 0:
            result.update(tuple(cell) for cell in footprint)
    return result
