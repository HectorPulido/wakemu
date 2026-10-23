"""Authorize bounded original visual item scripts; never evaluate submitted Lua.

The native client already owns these exact ie_actions assets. Server-generated
13270 variables carry only the actor identity and an authorized scene cell.
Scenario callbacks and arbitrary script paths are deliberately outside this API.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _criterion, _equipped, _idle

SOURCE_SHA256 = "2de60d983c3837c6add52fe3fe61d431b199e24f35a800a1b5f9b60488b7444f"
LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")


@lru_cache(maxsize=1)
def descriptors():
    payload = Path(__file__).with_name("native_item_scripts.json").read_bytes()
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native script descriptors")
    return json.loads(payload)


def _request(body):
    if not isinstance(body, bytes) or len(body) not in (13, 23):
        raise ValueError("Invalid native script action grammar")
    action_id, uid, present = struct.unpack_from(">iqB", body)
    if action_id <= 0 or uid <= 0 or present not in (0, 1):
        raise ValueError("Invalid native script action identity")
    if len(body) != (23 if present else 13):
        raise ValueError("Invalid native script position suffix")
    return action_id, uid, struct.unpack_from(">iih", body, 13) if present else None


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native item action header")
    action_id = struct.unpack_from(">i", body)[0]
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        return None
    _request(body)
    return "bIa"


def script_packet(actor_id, action_id, position):
    """Encode cwh13270/ffK.DEFAULT using the original fixed variable names."""
    if type(actor_id) is not int or not 0 < actor_id < 2**63:
        raise ValueError("Invalid native script actor")
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        raise ValueError("Unqualified native visual script")
    if (
        not isinstance(position, (tuple, list))
        or len(position) != 3
        or any(type(value) is not int for value in position)
        or any(not -(2**31) <= value < 2**31 for value in position[:2])
        or not -(2**15) <= position[2] < 2**15
    ):
        raise ValueError("Invalid native script position")
    variables = dict(
        user=actor_id,
        castCellX=position[0],
        castCellY=position[1],
        castCellZ=position[2],
    )
    result = bytearray(struct.pack(">qiBi", actor_id, action_id, 0, len(variables)))
    for key, value in variables.items():
        encoded = key.encode("utf-8")
        result.extend(struct.pack(">i", len(encoded)))
        result.extend(encoded)
        result.extend(struct.pack(">q", value))
    return 13270, bytes(result)


def _position(character, requested, native_map_id, geometry):
    """Use current scene coordinates, never client-submitted actor variables."""
    position = tuple(character[key] for key in ("x", "y", "z"))
    if requested is None or requested == position:
        return position
    from wakfu_server.combat_terrain import map_geometry

    map_id = character["map_id"] if native_map_id is None else native_map_id
    native = (geometry or map_geometry)(map_id)
    if native.get("map_id") != map_id or requested not in {
        tuple(cell) for cell in native.get("cells", ())
    }:
        raise ValueError("The visual script target is not a valid cell in this scene")
    return requested


def use(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    location=None,
    native_map_id=None,
    target_present=False,
    geometry=None
):
    """Commit native source consumption and return an independently scoped visual.

    World supplies the source owner's authoritative buffered location when it
    differs from durable coordinates. For the two mobile-target scripts World
    must also prove a visible mobile exists at the target in this same scene.
    Inventory packets belong to the owner; script_packet is broadcast once to
    scene viewers including that owner after this transaction has committed.
    """
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Use this visual item outside combat")
    action_id, source_uid, requested = _request(body)
    plan = next(
        (row for row in descriptors()["items"] if row["action_id"] == action_id), None
    )
    if plan is None:
        raise ValueError("Unsupported native script action")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (source_uid,)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, owner_id),
        ).fetchone()
        if (
            item is None
            or item["quantity"] < 1
            or item["reference"] != plan["item_ref"]
        ):
            raise ValueError(
                "The script source is unavailable or does not match this action"
            )
        rule = db.execute(
            "SELECT * FROM native_script_item_actions WHERE item_ref=%s",
            (item["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["source_sha256"] != SOURCE_SHA256
            or rule["consumes_source"] != plan["consumes_source"]
        ):
            raise ValueError("The native script authority has changed")
        from .haven_bag_furniture_knowledge import _rules

        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_class") != "bIa"
            or published.get("use_action_id") != action_id
        ):
            raise ValueError("The script differs from the active native catalog")
        character = store.character(account_id, owner_id, db)
        if _equipped(character, source_uid):
            raise ValueError("Unequip the visual item before using it")
        if location is not None:
            if location.get("id") != owner_id or any(
                type(location.get(key)) is not int for key in LOCATION_KEYS
            ):
                raise ValueError("The visual script actor location is invalid")
            character = dict(character, **{key: location[key] for key in LOCATION_KEYS})
        from wakfu_server.swimming import at_position

        visible = dict(
            character,
            map_id=character["map_id"] if native_map_id is None else native_map_id,
        )
        if at_position(visible):
            raise ValueError("This visual item cannot be used while swimming")
        if not _criterion(
            store, db, account_id, character, plan["criterion"], native_map_id
        ):
            raise ValueError("The native script conditions are not satisfied")
        position = _position(character, requested, native_map_id, geometry)
        if plan["requires_mobile_target"] and target_present is not True:
            raise ValueError("Select a visible mobile for this visual item")
        visual = script_packet(owner_id, action_id, position)
        consumed = int(plan["consumes_source"])
        packets = []
        if consumed:
            if item["quantity"] == 1:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (source_uid, owner_id),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                    (source_uid, owner_id),
                )
            packets.append((12470, struct.pack(">qh", source_uid, -1)))
        return dict(
            character=store.character(account_id, owner_id, db),
            packets=packets,
            applied=True,
            validated=True,
            native_class="bIa",
            consumed=consumed,
            source_uid=source_uid,
            source_reference=item["reference"],
            script_id=action_id,
            position=position,
            script_packet=visual,
            location={key: character[key] for key in LOCATION_KEYS},
        )
