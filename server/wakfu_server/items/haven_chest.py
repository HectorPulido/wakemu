"""Account chest planning and atomic durable custody of complete owned items.

Inventory metadata is snapshotted before deleting its FK-owned rows, then
restored verbatim on withdrawal. Only explicit supported metadata tables are
used. This module does not start services or send packets.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib
import uuid

from psycopg.types.json import Jsonb

from .haven_chest_wire import decode_deposit, decode_withdraw, decode_relocate
from .haven_chest_layout import TAB_CAPACITY, provisioned_capacity, resolve

_METADATA = (
    "inventory_item_elements",
    "inventory_item_shards",
    "inventory_mounts",
    "inventory_item_bindings",
    "inventory_item_recycling_state",
)
_RETRY_WINDOW = timedelta(seconds=3)
_NAMESPACE = uuid.UUID("a888142e-f9d3-4d38-91b8-64ccac719c6b")


def _json(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$bytes": bytes(value).hex()}
    if isinstance(value, dict):
        return {key: _json(entry) for key, entry in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(entry) for entry in value]
    return value


def _unjson(value):
    if isinstance(value, dict):
        if set(value) == {"$bytes"}:
            return bytes.fromhex(value["$bytes"])
        return {key: _unjson(entry) for key, entry in value.items()}
    if isinstance(value, list):
        return [_unjson(entry) for entry in value]
    return value


def _identity(entry):
    """Physical placement and identities do not define stack compatibility."""
    item = {
        key: value
        for key, value in entry["item"].items()
        if key not in {"uid", "quantity", "container", "slot", "character_id"}
    }
    metadata = {
        table: {key: value for key, value in row.items() if key != "uid"}
        for table, row in entry.get("metadata", {}).items()
    }
    return item, metadata


def _clone(entry, uid):
    entry = deepcopy(entry)
    entry["item"]["uid"] = uid
    for row in entry.get("metadata", {}).values():
        row["uid"] = uid
    if "mount" in entry["item"]:
        entry["item"]["mount"]["uid"] = uid
    return entry


def _move(source, destination, quantity, maximum, allocate):
    if type(quantity) is not int or not 1 <= quantity <= source["item"]["quantity"]:
        raise ValueError("Chest quantity exceeds owned source")
    if type(maximum) is not int or not 1 <= maximum <= 32767:
        raise ValueError("Unsupported native chest stack rule")
    if source["item"]["quantity"] > maximum:
        raise ValueError("Oversized owned chest source stack")
    if destination is not None:
        if _identity(source) != _identity(destination):
            raise ValueError("Chest destination contains an incompatible item")
        if destination["item"]["quantity"] + quantity > maximum:
            raise ValueError("Chest destination stack is full")
        destination["item"]["quantity"] += quantity
        moved = destination
    else:
        moved = _clone(
            source,
            source["item"]["uid"]
            if quantity == source["item"]["quantity"]
            else allocate(),
        )
        moved["item"]["quantity"] = quantity
    source["item"]["quantity"] -= quantity
    return moved


def plan(
    inventory, chest, requests, *, deposit, character_id, containers, rules, allocate
):
    """Plan an entire native batch on copies. Failure never mutates inputs.

    Explicit occupied destinations merge compatible stacks. Automatic (-1)
    destinations prefer compatible stacks, then free cells, as the native UI.
    """
    inventory, chest = deepcopy(inventory), deepcopy(chest)
    if any(entry["item"].get("character_id") != character_id for entry in inventory):
        raise ValueError("Foreign chest inventory snapshot")
    inventory_ids = [entry["item"]["uid"] for entry in inventory]
    chest_ids = [entry["item"]["uid"] for entry in chest["items"]]
    chest_slots = [entry["slot"] for entry in chest["items"]]
    if (
        len(set(inventory_ids + chest_ids)) != len(inventory_ids + chest_ids)
        or len(set(chest_slots)) != len(chest_slots)
        or any(
            type(slot) is not int or not 0 <= slot < chest["capacity"]
            for slot in chest_slots
        )
    ):
        raise ValueError("Duplicate or invalid owned chest position/identity")
    for request in requests:
        compartment = resolve(chest, request["compartment"])
        offset = compartment["offset"]
        chest_slot = request["slot"]
        if chest_slot != -1 and not 0 <= chest_slot < compartment["capacity"]:
            raise ValueError("Invalid chest compartment position")
        if deposit:
            source = next(
                (
                    entry
                    for entry in inventory
                    if entry["item"]["uid"] == request["uid"]
                ),
                None,
            )
            if source is None:
                raise ValueError("Chest deposit item unavailable or foreign")
            source_container = next(
                (
                    row
                    for row in containers
                    if row["uid"] == source["item"]["container"]
                    and row["character_id"] == character_id
                    and row["kind"] in (0, 1, 2, 3)
                ),
                None,
            )
            if source_container is None:
                raise ValueError("Unsupported chest source container")
            destinations = [
                entry
                for entry in chest["items"]
                if offset <= entry["slot"] < offset + compartment["capacity"]
            ]
            slot = -1 if chest_slot == -1 else offset + chest_slot
            start, capacity = offset, offset + compartment["capacity"]
            position = lambda entry: entry["slot"]
        else:
            source = next(
                (
                    entry
                    for entry in chest["items"]
                    if entry["slot"] == offset + chest_slot
                ),
                None,
            )
            if source is None or source["item"]["reference"] != request["reference"]:
                raise ValueError("Chest withdrawal source changed or unavailable")
            container = next(
                (
                    row
                    for row in containers
                    if row["uid"] == request["container"]
                    and row["character_id"] == character_id
                    and row["kind"] in (0, 1, 2, 3)
                ),
                None,
            )
            if container is None:
                raise ValueError("Foreign chest withdrawal container")
            destinations = [
                entry
                for entry in inventory
                if entry["item"]["container"] == container["uid"]
            ]
            slot, capacity = request["destination"], container["capacity"]
            start = 0
            position = lambda entry: entry["item"]["slot"]
        rule = rules.get(source["item"]["reference"], {})
        maximum = rule.get("native_maximum", rule.get("maximum"))
        if maximum is None:
            raise ValueError("Missing native stack rule for chest item")
        if slot == -1:
            compatible = next(
                (
                    entry
                    for entry in destinations
                    if _identity(entry) == _identity(source)
                    and entry["item"]["quantity"] + request["quantity"] <= maximum
                ),
                None,
            )
            used = {position(entry) for entry in destinations}
            slot = (
                position(compatible)
                if compatible
                else next((n for n in range(start, capacity) if n not in used), -1)
            )
        if type(slot) is not int or not start <= slot < capacity:
            raise ValueError("Chest destination inventory is full or invalid")
        destination = next(
            (entry for entry in destinations if position(entry) == slot), None
        )
        moved = _move(source, destination, request["quantity"], maximum, allocate)
        if destination is None:
            if deposit:
                moved["slot"] = slot
                for key in ("character_id", "container", "slot"):
                    moved["item"].pop(key, None)
                chest["items"].append(moved)
            else:
                moved.pop("slot", None)
                moved["item"].update(
                    character_id=character_id, container=container["uid"], slot=slot
                )
                inventory.append(moved)
        if source["item"]["quantity"] == 0:
            (inventory if deposit else chest["items"]).remove(source)
    return inventory, chest


def plan_relocate(chest, requests, *, rules, allocate):
    """Move complete owned metadata between tabs on a detached atomic plan."""
    chest = deepcopy(chest)
    items = chest["items"]
    if (
        len({entry["slot"] for entry in items}) != len(items)
        or len({entry["item"]["uid"] for entry in items}) != len(items)
        or any(
            type(entry["slot"]) is not int or not 0 <= entry["slot"] < chest["capacity"]
            for entry in items
        )
    ):
        raise ValueError("Duplicate owned chest position/identity")
    for request in requests:
        source_tab = resolve(chest, request["compartment"])
        destination_tab = resolve(chest, request["destination_compartment"])
        if (
            not 0 <= request["slot"] < source_tab["capacity"]
            or not 0 <= request["destination"] < destination_tab["capacity"]
        ):
            raise ValueError("Invalid chest relocation position")
        source_slot = source_tab["offset"] + request["slot"]
        destination_slot = destination_tab["offset"] + request["destination"]
        source = next((entry for entry in items if entry["slot"] == source_slot), None)
        if source is None:
            raise ValueError("Chest relocation source unavailable")
        if source_slot == destination_slot:
            if not 1 <= request["quantity"] <= source["item"]["quantity"]:
                raise ValueError("Chest quantity exceeds owned source")
            continue
        destination = next(
            (entry for entry in items if entry["slot"] == destination_slot), None
        )
        rule = rules.get(source["item"]["reference"], {})
        maximum = rule.get("native_maximum", rule.get("maximum"))
        if maximum is None:
            raise ValueError("Missing native stack rule for chest item")
        if destination is not None and _identity(source) != _identity(destination):
            # Native drag permits unlocked occupied destinations. A whole
            # stack exchanges positions; a partial incompatible move rejects.
            if request["quantity"] != source["item"]["quantity"]:
                raise ValueError("Cannot swap a partial incompatible chest stack")
            source["slot"], destination["slot"] = destination_slot, source_slot
            continue
        moved = _move(source, destination, request["quantity"], maximum, allocate)
        if destination is None:
            moved["slot"] = destination_slot
            items.append(moved)
        if source["item"]["quantity"] == 0:
            items.remove(source)
    return chest


def _ensure(db, account_id):
    identity = uuid.uuid5(_NAMESPACE, str(account_id))
    db.execute(
        "INSERT INTO account_haven_chests(account_id,compartment_id) VALUES(%s,%s) "
        "ON CONFLICT(account_id) DO NOTHING",
        (account_id, identity),
    )
    row = db.execute(
        "SELECT * FROM account_haven_chests WHERE account_id=%s FOR UPDATE",
        (account_id,),
    ).fetchone()
    capacity = max(row["capacity"], provisioned_capacity())
    revision = row["revision"]
    if capacity != row["capacity"]:
        revision += 1
        db.execute(
            "UPDATE account_haven_chests SET capacity=%s,revision=%s WHERE account_id=%s",
            (capacity, revision, account_id),
        )
    return dict(
        id=str(row["compartment_id"]),
        account_id=account_id,
        capacity=capacity,
        compartment_size=TAB_CAPACITY,
        revision=revision,
        items=_unjson(row["items"]),
    )


def load(store, account_id, generation, character_id):
    from .inventory_items import _lease

    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        return _ensure(db, account_id)


def _snapshot(db, item):
    metadata = {}
    for table in _METADATA:
        row = db.execute(
            f"SELECT * FROM {table} WHERE uid=%s", (item["uid"],)
        ).fetchone()
        if row is not None:
            metadata[table] = dict(row)
    return dict(item=deepcopy(item), metadata=metadata)


def _equipped(character):
    return set(_equipment_positions(character))


def _equipment_positions(character):
    from wakfu_server.wire import proto_fields

    result = {}
    for index, build in character["builds"].items():
        for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
            if tag == 10:
                fields = dict(proto_fields(value))
                uid = fields.get(8)
                if uid is not None:
                    result.setdefault(uid, []).append((index, fields.get(16)))
    return result


def deposit_requests(character, chest, requests):
    """Keep equipped items in place while validating the complete owned batch.

    Opcode12038 has no quick-transfer flag, so this applies uniformly to
    deposits instead of guessing the UI action from the number of rows.
    """
    inventory = {item["uid"]: item for item in character["inventory_items"]}
    containers = {
        row["uid"]
        for row in character["inventory_containers"]
        if row["character_id"] == character["id"] and row["kind"] in (0, 1, 2, 3)
    }
    equipped = _equipped(character)
    totals, accepted, skipped = {}, [], set()
    for request in requests:
        tab = resolve(chest, request["compartment"])
        slot, quantity = request["slot"], request["quantity"]
        if type(slot) is not int or not -1 <= slot < tab["capacity"]:
            raise ValueError("Invalid chest compartment position")
        item = inventory.get(request["uid"])
        if item is None or item["character_id"] != character["id"]:
            raise ValueError("Chest deposit item unavailable or foreign")
        if item["container"] not in containers:
            raise ValueError("Unsupported chest source container")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Invalid chest deposit quantity")
        totals[item["uid"]] = totals.get(item["uid"], 0) + quantity
        if totals[item["uid"]] > item["quantity"]:
            raise ValueError("Chest quantity exceeds owned source")
        if item["uid"] in equipped:
            skipped.add(item["uid"])
        else:
            accepted.append(request)
    return accepted, sorted(skipped)


def persist_inventory(db, character_id, inventory, planned):
    """Apply a planned custody change, preserving all supported item metadata."""
    before = {entry["item"]["uid"]: entry for entry in inventory}
    after = {entry["item"]["uid"]: entry for entry in planned}
    for uid in before.keys() - after.keys():
        db.execute(
            "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
            (uid, character_id),
        )
    for uid, entry in after.items():
        item = entry["item"]
        if uid in before:
            if item["quantity"] != before[uid]["item"]["quantity"]:
                db.execute(
                    "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
                    (item["quantity"], uid, character_id),
                )
            continue
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                uid,
                character_id,
                item["reference"],
                item["quantity"],
                item["container"],
                item["slot"],
            ),
        )
        for table, row in entry["metadata"].items():
            if table not in _METADATA:
                raise ValueError("Unsupported stored chest metadata table")
            # Column names derive only from original SELECT rows and our
            # fixed metadata table whitelist, never from a client packet.
            if any(not key.replace("_", "").isalnum() for key in row):
                raise ValueError("Invalid stored chest metadata column")
            columns = list(row)
            db.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES({','.join(['%s'] * len(columns))})",
                tuple(row[key] for key in columns),
            )


def transfer(
    store,
    account_id,
    generation,
    character_id,
    opcode,
    body,
    *,
    opening_token,
    location,
    ranch_session=None,
):
    """Commit item custody and receipt together, then return owned snapshots.

    The dispatcher must create a new opening_token only for an authorized
    native chest open, keep it private, and invalidate it on leave/combat.
    Native messages carry no nonce. Identical retry suppression is bounded to
    three seconds and only applies while the committed revision is current.
    """
    from .inventory_items import _lease
    from .inventory_owner import lock_inventory_character, lock_item_owner
    from .inventory_move import STACKS
    from .inventory_uids import allocate
    from .haven_bag_store import owner_id

    try:
        token = uuid.UUID(str(opening_token))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("Missing active chest opening") from error
    relocate = opcode == 13050
    if relocate:
        requests, deposit = decode_relocate(body), False
    elif opcode == 12038:
        requests, deposit = decode_deposit(body), True
    elif opcode == 12551:
        actor, requests = decode_withdraw(body)
        deposit = False
    else:
        raise ValueError("Unsupported chest opcode")
    digest = hashlib.sha256(opcode.to_bytes(2, "big") + body).digest()
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        bag_id = owner_id(db, character_id)
        if (
            location.get("id") != character_id
            or location.get("account_id") != account_id
        ):
            raise ValueError("Foreign account chest location owner")
        if ranch_session is None:
            allowed = location.get("map_id") == 9
        else:
            allowed = can_access_location(
                location, getattr(ranch_session, "parent", None), ranch_session
            )
            if allowed:
                ranch_session.validate_lease(generation)
        if not allowed or location.get("instance_id") != bag_id:
            raise ValueError("Chest requires the account-owned active private scene")
        chest = _ensure(db, account_id)
        now = store.now()
        receipt = db.execute(
            "SELECT revision,completed_at FROM account_haven_chest_receipts "
            "WHERE account_id=%s AND generation=%s AND opening_token=%s AND request_hash=%s",
            (account_id, generation, token, digest),
        ).fetchone()
        character = store.character(account_id, character_id, db)
        if (
            receipt is not None
            and receipt["revision"] == chest["revision"]
            and timedelta(0) <= now - receipt["completed_at"] < _RETRY_WINDOW
        ):
            from wakfu_server.characters.heroes import load_roster

            roster = load_roster(db, store, account_id, character_id)
            return dict(
                character=character,
                chest=chest,
                applied=False,
                inventory_characters=(roster["leader"], *roster["heroes"]),
            )
        inventory_owner_id = character_id
        if deposit:
            inventory_owner_id = lock_item_owner(
                store,
                db,
                account_id,
                generation,
                character_id,
                sorted({request["uid"] for request in requests}),
            )
        elif not relocate:
            inventory_owner_id = lock_inventory_character(
                store,
                db,
                account_id,
                generation,
                actor,
            )
        inventory_character = (
            character
            if inventory_owner_id == character_id
            else store.character(account_id, inventory_owner_id, db)
        )
        skipped_equipped = []
        if deposit:
            requests, skipped_equipped = deposit_requests(
                inventory_character, chest, requests
            )
            if not requests:
                return dict(
                    character=character,
                    chest=chest,
                    applied=False,
                    skipped_equipped=skipped_equipped,
                    inventory_characters=(inventory_character,),
                )
        inventory = [
            _snapshot(db, item) for item in inventory_character["inventory_items"]
        ]
        if deposit:
            from .exchange_rules import ITEMS

            selected_uids = {request["uid"] for request in requests}
            for entry in inventory:
                if entry["item"]["uid"] not in selected_uids:
                    continue
                template = ITEMS.get(str(entry["item"]["reference"]), {}).get(
                    "binding_template", {}
                )
                binding = entry["metadata"].get("inventory_item_bindings")
                if template.get("enum") == "BOUND_ON_PICKUP_TO_CHARACTER":
                    raise ValueError(
                        "Character-bound items cannot enter an account chest"
                    )
                if (
                    binding
                    and binding["bound"] is True
                    and template.get("enum") != "BOUND_ON_PICKUP_TO_ACCOUNT"
                ):
                    raise ValueError(
                        "Stored binding does not permit account chest custody"
                    )
        if relocate:
            updated = plan_relocate(
                chest, requests, rules=STACKS, allocate=lambda: allocate(db)
            )
        else:
            planned, updated = plan(
                inventory,
                chest,
                requests,
                deposit=deposit,
                character_id=inventory_owner_id,
                containers=inventory_character["inventory_containers"],
                rules=STACKS,
                allocate=lambda: allocate(db),
            )
            persist_inventory(db, inventory_owner_id, inventory, planned)
        updated["revision"] += 1
        db.execute(
            "UPDATE account_haven_chests SET items=%s,revision=%s WHERE account_id=%s",
            (Jsonb(_json(updated["items"])), updated["revision"], account_id),
        )
        db.execute(
            "INSERT INTO account_haven_chest_receipts "
            "(account_id,generation,opening_token,request_hash,revision,completed_at) VALUES(%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(account_id,generation,opening_token,request_hash) DO UPDATE "
            "SET revision=EXCLUDED.revision,completed_at=EXCLUDED.completed_at",
            (account_id, generation, token, digest, updated["revision"], now),
        )
        character = store.character(account_id, character_id, db)
        inventory_character = (
            character
            if inventory_owner_id == character_id
            else store.character(account_id, inventory_owner_id, db)
        )
        return dict(
            character=character,
            inventory_characters=(inventory_character,),
            chest=updated,
            applied=True,
            skipped_equipped=skipped_equipped,
        )


def can_access_location(character, bag_session, ranch_session=None):
    """Authorize a live owned bag or its exact owned ranch child capability.

    This does not replace the selected SQL lease or canonical bag-instance fence.
    Callers must invalidate their opening token when this capability is lost.
    """
    if bag_session is None:
        return False
    if ranch_session is None:
        return (
            bag_session.is_owner is True
            and character.get("map_id") == 9
            and bag_session.owns(character)
        )
    try:
        parent = ranch_session.parent
        return (
            parent is bag_session
            and parent.is_owner is True
            and parent.owner["account_id"] == character["account_id"]
            and ranch_session.owns(character)
            and parent.owns(ranch_session.return_point)
            and character["instance_id"] == parent.bag_instance_id
        )
    except (AttributeError, KeyError, TypeError):
        return False


def validate_open(
    character, bag_session, body, objects, *, fight_active, ranch_session=None
):
    """Authorize only the installed account chest in this owner's interior."""
    import struct

    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid native chest open request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if action != 12 or parameter != 0:
        raise ValueError("Unsupported native chest action")
    if fight_active or not can_access_location(character, bag_session, ranch_session):
        raise ValueError("Chest requires its owner outside combat")
    obj = next(
        (
            row
            for row in objects
            if row["id"] == identity and row["type"] == "AccountChest"
        ),
        None,
    )
    if obj is None or obj["map_id"] != character["map_id"]:
        raise ValueError("Foreign or unknown account chest")
    if (
        abs(character["x"] - obj["x"]) + abs(character["y"] - obj["y"]) > 4
        or abs(character["z"] - obj["z"]) > 1
    ):
        raise ValueError("Account chest is too far away")
    return identity
