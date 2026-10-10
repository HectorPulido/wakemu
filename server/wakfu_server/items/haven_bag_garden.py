"""Owner-scoped garden policy for dynamic Haven Bag rooms.

Garden plants use the shared durable flora growth and harvesting engine. Native
exterior terrain and weather catalogs do not describe these dynamic interiors.
The native client synthesizes ground 28 for garden rooms (fvs.gx).
"""

from .haven_bag_store import instance_id

LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")
GARDEN_GEMS = frozenset((4266, 11099))


def active_character(stored, players):
    """Overlay only a server-owned active interior; retain SQL inventory/build."""
    live = next((p for p in players if p["id"] == stored["id"]), None)
    if live is None or live.get("map_id") != 9:
        return stored
    if (
        live.get("instance_id") != instance_id(stored)
        or live.get("account_id") != stored["account_id"]
    ):
        raise ValueError("Garden requires the owner's active Haven Bag")
    return {**stored, **{key: live[key] for key in LOCATION_KEYS}}


def room_at(character, x, y):
    if character.get("map_id") != 9 or character.get("instance_id") != instance_id(
        character
    ):
        raise ValueError("Garden requires the owner's active Haven Bag")
    if any(type(v) is not int or not 0 <= v < 18 for v in (x, y)):
        raise ValueError("Garden target is outside the Haven Bag rooms")
    config = character.get("haven_bag") or {}
    index = (x // 6) * 3 + y // 6
    room = next((r for r in config.get("rooms", ()) if r["index"] == index), None)
    if (
        room is None
        or not room.get("enabled")
        or room.get("primary_ref") not in GARDEN_GEMS
    ):
        raise ValueError("Planting requires an installed garden gem")
    return room


def reachable(character, resource):
    room_at(character, resource["x"], resource["y"])
    return (
        character["z"] == resource["z"] == 0
        and abs(character["x"] - resource["x"]) + abs(character["y"] - resource["y"])
        == 1
    )


def authorize(store, character, request, seed, resource):
    if resource["monster_resource"]:
        raise ValueError("Monster reproduction is unavailable inside Haven Bags")
    room_at(character, request["x"], request["y"])
    if not reachable(character, dict(request, z=0)):
        raise ValueError("Move next to the garden planting cell")
    for item in (character.get("haven_bag") or {}).get("furniture", ()):
        if item.get("deployed") and (item["x"], item["y"]) == (
            request["x"],
            request["y"],
        ):
            raise ValueError("Garden planting cell contains furniture")
    with store.connection() as db:
        if db.execute(
            "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
            (9, instance_id(character), request["x"], request["y"]),
        ).fetchone():
            raise ValueError("Garden planting cell is occupied")
    return 0
