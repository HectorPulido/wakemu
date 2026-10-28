"""Administrative population controls; no rewards, affinity or combat decisions."""
from collections import Counter
import time
from psycopg.errors import DeadlockDetected, LockNotAvailable, SerializationFailure
from psycopg.types.json import Jsonb

from .monster_initial_population import REGIONS
from .territory_cells import region_at
from .monsters import reference, owned_instance
from .planting import RESOURCES, SEEDS, decode

COMMANDS = frozenset(("!nuke", "!nuke-all", "!genesis", "!genesis-all", "!eco-status"))


_SCOPE_TRANSIENT_ERRORS = (LockNotAvailable, DeadlockDetected, SerializationFailure)
_SCOPE_ATTEMPTS = 8


def _retry_wait(delay):
    time.sleep(delay)


def locate(map_id, x, y, z):
    return {"region_id": region_at(map_id, x, y)}


def current_available(store, key):
    """Read the post-settlement roster, including deferred administrative removal."""
    with store.connection() as db:
        row = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            key,
        ).fetchone()
    return tuple(row["members"]) if row and row["status"] == "available" else ()


def admin_removed_packets(db, map_id, instance_id):
    """Idempotent scene cleanup for removed actors, including partial groups."""
    from .combat_monster_world import remove_message

    ids = set()
    for row in db.execute(
        "SELECT ecology_admin_removed_ids FROM combat_groups WHERE map_id=%s AND instance_id=%s",
        (map_id, instance_id),
    ):
        ids.update(row["ecology_admin_removed_ids"])
    ordered = sorted(ids)
    return [
        remove_message(tuple(ordered[offset : offset + 255]))
        for offset in range(0, len(ordered), 255)
    ]


def _inside(map_id, member, region_id):
    return region_id is None or region_at(map_id, member["x"], member["y"]) == region_id


def _authorize(db, character):
    row = db.execute(
        "SELECT a.is_admin FROM characters c JOIN accounts a ON a.id=c.account_id WHERE c.id=%s AND c.account_id=%s",
        (character["id"], character["account_id"]),
    ).fetchone()
    if row is None or row["is_admin"] is not True:
        raise ValueError("Ecology commands require an administrator account")


def _scopes(db, character, global_scope, *, genesis=False):
    if not global_scope:
        map_id, instance_id = character["map_id"], character.get("instance_id", 0)
        if instance_id != 0:
            raise ValueError(
                "Ecology administration is restricted to the public outdoor world"
            )
        region_id = region_at(map_id, character["x"], character["y"])
        if (map_id, region_id) not in REGIONS:
            raise ValueError("No native ecology region at this location")
        if genesis and REGIONS[map_id, region_id].get("monster_capacity", 0) <= 0:
            from .ecology_admin_errors import EcologyAdminFailure

            raise EcologyAdminFailure("no_monster_habitat")
        return [(map_id, instance_id, region_id)]
    if genesis:
        return [
            (m, 0, r)
            for (m, r), row in sorted(REGIONS.items())
            if row.get("monster_capacity", 0) > 0
        ]
    maps = {
        row["map_id"]
        for row in db.execute(
            "SELECT DISTINCT map_id FROM combat_groups WHERE instance_id=0 UNION SELECT DISTINCT map_id FROM planted_resources WHERE instance_id=0"
        )
    }
    maps.update(m for m, _ in REGIONS)
    # Only maps with native ecology are outdoor habitats. Special encounters on
    # other maps and every private/dungeon instance retain their own lifecycle.
    outdoor = {m for m, _ in REGIONS}
    return [(m, 0, None) for m in sorted(maps & outdoor)]


