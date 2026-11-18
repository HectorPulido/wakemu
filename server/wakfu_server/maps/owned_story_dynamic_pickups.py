"""Reviewed owned item scenes using native Decoration models and REPACK23.

The scene placement and item award join are explicit reconstruction. Real native
furniture templates, allocated instance identities, owner membership and prior
victory receipts remain authoritative; no original static IE or loot is invented.
"""
import struct

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server.achievements import storage, rewards


def policy(selected):
    native = mechanics.sources(selected)
    rows = native.get("reviewed_dynamic_pickups", [])
    if not isinstance(rows, list):
        raise ValueError("Owned pickups require explicit reviewed declarations")
    fields = {
        "id",
        "item_reference",
        "quantity",
        "quest_id",
        "objective_id",
        "step_id",
        "position",
        "approaches",
        "direction",
        "evidence",
    }
    steps = {step["id"]: step for step in selected["steps"]}
    seen = set()
    from wakfu_server.haven_bag_furniture_catalog import resolve_item
    from wakfu_server.combat_geometry import published_geometry

    cells = published_geometry(selected["map_id"]).cells if rows else ()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != fields
            or not isinstance(row["id"], str)
            or not row["id"]
            or ":" in row["id"]
            or row["id"] in seen
            or not isinstance(row["evidence"], str)
            or not row["evidence"].strip()
            or any(
                type(row[k]) is not int or row[k] <= 0
                for k in ("item_reference", "quantity", "quest_id", "objective_id")
            )
            or row["quantity"] != 1
            or type(row["direction"]) is not int
            or not 0 <= row["direction"] <= 7
            or not isinstance(row["position"], list)
            or len(row["position"]) != 3
            or any(type(v) is not int for v in row["position"])
            or tuple(row["position"]) not in cells
            or not isinstance(row["approaches"], list)
            or not row["approaches"]
        ):
            raise ValueError("Invalid owned dynamic pickup declaration")
        seen.add(row["id"])
        for point in row["approaches"]:
            if (
                not isinstance(point, list)
                or len(point) != 3
                or any(type(v) is not int for v in point)
                or tuple(point) not in cells
                or abs(point[0] - row["position"][0])
                + abs(point[1] - row["position"][1])
                != 1
                or abs(point[2] - row["position"][2]) > 1
            ):
                raise ValueError("Owned pickup approach leaves its native floor")
        item = resolve_item(row["item_reference"])
        step = steps.get(row["step_id"])
        if (
            item is None
            or item["kind"] != "Decoration"
            or step is None
            or step["kind"] != "dynamic_pickup"
            or step["reference"] != row["item_reference"]
            or not any(steps[k]["kind"] == "room_victory" for k in step["requires"])
            or dict(
                kind="quest_objective",
                quest_id=row["quest_id"],
                objective_id=row["objective_id"],
            )
            not in step["effects"]
        ):
            raise ValueError(
                "Owned pickup lacks its native item and prior victory producer"
            )
    return tuple(rows)


def _key(character, row):
    return f"owned-dynamic-pickup:{character['instance_id']}:{row['id']}"


def _publication(db, character, selected, row, *, create):
    key = _key(character, row)
    saved = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character["id"], key),
    ).fetchone()
    source = dict(
        owner_id=character["id"],
        instance_id=character["instance_id"],
        map_id=selected["map_id"],
        controller_sha256=controller._digest(selected),
        source_sha256=controller._digest(row),
    )
    if saved is not None:
        value = saved["payload"]
        if (
            any(value.get(k) != v for k, v in source.items())
            or type(value.get("uid")) is not int
            or value["uid"] <= 0
        ):
            raise ValueError("Owned dynamic pickup publication changed")
        return value
    if not create:
        return None
    from wakfu_server import npc_actor_identity

    value = dict(source, uid=npc_actor_identity.allocate_block(db, 1))
    if not storage.record_event(db, character["id"], key, value):
        raise ValueError("Owned dynamic pickup publication raced")
    return value


def _available(db, character, row, selected, completed):
    step = next(step for step in selected["steps"] if step["id"] == row["step_id"])
    progress = storage.load_locked(db, character["id"])
    return (
        row["step_id"] not in completed
        and set(step["requires"]) <= completed
        and row["quest_id"] in progress["running"]
        and row["objective_id"] not in progress["objectives"]
    )


def packets(db, store, character):
    selected, completed = controller._scope(db, store, character)
    rows = policy(selected)
    if not rows:
        return []
    from wakfu_server.haven_bag_furniture_catalog import resolve_item
    from wakfu_server.haven_bag_furniture_world import _record

    result = []
    for row in rows:
        if not _available(db, character, row, selected, completed):
            continue
        publication = _publication(db, character, selected, row, create=True)
        item = dict(
            item_ref=row["item_reference"],
            template_id=resolve_item(row["item_reference"])["template_id"],
            item_uid=publication["uid"],
            direction=row["direction"],
            virtual=False,
            **dict(zip(("x", "y", "z"), row["position"])),
        )
        result.append(
            (13664, struct.pack(">h", 1) + _record(character["id"], item, ranch=True))
        )
    return result


def interact(db, store, character, body):
    """Caller owns the normal leased-owner, idle and position fences."""
    if not isinstance(body, bytes) or len(body) != 12:
        return None
    uid, action, parameter = struct.unpack(">qHH", body)
    selected, completed = controller._scope(db, store, character)
    rows = policy(selected)
    for row in rows:
        publication = _publication(db, character, selected, row, create=False)
        if publication is None or publication["uid"] != uid:
            continue
        if action != 23 or parameter:
            raise ValueError("Owned pickup requires its native REPACK action")
        if not _available(db, character, row, selected, completed):
            return dict(applied=False, packets=[], step=None)
        if [character[k] for k in ("x", "y", "z")] not in row["approaches"]:
            raise ValueError("Owned pickup requires its actual adjacent approach")
        # Inventory, quest effects and the durable controller receipt share this
        # transaction; capacity failure leaves the real scene source available.
        granted = rewards.grant(
            db,
            store,
            character,
            dict(aeV=5, ckl=[row["item_reference"], row["quantity"]]),
        )
        current = store.character(character["account_id"], character["id"], db)
        outcome = controller._settle(
            db,
            store,
            current,
            selected,
            completed,
            kind="dynamic_pickup",
            reference=row["item_reference"],
            evidence=dict(
                dynamic_uid=uid,
                source_sha256=controller._digest(row),
                item_reference=row["item_reference"],
                quantity=row["quantity"],
                position=row["position"],
                request_action=23,
            ),
            apply_effects=mechanics.executor(selected),
        )
        if not outcome["applied"]:
            raise ValueError("Owned pickup lost its genuine controller producer")
        outcome["packets"] = [
            *granted,
            *outcome["packets"],
            (13082, struct.pack(">hq", 1, uid)),
        ]
        return outcome
    return None
