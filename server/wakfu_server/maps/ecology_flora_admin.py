"""Transactional outdoor flora resets with durable scene publication."""
import secrets

from psycopg.types.json import Jsonb

from . import ecology_admin, planting
from .monster_initial_population import REGIONS
from .planting_runtime import state_packet

COMMANDS = frozenset(("!nuke-all-flora", "!genesis-all-flora"))


def _inside(map_id, resource, region_id):
    return ecology_admin._inside(map_id, resource, region_id)


def _event(db, resource):
    db.execute(
        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL) "
        "ON CONFLICT(resource_uid) DO UPDATE SET resource=EXCLUDED.resource,group_payload=NULL,published=FALSE",
        (resource["resource_uid"], Jsonb(resource)),
    )


def _nuke(db, map_id, instance_id, region_id):
    from .ecology_flora_planner import is_flora

    events, cancelled_characters = {}, set()
    rows = list(
        db.execute(
            "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid FOR UPDATE",
            (map_id, instance_id),
        )
    )
    removed = 0
    for resource in rows:
        if not is_flora(resource["resource_reference"]) or not _inside(
            map_id, resource, region_id
        ):
            continue
        resource = dict(resource)
        events[resource["resource_uid"]] = dict(resource, stage=0)
        db.execute(
            "DELETE FROM resource_growth_decisions WHERE resource_uid=%s",
            (resource["resource_uid"],),
        )
        db.execute(
            "DELETE FROM planted_resources WHERE resource_uid=%s",
            (resource["resource_uid"],),
        )
        removed += 1
    # Fence prepared events even if their originating resource no longer exists.
    for row in db.execute(
        "SELECT resource_uid,resource FROM planting_growth_outbox WHERE NOT published AND group_payload IS NULL "
        "AND (resource->>'map_id')::integer=%s AND coalesce((resource->>'instance_id')::bigint,0)=%s FOR UPDATE",
        (map_id, instance_id),
    ):
        resource = row["resource"]
        if is_flora(resource["resource_reference"]) and _inside(
            map_id, resource, region_id
        ):
            resource = {
                key: value for key, value in resource.items() if key != "flora_spawn"
            }
            events[row["resource_uid"]] = dict(resource, stage=0)
    for row in db.execute(
        "SELECT operation_id,resource FROM planting_receipts WHERE NOT published AND group_payload IS NULL "
        "AND (resource->>'map_id')::integer=%s AND coalesce((resource->>'instance_id')::bigint,0)=%s FOR UPDATE",
        (map_id, instance_id),
    ):
        resource = row["resource"]
        if is_flora(resource["resource_reference"]) and _inside(
            map_id, resource, region_id
        ):
            db.execute(
                "UPDATE planting_receipts SET published=TRUE WHERE operation_id=%s",
                (row["operation_id"],),
            )
            events.setdefault(resource["resource_uid"], dict(resource, stage=0))
    cancelled = 0
    for row in db.execute(
        "SELECT id,character_id,body FROM ecology_planting_intents WHERE status='pending' "
        "AND (actor_location->>'map_id')::integer=%s AND coalesce((actor_location->>'instance_id')::bigint,0)=%s FOR UPDATE",
        (map_id, instance_id),
    ):
        try:
            request = planting.decode(bytes(row["body"]))
            seed = next(
                (
                    seed
                    for seed in planting.SEEDS.values()
                    if seed["action_id"] == request["action_id"]
                ),
                None,
            )
        except (ValueError, KeyError):
            continue
        if (
            seed is not None
            and is_flora(seed["resource_reference"])
            and _inside(map_id, request, region_id)
        ):
            db.execute(
                "UPDATE ecology_planting_intents SET status='cancelled' WHERE id=%s",
                (row["id"],),
            )
            cancelled_characters.add(row["character_id"])
            cancelled += 1
    for resource in events.values():
        _event(db, resource)
    return dict(
        removed=removed,
        cancelled=cancelled,
        cancelled_characters=sorted(cancelled_characters),
        packets=[state_packet(resource, 0) for resource in events.values()],
        events=list(events.values()),
    )


