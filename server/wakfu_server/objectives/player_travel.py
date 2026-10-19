"""Read-only native destination resolver for authored player travel actions.

World owns scene readiness, session fencing and transactional movement. Browser
input selects a stable action key; it never supplies coordinates or a price.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import hashlib
import json
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from .schedules import period_key

_CACHE = {}
_CACHE_LOCK = threading.RLock()
_GEOMETRY_INDEXES = OrderedDict()
_TARGETS = OrderedDict()
_GEOMETRY_LIMIT = 64
_GEOMETRY_COLUMN_LIMIT = 300_000
_TARGET_LIMIT = 4096


def _document(db, revision, path):
    identity = (revision, path)
    with _CACHE_LOCK:
        if identity in _CACHE:
            return _CACHE[identity]
    row = db.execute(
        "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
        (revision, path),
    ).fetchone()
    if row is None:
        return None
    raw = bytes(row["raw"])
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Native travel catalog checksum mismatch")
    value = json.loads(raw)
    with _CACHE_LOCK:
        # A process only needs its current release; keep obsolete releases bounded.
        if len(_CACHE) >= 1024:
            _CACHE.clear()
        _CACHE[identity] = value
    return value


def _coordinates(map_id, x, y, z):
    # Native generic object coordinates are integral JSON doubles. Preserve
    # exact values only; never truncate a fractional height or position.
    values = (map_id, x, y, z)
    if any(
        type(v) is not int and not (type(v) is float and v.is_integer()) for v in values
    ):
        return None
    return tuple(map(int, values))


def _floor_target(geometry, map_id, x, y, z, *, nearby=False):
    """Choose only actual single-height native floor, optionally near an entrance."""
    if not isinstance(geometry, dict):
        return None
    cells = {tuple(cell) for cell in geometry.get("cells", [])}
    heights = {}
    for cx, cy, cz in cells:
        heights.setdefault((cx, cy), set()).add(cz)
    if (x, y, z) in cells and len(heights[(x, y)]) == 1:
        selected = (x, y, z)
    elif nearby:
        candidates = [
            cell
            for cell in cells
            if abs(cell[0] - x) + abs(cell[1] - y) <= 4
            and abs(cell[2] - z) <= 1
            and len(heights[cell[:2]]) == 1
        ]
        if not candidates:
            return None
        selected = min(
            candidates,
            key=lambda cell: (
                abs(cell[0] - x) + abs(cell[1] - y),
                abs(cell[2] - z),
                *cell,
            ),
        )
    else:
        return None
    return dict(
        map_id=map_id, instance_id=0, x=selected[0], y=selected[1], z=selected[2]
    )


def _geometry_index(db, revision, map_id):
    """Index one immutable map once; ambiguous columns have no safe arrival."""
    cache_key = (revision, map_id)
    with _CACHE_LOCK:
        if cache_key in _GEOMETRY_INDEXES:
            _GEOMETRY_INDEXES.move_to_end(cache_key)
            return _GEOMETRY_INDEXES[cache_key]
        # Native geometry documents include massive edge/animation trees. Keep
        # only floor cells in Python; PostgreSQL verifies the whole raw SHA and
        # projects cells without transferring or caching unrelated geometry.
        row = db.execute(
            "SELECT convert_from(raw,'UTF8')::json->'cells' AS cells, "
            "encode(sha256(raw),'hex')=sha256 AS verified "
            "FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, f"combat-maps/{map_id}.json"),
        ).fetchone()
        if row is not None and not row["verified"]:
            raise ValueError("Native travel geometry checksum mismatch")
        columns = {}
        if row is not None:
            for x, y, z in row["cells"] or []:
                column = (x, y)
                if column not in columns:
                    columns[column] = z
                elif columns[column] != z:
                    columns[column] = None
        _GEOMETRY_INDEXES[cache_key] = columns
        while (
            len(_GEOMETRY_INDEXES) > _GEOMETRY_LIMIT
            or sum(len(index) for index in _GEOMETRY_INDEXES.values())
            > _GEOMETRY_COLUMN_LIMIT
        ):
            _GEOMETRY_INDEXES.popitem(last=False)
        return columns


def _target(db, revision, map_id, x, y, z, *, nearby=False):
    coordinates = _coordinates(map_id, x, y, z)
    if coordinates is None:
        return None
    cache_key = (revision, *coordinates, bool(nearby))
    with _CACHE_LOCK:
        if cache_key in _TARGETS:
            _TARGETS.move_to_end(cache_key)
            target = _TARGETS[cache_key]
            return None if target is None else dict(target)
    map_id, x, y, z = coordinates
    columns = _geometry_index(db, revision, map_id)
    selected = None
    if columns.get((x, y)) == z:
        selected = (x, y, z)
    elif nearby:
        candidates = []
        for dx in range(-4, 5):
            for dy in range(-4 + abs(dx), 5 - abs(dx)):
                height = columns.get((x + dx, y + dy))
                if height is not None and abs(height - z) <= 1:
                    candidates.append((x + dx, y + dy, height))
        if candidates:
            selected = min(
                candidates,
                key=lambda cell: (
                    abs(cell[0] - x) + abs(cell[1] - y),
                    abs(cell[2] - z),
                    *cell,
                ),
            )
    target = (
        None
        if selected is None
        else dict(
            map_id=map_id, instance_id=0, x=selected[0], y=selected[1], z=selected[2]
        )
    )
    with _CACHE_LOCK:
        _TARGETS[cache_key] = target
        while len(_TARGETS) > _TARGET_LIMIT:
            _TARGETS.popitem(last=False)
    return None if target is None else dict(target)


def _eligible(db, identity):
    actor = db.execute(
        "SELECT level FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (identity["character_id"], identity["account_id"]),
    ).fetchone()
    if actor is None:
        raise ValueError("Character unavailable")
    completed = {
        row["definition_key"]
        for row in db.execute(
            "SELECT definition_key FROM objectives_account_progress WHERE account_id=%s AND completed_at IS NOT NULL",
            (identity["account_id"],),
        ).fetchall()
    }
    now = datetime.now(timezone.utc)
    result = {}
    for row in db.execute(
        "SELECT key,definition FROM objectives_definitions ORDER BY key"
    ).fetchall():
        rule = row["definition"]
        band = rule.get("level_range", {"minimum": 1, "maximum": MAX_CHARACTER_LEVEL})
        if (
            rule["enabled"]
            and band["minimum"] <= actor["level"] <= band["maximum"]
            and all(key in completed for key in rule.get("prerequisite_keys", []))
            and period_key(rule["schedule"], now) is not None
        ):
            result[row["key"]] = rule
    return result


def _entrance_target(db, revision, source):
    """Prefer native interaction cells: object height need not equal floor height."""
    for point in source.get("approach_positions", []):
        coordinates = _coordinates(
            source["map_id"], point.get("x"), point.get("y"), point.get("z")
        )
        if coordinates is None:
            continue
        target = _target(db, revision, *coordinates)
        if target is not None:
            return target
    return _target(
        db,
        revision,
        source["map_id"],
        source["x"],
        source["y"],
        source["z"],
        nearby=True,
    )


def actions(db, identity, action_key=None):
    """Resolve authored dungeon entrances independently of public transport stops."""
    requested_dungeon = None
    if action_key is not None:
        match = re.fullmatch(r"travel\.dungeon\.([1-9][0-9]*)", action_key)
        if match is None:
            return []
        requested_dungeon = int(match[1])
    configured = db.execute(
        "SELECT value FROM settings WHERE name='objectives_travel_cost_kamas'"
    ).fetchone()
    cost_kamas = configured["value"] if configured else 500
    if type(cost_kamas) is not int or not 1 <= cost_kamas <= 2147483647:
        raise ValueError("Invalid objective travel cost")
    rules = _eligible(db, identity)
    routes = db.execute(
        "SELECT c.configuration->'route' AS route FROM dungeon_runtime_configurations c "
        "JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version) ORDER BY c.route_key"
    ).fetchall()
    # A route can start inside another dungeon. Such an entrance is not a public
    # destination and must not create a new instance-zero copy of a private map.
    private_maps = {row["route"]["start_map_id"] for row in routes}
    active = db.execute(
        "SELECT a.revision FROM native_catalog_active a JOIN native_catalog_releases r USING(revision) "
        "WHERE a.id=1 AND r.complete"
    ).fetchone()
    if active is None:
        raise ValueError("Published native travel catalog unavailable")
    revision = active["revision"]
    sources = {
        (row["map_id"], row["id"]): row
        for row in (_document(db, revision, "native-generic-teleporters.json") or [])
    }
    result = []
    for row in sorted(
        routes,
        key=lambda value: (value["route"]["entry_map_id"], value["route"]["key"]),
    ):
        route = row["route"]
        if (
            requested_dungeon is not None
            and route["definition_id"] != requested_dungeon
        ):
            continue
        rule = rules.get(f"content-v1.dungeon.{route['definition_id']}")
        source = sources.get((route["entry_map_id"], route["entry_object_id"]))
        if rule is None or source is None or route["entry_map_id"] in private_maps:
            continue
        if not any(
            destination["destination_id"] == route["destination_id"]
            and destination["map_id"] == route["start_map_id"]
            for destination in source["destinations"]
        ):
            continue
        target = _entrance_target(db, revision, source)
        if target is None:
            continue
        result.append(
            dict(
                action_key=f"travel.dungeon.{route['definition_id']}",
                label="Go to entrance: " + rule["title"],
                description="Travel to a verified public entrance. Native access requirements remain in force.",
                cost_kamas=cost_kamas,
                target=dict(target),
                objective_key=rule["key"],
                source_object=dict(
                    map_id=source["map_id"],
                    object_id=source["id"],
                    x=source["x"],
                    y=source["y"],
                    z=source["z"],
                ),
                provenance=dict(
                    catalog_revision=revision,
                    route_key=route["key"],
                    destination_id=route["destination_id"],
                    floor_policy="native_approach_or_single_height_distance_4_height_1",
                ),
            )
        )
    return list({row["action_key"]: row for row in result}.values())


def resolve(db, identity, action_key):
    if type(action_key) is not str or not action_key.startswith("travel."):
        raise ValueError("Unknown player travel action")
    for action in actions(db, identity, action_key):
        if action["action_key"] == action_key:
            return action
    raise ValueError("Travel action is unavailable or has no verified public arrival")