def _fence_initial(db, map_id, instance_id, region_id):
    regions = (
        [region_id] if region_id is not None else [r for m, r in REGIONS if m == map_id]
    )
    for region in regions:
        db.execute(
            "INSERT INTO monster_initial_population(map_id,instance_id,region_id,policy_version,group_id,initial_members) VALUES(%s,%s,%s,1,1,'[]'::jsonb) ON CONFLICT DO NOTHING",
            (map_id, instance_id, region),
        )
        db.execute(
            "UPDATE monster_initial_population_publication SET published_at=CURRENT_TIMESTAMP WHERE map_id=%s AND instance_id=%s AND region_id=%s",
            (map_id, instance_id, region),
        )


def _nuke(db, map_id, instance_id, region_id):
    from .combat_monster_world import remove_message, spawn_group
    from .planting_runtime import state_packet

    packets, removed, deferred, cancelled = [], 0, 0, 0
    cancelled_characters = set()
    removed_groups = []
    rows = list(
        db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated' ORDER BY group_id FOR UPDATE",
            (map_id, instance_id),
        )
    )
    for row in rows:
        selected = [m for m in row["members"] if _inside(map_id, m, region_id)]
        if not selected:
            continue
        ids = {m["id"] for m in selected}
        pending = set(row["ecology_admin_removed_ids"]) | ids
        key = (map_id, instance_id, row["group_id"])
        removed_groups.append(
            dict(key=key, actor_ids=sorted(ids), deferred=row["status"] == "fighting")
        )
        # Keeping the lease revision while fighting is essential: terminal
        # settlement must still recognize the original fight's authority.
        db.execute(
            "UPDATE combat_groups SET ecology_admin_removed_ids=%s,revision=revision+CASE WHEN status='fighting' THEN 0 ELSE 1 END WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            (Jsonb(sorted(pending)), *key),
        )
        if row["status"] == "fighting":
            deferred += len(ids - set(row["ecology_admin_removed_ids"]))
        else:
            removed += len(ids)
            packets.append(remove_message(tuple(m["id"] for m in row["members"])))
            remaining = [m for m in row["members"] if m["id"] not in pending]
            if remaining:
                packets.append(
                    (12608, spawn_group(remaining, group_id=row["group_id"]))
                )
        full_group = len(ids) == len(row["members"])
        db.execute(
            "UPDATE monster_maturation_outbox SET published=TRUE WHERE map_id=%s AND instance_id=%s AND group_id=%s AND (%s OR monster_id=ANY(%s))",
            (*key, full_group, list(ids)),
        )
        # Birth publication is keyed by the parent, even when the affected actor
        # is a child in a different group. Match both identities explicitly.
        db.execute(
            "UPDATE monster_reproduction_outbox o SET published=TRUE FROM monster_reproduction_receipts r WHERE o.map_id=r.map_id AND o.instance_id=r.instance_id AND o.monster_id=r.monster_id AND o.cycle=r.cycle AND o.map_id=%s AND o.instance_id=%s AND o.group_id=%s AND (%s OR o.monster_id=ANY(%s) OR r.child_id=ANY(%s))",
            (*key, full_group, list(ids), list(ids)),
        )
        # Deleted timers fence already-prepared maturation/reproduction tickets.
        for table in ("monster_maturation_timers", "monster_reproduction_timers"):
            db.execute(
                f"DELETE FROM {table} WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s)",
                (map_id, instance_id, list(ids)),
            )
    for resource in db.execute(
        "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid FOR UPDATE",
        (map_id, instance_id),
    ):
        if RESOURCES[resource["resource_reference"]]["monster_resource"] and _inside(
            map_id, resource, region_id
        ):
            packets.append(state_packet(resource, 0))
            db.execute(
                "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=%s",
                (resource["resource_uid"],),
            )
            db.execute(
                "UPDATE planting_receipts SET published=TRUE WHERE resource_uid=%s",
                (resource["resource_uid"],),
            )
            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s",
                (resource["resource_uid"],),
            )
            cancelled += 1
    # Prepared births can already have removed their original seed resource.
    for row in db.execute(
        "SELECT resource_uid,resource FROM planting_growth_outbox WHERE NOT published AND (resource->>'map_id')::integer=%s AND (resource->>'instance_id')::bigint=%s AND group_payload IS NOT NULL FOR UPDATE",
        (map_id, instance_id),
    ):
        if _inside(map_id, row["resource"], region_id):
            db.execute(
                "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=%s",
                (row["resource_uid"],),
            )
            packets.append(state_packet(row["resource"], 0))
            cancelled += 1
    for row in db.execute(
        "SELECT operation_id,resource FROM planting_receipts WHERE NOT published AND group_payload IS NOT NULL AND (resource->>'map_id')::integer=%s AND coalesce((resource->>'instance_id')::bigint,0)=%s FOR UPDATE",
        (map_id, instance_id),
    ):
        if _inside(map_id, row["resource"], region_id):
            db.execute(
                "UPDATE planting_receipts SET published=TRUE WHERE operation_id=%s",
                (row["operation_id"],),
            )
    for row in db.execute(
        "SELECT id,character_id,body,actor_location FROM ecology_planting_intents WHERE status='pending' AND (actor_location->>'map_id')::integer=%s AND coalesce((actor_location->>'instance_id')::bigint,0)=%s FOR UPDATE",
        (map_id, instance_id),
    ):
        try:
            request = decode(bytes(row["body"]))
            seed = next(
                (
                    seed
                    for seed in SEEDS.values()
                    if seed["action_id"] == request["action_id"]
                ),
                None,
            )
            monster_seed = (
                seed is not None
                and RESOURCES[seed["resource_reference"]]["monster_resource"]
            )
        except (ValueError, KeyError):
            monster_seed = False
        if monster_seed and _inside(map_id, request, region_id):
            db.execute(
                "UPDATE ecology_planting_intents SET status='cancelled' WHERE id=%s",
                (row["id"],),
            )
            cancelled_characters.add(row["character_id"])
    _fence_initial(db, map_id, instance_id, region_id)
    return dict(
        removed=removed,
        deferred=deferred,
        cancelled=cancelled,
        packets=packets,
        cancelled_characters=sorted(cancelled_characters),
        removed_groups=removed_groups,
    )


