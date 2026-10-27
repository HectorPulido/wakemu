"""Native seasonal dungeon entry intents, available only at reviewed entrances."""
import struct
import time

# The first three maps have reviewed event windows; 472 is the Kwismas
# native exterior; its reviewed interiors are 474 and 476. No arbitrary
# seasonal-looking criterion is waived.
REVIEWED_MAPS = frozenset((443, 1075, 146, 474, 476))
_REQUEST = struct.Struct(">qiBi")


def at_entrance(actor, source):
    """Use persisted authoritative position and the native interaction mask."""
    from wakfu_server.maps.teleporter_approach import callback

    class Stationary:
        approved = ()

    return callback(Stationary(), map_id=actor["map_id"], instance_id=0)(actor, source)


def route_target(route, source, revision, *, minimum_level_offer=False):
    """Bind the exact reviewed source, native destination and entry criterion."""
    if type(minimum_level_offer) is not bool:
        raise ValueError("Invalid owned dungeon entrance offer")
    if route["start_map_id"] not in REVIEWED_MAPS and not minimum_level_offer:
        return None
    if (source["map_id"], source["id"]) != (
        route["entry_map_id"],
        route["entry_object_id"],
    ):
        return None
    destination = next(
        (
            item
            for item in source["destinations"]
            if item["destination_id"] == route["destination_id"]
        ),
        None,
    )
    if destination is None or (
        destination["map_id"] != route["start_map_id"]
        or destination["criterion"] != route["criterion"]
        or destination["cyZ"]
        != (route.get("native_template_id") or route["template_id"])
        or not destination.get("native_altitude_walkable", False)
        or destination.get("cyX", 0) != 0
    ):
        return None
    return dict(
        kind="seasonal_entry",
        route_kind="dungeon",
        route_key=route["key"],
        entry_map_id=route["entry_map_id"],
        source_id=source["id"],
        destination_id=destination["destination_id"],
        destination_map_id=destination["map_id"],
        criterion=destination["criterion"],
        catalog_revision=revision,
    )


def public_allowed(actor, destination):
    from wakfu_server.maps.seasonal_transport import evaluate

    try:
        return (
            evaluate(
                destination["criterion"],
                actor,
                destination["map_id"],
                now_ms=int(time.time() * 1000),
            )
            is True
        )
    except ValueError:
        return False


def actions(db, identity):
    from . import player_travel

    actor = db.execute(
        "SELECT id,account_id,level,map_id,instance_id,x,y,z FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (identity["character_id"], identity["account_id"]),
    ).fetchone()
    if actor is None or actor["instance_id"] != 0:
        return []
    active = db.execute(
        "SELECT a.revision FROM native_catalog_active a JOIN native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete"
    ).fetchone()
    if active is None:
        return []
    revision = active["revision"]
    sources = {
        (item["map_id"], item["id"]): item
        for item in (
            player_travel._document(db, revision, "native-generic-teleporters.json")
            or []
        )
    }
    rules = player_travel._eligible(db, identity)
    rows = db.execute(
        "SELECT c.configuration->'route' AS route FROM dungeon_runtime_configurations c "
        "JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version) ORDER BY c.route_key"
    ).fetchall()
    private_maps = {item["route"]["start_map_id"] for item in rows}
    result = []
    # A reviewed public event island has no dungeon route or achievement card.
    public_source = sources.get((235, 18012))
    if (
        actor["map_id"] == 235
        and public_source is not None
        and at_entrance(actor, public_source)
    ):
        native = next(
            (
                item
                for item in public_source["destinations"]
                if item["destination_id"] == 4810 and item["map_id"] == 146
            ),
            None,
        )
        if (
            native is not None
            and public_allowed(actor, native)
            and native["cyZ"] < 0
            and native.get("native_altitude_walkable") is True
            and native.get("cyX", 0) == 0
        ):
            result.append(
                dict(
                    key="seasonal.public.146",
                    label="Enter summer island",
                    kind="seasonal_entry",
                    enabled=True,
                    description="Native entrance items and level requirements still apply.",
                    target=dict(
                        kind="seasonal_entry",
                        route_kind="public",
                        entry_map_id=235,
                        source_id=18012,
                        destination_id=4810,
                        destination_map_id=146,
                        criterion=native["criterion"],
                        catalog_revision=revision,
                    ),
                )
            )
    for row in rows:
        route = row["route"]
        if route["entry_map_id"] != actor["map_id"] or actor["map_id"] in private_maps:
            continue
        source = sources.get((actor["map_id"], route["entry_object_id"]))
        rule = rules.get(f"content-v1.dungeon.{route['definition_id']}")
        if source is None or rule is None or not at_entrance(actor, source):
            continue
        minimum_offer = False
        if route["start_map_id"] not in REVIEWED_MAPS:
            from wakfu_server.maps.dungeon_entry_access import minimum_offer_allowed

            minimum_offer = minimum_offer_allowed(
                db,
                route["criterion"],
                character=actor,
                destination_map_id=route["start_map_id"],
            )
        target = route_target(
            route, source, revision, minimum_level_offer=minimum_offer
        )
        if target is not None:
            result.append(
                dict(
                    key=("dungeon.enter." if minimum_offer else "seasonal.enter.")
                    + route["key"],
                    label="Enter: " + rule["title"],
                    kind="seasonal_entry",
                    description="Native entrance items, party and travel requirements still apply.",
                    enabled=True,
                    definition_key=rule["key"],
                    target=target,
                )
            )
    return result


def resolve(db, action):
    current = next(
        (item for item in actions(db, action) if item["key"] == action["action_key"]),
        None,
    )
    if current is None or current["target"] != action["target"]:
        raise ValueError(
            "Seasonal entrance changed or is unavailable; stand at its entrance and refresh Adventures."
        )
    return current["target"]


def request(target):
    return _REQUEST.pack(target["source_id"], target["destination_id"], 0, 2)
