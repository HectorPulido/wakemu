"""Atomic inventory <-> haven-bag gem transfers.

The native incremental replies move one physical gem between the two client
containers. PostgreSQL commits the matching ownership transition first.
"""
import copy
import struct
from psycopg.types.json import Jsonb

from .haven_bag_store import GEM_TYPES, owner_id


def can_transfer(bag_session, character, *, fight_active):
    """Guard dispatcher requests against visitors, stale locations and fights."""
    return (
        fight_active is False
        and bag_session is not None
        and bag_session.is_owner
        and bag_session.owns(character)
    )


def decode_insert(body):
    if not isinstance(body, bytes) or len(body) != 10 or body[-1] != 0:
        raise ValueError("Invalid haven-bag gem insertion request")
    uid, room = struct.unpack(">qB", body[:9])
    if uid <= 0 or room > 8:
        raise ValueError("Invalid haven-bag gem insertion identity")
    return {"uid": uid, "room": room}


def decode_remove(body):
    if not isinstance(body, bytes) or len(body) != 11:
        raise ValueError("Invalid haven-bag gem removal request")
    container, position, room, primary = struct.unpack(">qBBB", body)
    if container <= 0 or position > 127 or room > 8 or primary not in (0, 1):
        raise ValueError("Invalid haven-bag gem removal destination")
    return {
        "container": container,
        "position": position,
        "room": room,
        "primary": bool(primary),
    }


def _layout_row(db, character_id):
    row = db.execute(
        "SELECT layout FROM haven_bags WHERE character_id=%s FOR UPDATE",
        (character_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing owned haven bag")
    return copy.deepcopy(row["layout"])


def _rooms(layout):
    return {row["index"]: row for row in layout}


def _empty_room(index):
    return dict(
        index=index,
        enabled=False,
        primary_ref=-1,
        primary_uid=0,
        secondary_ref=-1,
        secondary_uid=0,
    )


def _item_options(db, uid):
    elements = db.execute(
        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
        (uid,),
    ).fetchone()
    shard = db.execute(
        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s", (uid,)
    ).fetchone()
    result = {}
    if elements is not None:
        result.update(dict(elements))
    if shard is not None:
        result["shard_state"] = bytes(shard["shard_state"])
    return result


def _gem_transfer_record(db, uid):
    options = _item_options(db, uid)
    return (
        options.get("damage_elements"),
        options.get("resistance_elements"),
        options.get("shard_state"),
    )


def insert(store, account_id, generation, character_id, body, *, location):
    """Apply native 12177 and return ordered client packets.

    A stacked source is split into a transient client inventory unit, then
    consumed by native 12234. The durable remainder keeps its original UID.
    """
    request = decode_insert(body)
    if (
        not isinstance(location, dict)
        or location.get("map_id") != 9
        or type(location.get("instance_id")) is not int
    ):
        raise ValueError("Gem insertion requires the owner's active haven bag")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        bag_id = owner_id(db, character_id)
        if location["instance_id"] != bag_id:
            raise ValueError("Gem transfer requires the account owner bag")
        layout = _layout_row(db, bag_id)
        rooms = _rooms(layout)
        room = rooms.get(request["room"])
        if room is None:
            room = _empty_room(request["room"])
            layout.append(room)
            rooms[request["room"]] = room

        source_uid = request["uid"]
        installed = db.execute(
            "SELECT uid FROM haven_bag_gems WHERE account_id=%s AND character_id=%s "
            "AND room_index=%s AND source_uid=%s ORDER BY primary_slot DESC LIMIT 1",
            (account_id, bag_id, request["room"], source_uid),
        ).fetchone()
        if installed is not None:
            current = store.character(account_id, character_id, db)
            return {
                "uid": installed["uid"],
                "room": request["room"],
                "character": current,
                "packets": [
                    (12234, struct.pack(">qB", installed["uid"], request["room"]))
                ],
                "replayed": True,
            }

        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (source_uid, character_id),
        ).fetchone()
        if item is None or item["reference"] not in GEM_TYPES:
            raise ValueError("Gem is not an available owned item")
        if db.execute(
            "SELECT 1 FROM inventory_mounts WHERE uid=%s", (source_uid,)
        ).fetchone():
            raise ValueError("Mounted item cannot be installed as a gem")

        ref = item["reference"]
        primary_present = room["primary_ref"] != -1
        if not primary_present:
            primary_slot = True
        elif room["secondary_ref"] == -1:
            if GEM_TYPES[room["primary_ref"]] != GEM_TYPES[ref]:
                raise ValueError("Gem type does not match the room's primary gem")
            primary_slot = False
        else:
            raise ValueError("Haven-bag room has no available gem slot")

        from .inventory_uids import allocate
        from .inventory_items import insertion

        item_uid = source_uid
        packet_item = dict(item)
        packet_item.update(_item_options(db, source_uid))
        packets = []
        if item["quantity"] > 1:
            container = db.execute(
                "SELECT capacity FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
                (item["container"], character_id),
            ).fetchone()
            occupied = {
                row["slot"]
                for row in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s FOR UPDATE",
                    (item["container"],),
                )
            }
            free_slot = (
                next(
                    (
                        slot
                        for slot in range(container["capacity"])
                        if slot not in occupied
                    ),
                    None,
                )
                if container is not None
                else None
            )
            if free_slot is None:
                raise ValueError("A free inventory slot is required to split this gem")
            item_uid = allocate(db)
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_uid,),
            )
            packets.append((12470, struct.pack(">qh", source_uid, -1)))
            packet_item.update(uid=item_uid, quantity=1, slot=free_slot)
            packets.append(insertion(packet_item))
        else:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (source_uid,))

        damage = packet_item.get("damage_elements")
        resistance = packet_item.get("resistance_elements")
        shard = packet_item.get("shard_state")
        db.execute(
            "INSERT INTO haven_bag_gems(uid,account_id,character_id,room_index,primary_slot,reference,source_uid,damage_elements,resistance_elements,shard_state) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                item_uid,
                account_id,
                bag_id,
                request["room"],
                primary_slot,
                ref,
                source_uid,
                damage,
                resistance,
                shard,
            ),
        )
        key = "primary" if primary_slot else "secondary"
        room[key + "_ref"] = ref
        room[key + "_uid"] = item_uid
        room["enabled"] = True
        db.execute(
            "UPDATE haven_bags SET layout=%s WHERE character_id=%s",
            (Jsonb(layout), bag_id),
        )
        packets.append((12234, struct.pack(">qB", item_uid, request["room"])))
        current = store.character(account_id, character_id, db)
        return {
            "uid": item_uid,
            "room": request["room"],
            "character": current,
            "packets": packets,
            "replayed": False,
        }