def _status(db, map_id, instance_id, region_id):
    from .ecology_policy import decision

    counts, forms, statuses = Counter(), Counter(), Counter()
    groups = 0
    for row in db.execute(
        "SELECT members,status,ecology_admin_removed_ids FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
        (map_id, instance_id),
    ):
        members = [m for m in row["members"] if _inside(map_id, m, region_id)]
        if members:
            groups += 1
        for member in members:
            counts[reference(member["ref"])["family_id"]] += 1
            forms[member["ref"]] += 1
            statuses[row["status"]] += 1
            if member["id"] in row["ecology_admin_removed_ids"]:
                statuses["pending_removal"] += 1
    habitat = REGIONS[map_id, region_id]
    lines = [
        f'Ecology map={map_id} instance={instance_id} region={region_id}: {sum(counts.values())} monsters, {groups} groups; capacity={habitat.get("monster_capacity", 0)}, free={max(0,habitat.get("monster_capacity", 0)-sum(counts.values()))}; available={statuses["available"]}, fighting={statuses["fighting"]}, pending removal={statuses["pending_removal"]}.'
    ]
    from .monster_reproduction import validate_policy

    reproduction = validate_policy(
        db.execute(
            "SELECT value FROM settings WHERE name='monster_reproduction'"
        ).fetchone()["value"]
    )
    genesis_row = db.execute(
        "SELECT value FROM settings WHERE name='monster_genesis'"
    ).fetchone()
    genesis = validate_genesis_policy(
        None if genesis_row is None else genesis_row["value"]
    )
    map_groups = list(
        db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
            (map_id, instance_id),
        )
    )
    lines.append(
        f'Map population: {sum(len(row["members"]) for row in map_groups)}/{reproduction["max_zone_members"]} monsters, {len(map_groups)}/{reproduction["max_zone_groups"]} groups; genesis target={genesis["groups_per_region"]} groups per region, random group size={genesis["min_members"]}..{genesis["max_members"]}.'
    )
    for family in sorted(
        set(counts) | {f["family_id"] for f in habitat["monster_families"]}
    ):
        n = counts[family]
        evidence = decision(
            db,
            map_id=map_id,
            region_id=region_id,
            kind="monster",
            family_id=family,
            action="harvest",
            before=n,
        )["evidence"]
        low, high = evidence["minimum"], evidence["maximum"]
        lines.append(
            f'Family {family}: {n}; equilibrium={low}..{high}; deficit={max(0,low-n)}; excess={max(0,n-high)}; source={evidence["limit_source"]}.'
        )
    for ref, n in sorted(forms.items()):
        monster = reference(ref)
        lines.append(
            f'Ref {ref} ({monster.get("name", ref)}), family {monster["family_id"]}: {n}.'
        )
    return "\n".join(lines)


