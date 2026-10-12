"""Public garden policy for authoritative dynamic Haven Bag interiors.

Garden plants use the shared durable flora growth and harvesting engine. Native
exterior terrain and weather catalogs do not describe these dynamic interiors.
The native client synthesizes ground 28 for garden rooms (fvs.gx).
"""

from .haven_bag_store import instance_id

LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")
GARDEN_GEMS = frozenset((4266, 11099))
RANCH_MAP_ID = 1440


def is_private_garden(character):
    """Recognize a server-owned bag or its authorized private Ranch scene."""
    if not isinstance(character, dict):
        return False
    map_id = character.get("map_id")
    instance = character.get("instance_id")
    if type(instance) is not int or instance <= 0:
        return False
    if map_id == 9:
        return instance == instance_id(character)
    if map_id != RANCH_MAP_ID:
        return False
    config = character.get("haven_bag")
    owner = config.get("owner_id") if isinstance(config, dict) else None
    return (
        character.get("haven_ranch_session") is True
        and type(owner) is int
        and owner > 0
        and owner == instance
    )


def _load_owner_bag(store, owner_id):
    """Load only the account's canonical bag selected for this private Ranch."""
    with store.connection() as db:
        row = db.execute(
            "SELECT h.character_id AS owner_id,h.appearance_id,h.layout AS rooms,h.locked,"
            "h.furniture,h.access FROM account_haven_bags a "
            "JOIN haven_bags h ON h.character_id=a.character_id "
            "JOIN characters c ON c.id=h.character_id "
            "WHERE a.character_id=%s AND c.deleted_at IS NULL",
            (owner_id,),
        ).fetchone()
    if row is None:
        raise ValueError("Ranch requires an authoritative Haven Bag")
    return dict(row)


def active_character(stored, players, *, store=None):
    """Overlay only a server-owned active interior; retain SQL inventory/build."""
    live = next((p for p in players if p["id"] == stored["id"]), None)
    if live is None or live.get("map_id") not in (9, RANCH_MAP_ID):
        return stored
    if live.get("account_id") != stored["account_id"]:
        raise ValueError("Garden actor account does not match its active session")
    config = live.get("haven_bag")
    if live.get("map_id") == RANCH_MAP_ID:
        owner_id = live.get("instance_id")
        if type(owner_id) is not int or owner_id <= 0:
            raise ValueError("Ranch requires an active private instance")
        saved_config = stored.get("haven_bag")
        if (
            config is None
            and isinstance(saved_config, dict)
            and saved_config.get("owner_id") == owner_id
        ):
            config = saved_config
        if store is not None:
            durable = _load_owner_bag(store, owner_id)
            if config is not None and config != durable:
                raise ValueError("Ranch Haven Bag configuration is stale")
            config = durable
        if not isinstance(config, dict) or config.get("owner_id") != owner_id:
            raise ValueError("Ranch requires its authoritative Haven Bag")
        visitor = live.get("haven_bag_visitor", False)
        if type(visitor) is not bool:
            raise ValueError("Invalid Ranch visitor authority")
        return {
            **stored,
            **{key: live[key] for key in LOCATION_KEYS},
            "haven_bag": config,
            "haven_bag_visitor": visitor,
            "haven_ranch_session": True,
        }
    if not config:
        if live.get("instance_id") == instance_id(stored):
            config = stored.get("haven_bag") or {}
        elif (
            store is not None
            and type(live.get("instance_id")) is int
            and live["instance_id"] > 0
        ):
            # External ecology carries scalar occupancy only. Resolve the bag
            # from its authoritative private instance rather than substituting
            # the visitor's SQL layout or transmitting inventory graphs.
            from .haven_bag_store import load

            with store.connection() as db:
                config = load(db, live["instance_id"])
        else:
            config = {}
    if (
        type(live.get("instance_id")) is not int
        or live["instance_id"] <= 0
        or (live["instance_id"] != config.get("owner_id", stored["id"]))
    ):
        raise ValueError("Garden requires an authoritative active Haven Bag")
    # The live session supplies the visited layout and location only. Seeds,
    # harvested items, profession progress and identity remain the visitor's.
    return {
        **stored,
        **{key: live[key] for key in LOCATION_KEYS},
        "haven_bag": config,
        "haven_bag_visitor": live.get("haven_bag_visitor", False),
    }


def room_at(character, x, y):
    if character.get("map_id") != 9 or character.get("instance_id") != instance_id(
        character
    ):
        raise ValueError("Garden requires the active Haven Bag layout")
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


def validate_target(character, x, y, *, z=None):
    """Validate a bag-room cell or exact native-height private Ranch cell."""
    if character.get("map_id") == 9:
        room_at(character, x, y)
        if z not in (None, 0):
            raise ValueError("Unknown Haven Bag garden height")
        return 0
    if not is_private_garden(character) or character.get("map_id") != RANCH_MAP_ID:
        raise ValueError("Planting requires an authorized private garden")
    if any(type(value) is not int for value in (x, y)):
        raise ValueError("Invalid Ranch planting cell")
    from wakfu_server.planting_cells import private_surfaces

    candidates = private_surfaces(RANCH_MAP_ID, x, y)
    if z is not None:
        if (
            type(z) is not int
            or len([cell for cell in candidates if cell["z"] == z]) != 1
        ):
            raise ValueError("Unknown native Ranch planting height")
        return z
    if len(candidates) != 1:
        raise ValueError("Absent or ambiguous native Ranch planting height")
    return candidates[0]["z"]


def reachable(character, resource):
    if character.get("map_id") == RANCH_MAP_ID:
        try:
            validate_target(character, resource["x"], resource["y"], z=resource["z"])
        except ValueError:
            return False
        from wakfu_server.combat_terrain import map_geometry

        source = tuple(character[key] for key in ("x", "y", "z"))
        target = (resource["x"], resource["y"], resource["z"])
        return any(
            tuple(start) == source and tuple(end) == target
            for start, end in map_geometry(RANCH_MAP_ID)["edges"]
        )
    room_at(character, resource["x"], resource["y"])
    return (
        character["z"] == resource["z"] == 0
        and abs(character["x"] - resource["x"]) + abs(character["y"] - resource["y"])
        == 1
    )


def authorize(store, character, request, seed, resource):
    if resource["monster_resource"] and character.get("map_id") != RANCH_MAP_ID:
        raise ValueError("Monster reproduction is unavailable inside private gardens")
    target_z = validate_target(character, request["x"], request["y"])
    target = dict(request, z=target_z)
    if not reachable(character, target):
        raise ValueError("Move next to the garden planting cell")
    if character["map_id"] == RANCH_MAP_ID:
        from wakfu_server.planting_cells import assert_private_cell_unoccupied

        assert_private_cell_unoccupied(store, character, request)
        return target_z
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