def remove(store, account_id, generation, character_id, body, *, location):
    """Apply native 13090; selector true chooses the primary gem (nQ(true))."""
    request = decode_remove(body)
    if (
        not isinstance(location, dict)
        or location.get("map_id") != 9
        or type(location.get("instance_id")) is not int
    ):
        raise ValueError("Gem removal requires the owner's active haven bag")
    if location.get("other_occupants", False) is not False:
        raise ValueError("Cannot remove a gem while visitors are in the haven bag")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        bag_id = owner_id(db, character_id)
        if location["instance_id"] != bag_id:
            raise ValueError("Gem transfer requires the account owner bag")
        layout = _layout_row(db, bag_id)
        rooms = _rooms(layout)
        room = rooms.get(request["room"])
        if room is None:
            raise ValueError("Unknown haven-bag room")
        key = "primary" if request["primary"] else "secondary"
        ref, uid = room[key + "_ref"], room[key + "_uid"]
        if ref == -1 or uid <= 0:
            raise ValueError("Selected haven-bag gem slot is empty")
        if request["room"] == 0 and request["primary"]:
            raise ValueError("The fixed entrance gem cannot be removed")
        if request["primary"] and room["secondary_ref"] != -1:
            raise ValueError("Remove the secondary gem before the primary gem")
        if request["primary"]:
            if db.execute(
                "SELECT 1 FROM planted_resources WHERE map_id=9 AND instance_id=%s "
                "AND (x / 6) * 3 + (y / 6)=%s LIMIT 1",
                (bag_id, request["room"]),
            ).fetchone():
                raise ValueError("Remove garden plants before removing the room gem")
            bag = db.execute(
                "SELECT furniture FROM haven_bags WHERE character_id=%s",
                (bag_id,),
            ).fetchone()
            if any(
                item.get("deployed") and item.get("room") == request["room"]
                for item in bag["furniture"]
            ):
                raise ValueError("Cannot disable a room that still contains furniture")

        target = db.execute(
            "SELECT capacity FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["container"], character_id),
        ).fetchone()
        if target is None or request["position"] >= target["capacity"]:
            raise ValueError("Invalid owned inventory destination")
        if db.execute(
            "SELECT 1 FROM inventory_items WHERE container=%s AND slot=%s FOR UPDATE",
            (request["container"], request["position"]),
        ).fetchone():
            raise ValueError("Inventory destination is occupied")

        gem = db.execute(
            "SELECT * FROM haven_bag_gems WHERE uid=%s AND account_id=%s AND character_id=%s "
            "AND room_index=%s AND primary_slot=%s FOR UPDATE",
            (uid, account_id, bag_id, request["room"], request["primary"]),
        ).fetchone()
        if gem is None or gem["reference"] != ref:
            raise ValueError("Gem ownership record does not match the room")
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,1,%s,%s)",
            (uid, character_id, ref, request["container"], request["position"]),
        )
        if gem["damage_elements"] is not None:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,%s,%s)",
                (uid, gem["damage_elements"], gem["resistance_elements"]),
            )
        if gem["shard_state"] is not None:
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (uid, gem["shard_state"]),
            )
        db.execute("DELETE FROM haven_bag_gems WHERE uid=%s", (uid,))
        room[key + "_ref"] = -1
        room[key + "_uid"] = 0
        room["enabled"] = request["room"] == 0 or room["primary_ref"] != -1
        db.execute(
            "UPDATE haven_bags SET layout=%s WHERE character_id=%s",
            (Jsonb(layout), bag_id),
        )
        current = store.character(account_id, character_id, db)
        from .inventory_items import insertion

        restored_item = next(
            item for item in current["inventory_items"] if item["uid"] == uid
        )
        return {
            "uid": uid,
            "container": request["container"],
            "position": request["position"],
            "room": request["room"],
            "primary": request["primary"],
            "character": current,
            "packets": [
                (
                    12451,
                    struct.pack(
                        ">qBBB",
                        request["container"],
                        request["position"],
                        request["room"],
                        request["primary"],
                    ),
                ),
                # Native bpq.a(BJBZZ) only removes the room gem for remote
                # acknowledgements; it never inserts it into the inventory.
                # Publish the restored item after removing its room reference.
                insertion(restored_item),
            ],
        }