def validate_genesis_policy(value):
    """Validate the explicit administrative group policy independently of seeds."""
    if type(value) is not dict or set(value) != {
        "groups_per_region",
        "min_members",
        "max_members",
    }:
        raise ValueError("Invalid administrative monster genesis policy")
    if (
        type(value["groups_per_region"]) is not int
        or not 1 <= value["groups_per_region"] <= 100000
    ):
        raise ValueError("Invalid administrative monster group target")
    minimum, maximum = value["min_members"], value["max_members"]
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or not 2 <= minimum <= maximum <= 8
    ):
        raise ValueError("Invalid administrative monster group size")
    return value


def _genesis(db, groups, map_id, instance_id, region_id, *, players=(), prepared=None):
    from .ecology_admin_planner import plan_groups
    from .npc_actor_identity import allocate_block
    from .combat_monster_world import spawn_group
    from .monster_reproduction import validate_policy

    habitat = REGIONS[map_id, region_id]
    warnings = []
    if prepared is not None:
        supported = set(prepared["candidates"])
        if not supported:
            raise ValueError(
                "No supported ordinary native monster references for this habitat"
            )
        missing = {row["family_id"] for row in habitat["monster_families"]} - supported
        if missing:
            warnings.append(
                f"Map {map_id}, region {region_id}: unsupported native monster families {sorted(missing)} were not populated."
            )
    row = db.execute(
        "SELECT value FROM settings WHERE name='monster_genesis'"
    ).fetchone()
    genesis = validate_genesis_policy(None if row is None else row["value"])
    config = validate_policy(
        db.execute(
            "SELECT value FROM settings WHERE name='monster_reproduction'"
        ).fetchone()["value"]
    )
    max_members = min(genesis["max_members"], config["max_members"])
    if max_members < genesis["min_members"]:
        raise ValueError(
            "Administrative group minimum exceeds reproduction roster capacity"
        )
    from .monster_population_capacity import snapshot, physical_cells

    capacity = snapshot(db, map_id, instance_id)
    rows = capacity["groups"]
    occupied, counts, regional_groups = (
        set(physical_cells(db, map_id, instance_id)),
        Counter(),
        [],
    )
    for row in rows + capacity["reservations"]:
        regional_members = []
        for member in row["members"]:
            occupied.add(tuple(member[k] for k in ("x", "y", "z")))
            if _inside(map_id, member, region_id):
                counts[reference(member["ref"])["family_id"]] += 1
                regional_members.append(member)
        if regional_members:
            regional_groups.append(regional_members)
    occupied.update(
        tuple(row[k] for k in ("x", "y", "z"))
        for row in db.execute(
            "SELECT x,y,z FROM planted_resources WHERE map_id=%s AND instance_id=%s",
            (map_id, instance_id),
        )
    )
    occupied.update(
        (player["x"], player["y"], player["z"])
        for player in players
        if player.get("map_id") == map_id
        and player.get("instance_id", 0) == instance_id
    )
    member_budget = max(0, config["max_zone_members"] - capacity["members"])
    group_budget = max(0, config["max_zone_groups"] - capacity["group_count"])
    group_counts = Counter(
        reference(roster[0]["ref"])["family_id"] for roster in regional_groups
    )
    planned = plan_groups(
        map_id,
        region_id,
        counts,
        occupied,
        group_counts=group_counts,
        target_groups=genesis["groups_per_region"],
        min_members=genesis["min_members"],
        max_members=max_members,
        capacity=habitat["monster_capacity"],
        max_groups=group_budget,
        member_budget=member_budget,
        prepared=prepared,
    )
    packets, added, created_groups = [], 0, []
    for chunk in planned:
        members = [
            owned_instance(
                row["reference"],
                row["level"],
                -allocate_block(db, 1),
                map_id=map_id,
                instance_id=instance_id,
                **{k: row[k] for k in ("x", "y", "z")},
            )
            for row in chunk
        ]
        key = groups.register_transaction(
            db, map_id, instance_id, -members[0]["id"], members
        )
        packets.append((12608, spawn_group(members, group_id=key[2])))
        created_groups.append(
            dict(
                key=key,
                actor_ids=[member["id"] for member in members],
                references=[member["ref"] for member in members],
                size=len(members),
            )
        )
        added += len(members)
    target = genesis["groups_per_region"]
    if len(regional_groups) + len(planned) < target:
        warnings.append(
            f"Map {map_id}, region {region_id}: {len(regional_groups) + len(planned)}/{target} groups; native capacity, free terrain or map population budgets prevent completing genesis."
        )
    _fence_initial(db, map_id, instance_id, region_id)
    return dict(
        added=added, packets=packets, created_groups=created_groups, warnings=warnings
    )