def _genesis(db, map_id, instance_id, region_id, *, players=(), prepared=None):
    from .ecology_flora_planner import plan

    existing = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid FOR UPDATE",
            (map_id, instance_id),
        )
    ]
    occupied = {(row["x"], row["y"]) for row in existing}
    for row in db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
        (map_id, instance_id),
    ):
        occupied.update((member["x"], member["y"]) for member in row["members"])
    for table in ("mining_vein_slots", "fishing_spot_slots"):
        occupied.update(
            (row["x"], row["y"])
            for row in db.execute(
                f"SELECT x,y FROM {table} WHERE map_id=%s AND instance_id=%s AND enabled",
                (map_id, instance_id),
            )
        )
    for row in db.execute(
        "SELECT resource FROM planting_growth_outbox WHERE NOT published "
        "AND (resource->>'map_id')::integer=%s AND coalesce((resource->>'instance_id')::bigint,0)=%s",
        (map_id, instance_id),
    ):
        occupied.add((row["resource"]["x"], row["resource"]["y"]))
    occupied.update(
        (p["x"], p["y"])
        for p in players
        if p.get("map_id") == map_id and p.get("instance_id", 0) == instance_id
    )
    planned = plan(prepared, existing, occupied)
    events = []
    now_ms = db.execute(
        "SELECT floor(extract(epoch FROM CURRENT_TIMESTAMP)*1000)::bigint AS now_ms"
    ).fetchone()["now_ms"]
    for row in planned["rows"]:
        resource = dict(
            row,
            resource_uid=secrets.randbits(62) + 1,
            map_id=map_id,
            instance_id=instance_id,
            creation_time=int(now_ms),
        )
        cell = (map_id, instance_id, resource["x"], resource["y"])
        # Planting takes cell before flora; never wait in the opposite order.
        locked = db.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked",
            ("planting-cell:" + ":".join(map(str, cell)),),
        ).fetchone()["locked"]
        if not locked:
            continue
        inserted = db.execute(
            "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING resource_uid",
            tuple(
                resource[key]
                for key in (
                    "resource_uid",
                    "map_id",
                    "instance_id",
                    "x",
                    "y",
                    "z",
                    "resource_reference",
                    "stage",
                    "creation_time",
                )
            ),
        ).fetchone()
        if inserted is None:
            continue
        event = dict(resource, flora_spawn=True)
        _event(db, event)
        events.append(event)
    return dict(
        added=len(events),
        packets=[planting.resource_packet(resource) for resource in events],
        events=events,
        warnings=planned.get("warnings", []),
    )


def execute(
    store, groups, character, command, *, players=(), coordination=None, publish=None
):
    """Commit/publicize each habitat independently; retries preserve scene events."""
    if command not in COMMANDS:
        raise ValueError("Unknown flora administrator command")
    if store is None or groups is None:
        raise ValueError("Persistent ecology administration is unavailable")
    genesis = command == "!genesis-all-flora"
    with store.connection() as db:
        ecology_admin._authorize(db, character)
    scopes = (
        [
            (map_id, 0, region_id)
            for (map_id, region_id), habitat in sorted(REGIONS.items())
            if habitat.get("plant_capacity", 0) > 0
        ]
        if genesis
        else [(map_id, 0, None) for map_id in sorted({m for m, _ in REGIONS})]
    )
    result = dict(ecology_admin._empty_result(), flora=True)
    for scope in scopes:
        try:
            from .ecology_flora_planner import prepare

            prepared = prepare(scope[0], scope[2]) if genesis else None
            with coordination(scope) if coordination is not None else groups.lock:
                with store.connection() as db, db.transaction():
                    ecology_admin._authorize(db, character)
                    # Harvest locks resources before flora population. Keep that
                    # order even for standalone callers without world fences.
                    list(
                        db.execute(
                            "SELECT resource_uid FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid FOR UPDATE",
                            scope[:2],
                        )
                    )
                    db.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                        (f"flora-population:{scope[0]}:{scope[1]}",),
                    )
                    current_players = players() if callable(players) else players
                    if isinstance(current_players, dict):
                        current_players = current_players.get("players", ())
                    outcome = (
                        _genesis(db, *scope, players=current_players, prepared=prepared)
                        if genesis
                        else _nuke(db, *scope)
                    )
                    scoped = dict(
                        ecology_admin._empty_result(), flora=True, scopes=[scope]
                    )
                    for key in (
                        "removed",
                        "cancelled",
                        "added",
                        "cancelled_characters",
                        "warnings",
                    ):
                        scoped[key] = outcome.get(key, scoped[key])
                    scoped["location_packets"] = [
                        (*scope[:2], opcode, payload)
                        for opcode, payload in outcome["packets"]
                    ]
                    audit = {
                        key: value
                        for key, value in scoped.items()
                        if key != "location_packets"
                    }
                    operation = db.execute(
                        "INSERT INTO ecology_admin_operations(account_id,character_id,command,outcome) VALUES(%s,%s,%s,%s) RETURNING id",
                        (
                            character["account_id"],
                            character["id"],
                            command,
                            Jsonb(audit),
                        ),
                    ).fetchone()["id"]
                    scoped.update(operation_id=operation, operation_ids=[operation])
                for key in ("removed", "cancelled", "added"):
                    result[key] += scoped[key]
                for key in (
                    "location_packets",
                    "scopes",
                    "cancelled_characters",
                    "warnings",
                    "operation_ids",
                ):
                    result[key].extend(scoped[key])
                result["operation_id"] = operation
                if publish is not None:
                    try:
                        publish(scoped)
                        with store.connection() as db:
                            for event in outcome["events"]:
                                db.execute(
                                    "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=%s AND resource=%s AND group_payload IS NULL",
                                    (event["resource_uid"], Jsonb(event)),
                                )
                    except (OSError, ValueError) as error:
                        result["publication_failures"].append((*scope, str(error)))
        except ValueError as error:
            result["failures"].append((*scope, str(error)))
    result[
        "message"
    ] = f'Flora: removed={result["removed"]}, cancelled plantings={result["cancelled"]}, added={result["added"]}; scopes={len(result["scopes"])}, skipped={len(result["failures"])}.'
    for map_id, instance_id, region_id, reason in result["failures"]:
        result["message"] += f"\nMap {map_id}, region {region_id}: {reason}"
    if result["warnings"]:
        result["message"] += "\n" + "\n".join(result["warnings"])
    if result["publication_failures"]:
        result["message"] += "\nDelivery pending; durable scene events will retry."
    return result