def _empty_result():
    return dict(
        location_packets=[],
        removed=0,
        deferred=0,
        cancelled=0,
        added=0,
        scopes=[],
        failures=[],
        cancelled_characters=[],
        created_groups=[],
        removed_groups=[],
        operation_ids=[],
        publication_failures=[],
        warnings=[],
    )


def execute(
    store,
    groups,
    character,
    command,
    *,
    players=(),
    coordination=None,
    publish=None,
    prepare_scope=None,
    validate_actor=None,
    job=None,
):
    """Commit one bounded habitat at a time, then publish inside its fence.

    Geometry preparation happens before live-world locks. A global command
    preserves completed scopes if a later scope is unavailable or delivery fails.
    """
    if command not in COMMANDS:
        raise ValueError("Unknown ecology administrator command")
    if store is None or groups is None:
        raise ValueError("Persistent ecology administration is unavailable")
    global_scope = command.endswith("-all")
    genesis = command.startswith("!genesis")
    from wakfu_server.ecology_admin_jobs import EcologyAdminCancelled

    with store.connection() as db:
        if validate_actor is not None:
            db.execute("SET LOCAL lock_timeout='250ms'")
            db.execute("SET LOCAL statement_timeout='3000ms'")
        _authorize(db, character)
        if validate_actor is not None:
            validate_actor(db, job)
        scopes = _scopes(db, character, global_scope, genesis=genesis)
    result = _empty_result()
    for scope in scopes:
        try:
            prepared = None
            if genesis:
                from .ecology_admin_planner import prepare

                prepared = (
                    prepare(scope[0], scope[2])
                    if prepare_scope is None
                    else prepare_scope("monsters", scope[0], scope[2])
                )
            for attempt in range(_SCOPE_ATTEMPTS):
                committed = False
                try:
                    window = (
                        coordination(scope) if coordination is not None else groups.lock
                    )
                    with window:
                        scope_result = _empty_result()
                        with store.connection() as db, db.transaction():
                            if validate_actor is not None:
                                db.execute("SET LOCAL lock_timeout='250ms'")
                                db.execute("SET LOCAL statement_timeout='3000ms'")
                            _authorize(db, character)
                            if validate_actor is not None:
                                validate_actor(db, job)
                            db.execute(
                                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                                (f"monster-population:{scope[0]}:{scope[1]}",),
                            )
                            if command == "!eco-status":
                                result["message"] = _status(db, *scope)
                                result["scopes"] = [scope]
                                return result
                            current_players = (
                                players() if callable(players) else players
                            )
                            if isinstance(current_players, dict):
                                current_players = current_players.get("players", ())
                            outcome = (
                                _genesis(
                                    db,
                                    groups,
                                    *scope,
                                    players=current_players,
                                    prepared=prepared,
                                )
                                if genesis
                                else _nuke(db, *scope)
                            )
                            for key in ("removed", "deferred", "cancelled", "added"):
                                scope_result[key] = outcome.get(key, 0)
                            scope_result["location_packets"] = [
                                (*scope[:2], opcode, payload)
                                for opcode, payload in outcome["packets"]
                            ]
                            scope_result["scopes"] = [scope]
                            for key in (
                                "cancelled_characters",
                                "created_groups",
                                "removed_groups",
                                "warnings",
                            ):
                                scope_result[key] = outcome.get(key, [])
                            audit = {
                                key: value
                                for key, value in scope_result.items()
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
                            ).fetchone()
                            scope_result["operation_id"] = operation["id"]
                            scope_result["operation_ids"] = [operation["id"]]
                        committed = True
                        # Aggregate only committed outcomes. Publication is fenced against
                        # a simultaneous reset and occurs after the SQL commit.
                        for key in ("removed", "deferred", "cancelled", "added"):
                            result[key] += scope_result[key]
                        for key in (
                            "location_packets",
                            "scopes",
                            "cancelled_characters",
                            "created_groups",
                            "removed_groups",
                            "operation_ids",
                            "warnings",
                        ):
                            result[key].extend(scope_result[key])
                        result["operation_id"] = scope_result["operation_id"]
                        if publish is not None:
                            try:
                                publish(scope_result)
                            except (OSError, ValueError) as error:
                                result["publication_failures"].append(
                                    (*scope, str(error))
                                )
                    break
                except _SCOPE_TRANSIENT_ERRORS:
                    if committed or attempt + 1 == _SCOPE_ATTEMPTS:
                        raise
                    # Release the transaction and all live-world fences before
                    # waiting. Re-authorize and re-read the scope on each retry.
                    _retry_wait(min(0.05 * (2**attempt), 1.0))
        except EcologyAdminCancelled:
            result["interrupted"] = True
            break
        except _SCOPE_TRANSIENT_ERRORS as error:
            if not global_scope:
                raise
            result["failures"].append(
                (
                    *scope,
                    f"Database contention after {_SCOPE_ATTEMPTS} attempts ({type(error).__name__})",
                )
            )
        except ValueError as error:
            if not global_scope:
                raise
            result["failures"].append((*scope, str(error)))
    result[
        "message"
    ] = f'Ecology: removed={result["removed"]}, deferred until combat ends={result["deferred"]}, cancelled births={result["cancelled"]}, added={result["added"]}; scopes={len(result["scopes"])}, skipped={len(result["failures"])}.'
    if result["failures"]:
        result["message"] += "\n" + "\n".join(
            f"Map {m}, instance {i}, region {r}: {reason}"
            for m, i, r, reason in result["failures"]
        )
    if result["warnings"]:
        result["message"] += "\n" + "\n".join(result["warnings"])
    if result["publication_failures"]:
        result["message"] += (
            "\nCommitted scopes with delivery failures: "
            + str(len(result["publication_failures"]))
            + "; reconnect to refresh the durable scene."
        )
    return result
