"""Local reproduction policy and collision-free creature identity allocation."""
import math
import secrets
from contextlib import nullcontext


def dungeon_population(store, instance_id):
    """Dungeon rosters are authored encounters, never breeding ecosystems.

    Match the durable run regardless of room map or active/completed status.
    Public instance zero needs no database lookup; other private populations
    retain their existing policy unless they actually belong to a dungeon run.
    """
    if instance_id == 0:
        return False
    with store.connection() as db:
        return (
            db.execute(
                "SELECT 1 FROM dungeon_instances WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
            is not None
        )


def policy(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_reproduction'"
        ).fetchone()
    value = None if row is None else row["value"]
    return validate_policy(value)


def validate_policy(value):
    """Validate an explicit per-cycle snapshot without reading settings again."""
    if type(value) is not dict or set(value) != {
        "interval_ms",
        "birth_probability",
        "birth_stage_decay",
        "new_group_probability",
        "max_members",
        "max_zone_members",
        "max_zone_groups",
    }:
        raise ValueError("Invalid monster reproduction policy")
    if (
        type(value["interval_ms"]) is not int
        or not 1000 <= value["interval_ms"] <= 86400000
    ):
        raise ValueError("Invalid monster reproduction interval")
    if type(value["max_members"]) is not int or not 1 <= value["max_members"] <= 8:
        raise ValueError("Invalid monster reproduction roster limit")
    for key in ("max_zone_members", "max_zone_groups"):
        if type(value[key]) is not int or not 1 <= value[key] <= 100000:
            raise ValueError("Invalid monster zone population limit")
    for key in ("birth_probability", "birth_stage_decay", "new_group_probability"):
        number = value[key]
        if (
            type(number) not in (int, float)
            or not 0 <= number <= 1
            or not math.isfinite(number)
        ):
            raise ValueError("Invalid monster reproduction probability")
    return value


def birth_probability(reference, configuration):
    """Explicit local adult-tier decay with native level-gap weighting."""
    from .monster_maturation import STAGES

    stage = STAGES.get(reference)
    if stage is None or stage[1] == 0:
        return 0.0
    family, rank = stage
    tiers = family["tiers"]
    first_adult = tiers[1]["min_level"]
    next_level = tiers[min(rank + 1, len(tiers) - 1)]["min_level"]
    return (
        configuration["birth_probability"]
        * configuration["birth_stage_decay"] ** (rank - 1)
        * first_adult
        / next_level
    )


def allocate_identity(db):
    """Use the caller's transaction; rollback may leave harmless sequence gaps."""
    from .npc_actor_identity import allocate_block

    magnitude = allocate_block(db, 1)
    return magnitude, -magnitude


def attempt(
    store,
    ticket,
    *,
    present,
    indexed,
    players=(),
    excluded_ids=(),
    draw=None,
    group_draw=None,
    choose=secrets.choice,
    configuration=None,
    prepared=None,
):
    """Resolve a due birth atomically; caller holds group and harvest locks.

    `indexed` is the server's native directed walk-edge index. Birth requires
    a free adjacent surface; no invented height, respawn or skipped maturity.
    """
    if type(present) is not bool:
        raise ValueError("Invalid reproduction presence")
    if not present or dungeon_population(store, ticket["instance_id"]):
        return None
    from psycopg.types.json import Jsonb
    from .monster_maturation import STAGES
    from .monsters import owned_instance
    from .combat_monster_world import spawn_group

    configuration = (
        policy(store) if configuration is None else validate_policy(configuration)
    )
    key = (
        ticket["map_id"],
        ticket["instance_id"],
        ticket["monster_id"],
        ticket["cycle"],
    )
    group_key = (*key[:2], ticket["group_id"])
    with store.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("monster-population:" + ":".join(map(str, key[:2])),),
        )
        group = db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s FOR UPDATE",
            group_key,
        ).fetchone()
        old = db.execute(
            "SELECT * FROM monster_reproduction_receipts WHERE map_id=%s "
            "AND instance_id=%s AND monster_id=%s AND cycle=%s",
            key,
        ).fetchone()
        if old is not None:
            if (
                old["parent_group_id"] != ticket["group_id"]
                or old["parent_reference"] != ticket["reference"]
            ):
                raise ValueError("Foreign reproduction cycle")
            return dict(old, duplicate=True)
        if group is None or group["status"] != "available" or key[2] in excluded_ids:
            return None
        if (
            prepared is not None
            and list(group["members"]) != prepared["expected_members"]
        ):
            return None
        parent = next((m for m in group["members"] if m["id"] == key[2]), None)
        stage = STAGES.get(ticket["reference"])
        if (
            parent is None
            or parent["ref"] != ticket["reference"]
            or stage is None
            or stage[1] == 0
        ):
            return None
        timer = db.execute(
            "SELECT * FROM monster_reproduction_timers WHERE map_id=%s "
            "AND instance_id=%s AND monster_id=%s FOR UPDATE",
            key[:3],
        ).fetchone()
        if (
            timer is None
            or not timer["due"]
            or timer["cycle"] != key[3]
            or timer["reference"] != parent["ref"]
        ):
            return None
        if prepared is None:
            living_groups = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND status!='defeated'",
                key[:2],
            ).fetchall()
            population = sum(len(row["members"]) for row in living_groups)
            group_count = len(living_groups)
        else:
            counts = db.execute(
                "SELECT count(*) AS groups,COALESCE(sum(jsonb_array_length(members)),0) AS members "
                "FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
                key[:2],
            ).fetchone()
            population, group_count = counts["members"], counts["groups"]
            destination = tuple(prepared["destination"])
            if db.execute(
                "SELECT 1 FROM combat_groups g CROSS JOIN LATERAL jsonb_array_elements(g.members) m "
                "WHERE g.map_id=%s AND g.instance_id=%s AND g.status!='defeated' "
                "AND (m->>'x')::integer=%s AND (m->>'y')::integer=%s LIMIT 1",
                (*key[:2], *destination[:2]),
            ).fetchone():
                return None
        if population >= configuration["max_zone_members"]:
            return None
        can_append = len(group["members"]) < configuration["max_members"]
        can_separate = group_count < configuration["max_zone_groups"]
        if not can_append and not can_separate:
            return None
        blocked = {
            (p["x"], p["y"])
            for p in players
            if (p["map_id"], p["instance_id"]) == key[:2]
        }
        if prepared is None:
            for row in living_groups:
                blocked.update((m["x"], m["y"]) for m in row["members"])
            blocked.update(
                (r["x"], r["y"])
                for r in db.execute(
                    "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s",
                    key[:2],
                )
            )
        if prepared is None:
            candidates = [
                p
                for p in indexed[1].get(tuple(parent[k] for k in ("x", "y", "z")), ())
                if p[:2] not in blocked
            ]
            if not candidates:
                return None
            destination = choose(candidates)
        else:
            destination = tuple(prepared["destination"])
            if destination[:2] in blocked:
                return None
        cell = (*key[:2], *destination[:2])
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("planting-cell:" + ":".join(map(str, cell)),),
        )
        if db.execute(
            "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s "
            "AND x=%s AND y=%s",
            cell,
        ).fetchone():
            return None
        sample = secrets.randbelow(1 << 53) / (1 << 53) if draw is None else draw
        if (
            type(sample) not in (int, float)
            or not 0 <= sample < 1
            or not math.isfinite(sample)
        ):
            raise ValueError("Invalid reproduction draw")
        child_id = child_group = child = None
        probability = birth_probability(parent["ref"], configuration)
        if sample < probability:
            second = (
                secrets.randbelow(1 << 53) / (1 << 53)
                if group_draw is None
                else group_draw
            )
            if (
                type(second) not in (int, float)
                or not 0 <= second < 1
                or not math.isfinite(second)
            ):
                raise ValueError("Invalid reproduction group draw")
            separate = can_separate and (
                not can_append or second < configuration["new_group_probability"]
            )
            if prepared is None:
                magnitude, child_id = allocate_identity(db)
                seed = choose(stage[0]["tiers"][0]["candidates"])
                child = owned_instance(
                    seed["reference"],
                    seed["min_level"],
                    child_id,
                    map_id=key[0],
                    x=destination[0],
                    y=destination[1],
                    z=destination[2],
                    team=parent["team"],
                    instance_id=key[1],
                )
            else:
                child = prepared["child"]
                magnitude, child_id = -child["id"], child["id"]
                if tuple(child[k] for k in ("x", "y", "z")) != destination:
                    raise ValueError("Prepared birth position differs")
            child_group = magnitude if separate else ticket["group_id"]
            members = [child] if separate else [*group["members"], child]
            spawn_group(members, group_id=child_group)
            if separate:
                revision = db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                    "VALUES(%s,%s,%s,%s,'available') RETURNING revision",
                    (*key[:2], child_group, Jsonb(members)),
                ).fetchone()["revision"]
            else:
                revision = db.execute(
                    "UPDATE combat_groups SET members=%s,revision=revision+1 "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s RETURNING revision",
                    (Jsonb(members), *group_key),
                ).fetchone()["revision"]
            db.execute(
                "INSERT INTO combat_group_members(map_id,instance_id,monster_id,group_id) "
                "VALUES(%s,%s,%s,%s)",
                (*key[:2], child_id, child_group),
            )
        receipt = db.execute(
            "INSERT INTO monster_reproduction_receipts(map_id,instance_id,monster_id,cycle,"
            "parent_group_id,parent_reference,child_id,child_group_id,child,draw,probability,policy) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                *key,
                ticket["group_id"],
                parent["ref"],
                child_id,
                child_group,
                Jsonb(child) if child is not None else None,
                sample,
                probability,
                Jsonb(configuration),
            ),
        ).fetchone()
        if child_id is not None:
            db.execute(
                "INSERT INTO monster_reproduction_outbox(map_id,instance_id,monster_id,cycle,"
                "group_id,revision,new_group) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (*key, child_group, revision, separate),
            )
        db.execute(
            "UPDATE monster_reproduction_timers SET remaining_ms=%s,last_active_ms=NULL,due=false "
            "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
            (configuration["interval_ms"], *key[:3]),
        )
        return dict(receipt, duplicate=False)


def observe(
    store,
    map_id,
    instance_id,
    *,
    present,
    generation,
    now_ms,
    excluded_ids=(),
    configuration=None,
):
    from .monster_active_clocks import observe as observe_clocks
    from .monster_maturation import STAGES

    if dungeon_population(store, instance_id):
        return []
    adults = {reference for reference, (_, rank) in STAGES.items() if rank > 0}
    return observe_clocks(
        store,
        map_id,
        instance_id,
        present=present,
        generation=generation,
        now_ms=now_ms,
        excluded_ids=excluded_ids,
        table="monster_reproduction_timers",
        eligible_refs=adults,
        policy_provider=policy
        if configuration is None
        else lambda _: validate_policy(configuration),
    )


def pending(store, map_id, instance_id):
    if dungeon_population(store, instance_id):
        return []
    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT t.map_id,t.instance_id,t.monster_id,t.reference,t.cycle,m.group_id "
                "FROM monster_reproduction_timers t JOIN combat_group_members m "
                "USING(map_id,instance_id,monster_id) WHERE t.map_id=%s AND t.instance_id=%s "
                "AND t.due ORDER BY t.monster_id",
                (map_id, instance_id),
            )
        ]


def unpublished(store, map_id, instance_id, *, group_id=None):
    if dungeon_population(store, instance_id):
        return []
    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT o.*,g.members,g.status,g.revision AS current_revision "
                "FROM monster_reproduction_outbox o JOIN combat_groups g "
                "USING(map_id,instance_id,group_id) WHERE o.map_id=%s AND o.instance_id=%s "
                "AND NOT o.published "
                + ("AND o.group_id=%s " if group_id is not None else "")
                + "ORDER BY o.group_id,o.revision,o.monster_id,o.cycle",
                (map_id, instance_id)
                if group_id is None
                else (map_id, instance_id, group_id),
            )
        ]


def acknowledge(store, event):
    with store.connection() as db:
        return (
            db.execute(
                "UPDATE monster_reproduction_outbox o SET published=true FROM combat_groups g "
                "WHERE o.map_id=%s AND o.instance_id=%s AND o.monster_id=%s AND o.cycle=%s "
                "AND o.group_id=%s AND o.revision=%s AND g.map_id=o.map_id "
                "AND g.instance_id=o.instance_id AND g.group_id=o.group_id "
                "AND g.revision=%s AND g.status='available' AND NOT o.published RETURNING o.cycle",
                (
                    event["map_id"],
                    event["instance_id"],
                    event["monster_id"],
                    event["cycle"],
                    event["group_id"],
                    event["revision"],
                    event["current_revision"],
                ),
            ).fetchone()
            is not None
        )


def tick(
    store,
    locations,
    previous_locations,
    *,
    generation,
    now_ms,
    indexed_by_map,
    players,
    excluded_ids,
    emit,
    coordination=None,
):
    """One non-catch-up cycle with a fresh fence for each authoritative operation.

    A coordinator yields current (players, excluded harvest identities) while
    holding the caller's group/harvest fences. Without one, the caller retains
    the historical responsibility to hold those fences around this function.
    Enumeration is advisory; attempts and publication revalidate under a fence.
    """
    from .combat_monster_world import remove_message, spawn_group

    def guarded(stage, map_id, instance_id):
        if coordination is None:
            return nullcontext((players, excluded_ids))
        return coordination(stage, map_id, instance_id)

    def present_here(current_players, map_id, instance_id):
        return coordination is None or any(
            p.get("map_id") == map_id and p.get("instance_id", 0) == instance_id
            for p in current_players
        )

    locations = {
        location for location in locations if not dungeon_population(store, location[1])
    }
    previous_locations = {
        location
        for location in previous_locations
        if not dungeon_population(store, location[1])
    }
    # Live settings remain dynamic: reload once on each tick, outside registry
    # fences, rather than reopening a settings transaction for every parent.
    configuration = policy(store) if locations else None
    for map_id, instance_id in previous_locations - locations:
        with guarded("absent", map_id, instance_id):
            observe(
                store,
                map_id,
                instance_id,
                present=False,
                generation=generation,
                now_ms=now_ms,
            )
    for map_id, instance_id in sorted(locations):
        with guarded("observe", map_id, instance_id) as (
            current_players,
            current_excluded,
        ):
            observe(
                store,
                map_id,
                instance_id,
                present=present_here(current_players, map_id, instance_id),
                generation=generation,
                now_ms=now_ms,
                excluded_ids=current_excluded,
                configuration=configuration,
            )
        for ticket in pending(store, map_id, instance_id):
            with guarded("attempt", map_id, instance_id) as (
                current_players,
                current_excluded,
            ):
                attempt(
                    store,
                    ticket,
                    present=present_here(current_players, map_id, instance_id),
                    indexed=indexed_by_map[map_id],
                    players=current_players,
                    excluded_ids=current_excluded,
                    configuration=configuration,
                )
        group_ids = dict.fromkeys(
            event["group_id"] for event in unpublished(store, map_id, instance_id)
        )
        for group_id in group_ids:
            with guarded("publish", map_id, instance_id) as (_, current_excluded):
                # Claims, defeats and harvest occupations can change between
                # enumeration and fence acquisition. Never publish that old row.
                batch = [
                    event
                    for event in unpublished(
                        store, map_id, instance_id, group_id=group_id
                    )
                ]
                if not batch:
                    continue
                current = batch[-1]
                if current["status"] != "available" or any(
                    m["id"] in current_excluded for m in current["members"]
                ):
                    continue
                spawn = spawn_group(current["members"], group_id=group_id)
                # Preserve removal, replacement and acknowledgment as one
                # fenced operation through the current authoritative revision.
                emit(
                    map_id,
                    instance_id,
                    *remove_message([m["id"] for m in current["members"]]),
                )
                emit(map_id, instance_id, 12608, spawn)
                for event in batch:
                    acknowledge(store, event)
    return locations


def expanded_seeds(store, key, seeds, persisted):
    """Authorize appended seed-group members only by durable birth snapshots."""
    from .monster_maturation import STAGES
    from .monsters import owned_instance
    from .npc_actor_identity_repair import actor_aliases, aliased_members

    with store.connection() as db:
        aliases = actor_aliases(db, key)
    seeds = aliased_members(seeds, aliases)

    if [m["id"] for m in persisted[: len(seeds)]] != [m["id"] for m in seeds]:
        raise ValueError("Conflicting existing group seed roster")
    extras = persisted[len(seeds) :]
    if not extras:
        return list(seeds)
    with store.connection() as db:
        historical_ids = {
            old
            for old, new in aliases.items()
            if new in {member["id"] for member in extras}
        }
        births = {
            aliases.get(row["child_id"], row["child_id"]): dict(
                row,
                child=None
                if row["child"] is None
                else aliased_members([row["child"]], aliases)[0],
            )
            for row in db.execute(
                "SELECT child_id,child,parent_reference FROM monster_reproduction_receipts "
                "WHERE map_id=%s AND instance_id=%s AND child_group_id=%s "
                "AND child_id=ANY(%s)",
                (*key, [m["id"] for m in extras] + sorted(historical_ids)),
            )
        }
    expanded = list(seeds)
    for member in extras:
        birth = births.get(member["id"])
        if (
            birth is None
            or birth["child"] is None
            or birth["child"]["id"] != member["id"]
        ):
            raise ValueError("Seed group contains an unreceipted offspring")
        child = birth["child"]
        parent_stage = STAGES.get(birth["parent_reference"])
        candidate = (
            next(
                (
                    row
                    for row in parent_stage[0]["tiers"][0]["candidates"]
                    if row["reference"] == child["ref"]
                ),
                None,
            )
            if parent_stage is not None
            else None
        )
        if candidate is None or child["map_id"] != key[0]:
            raise ValueError("Invalid offspring birth reference")
        native = owned_instance(
            child["ref"],
            candidate["min_level"],
            child["id"],
            map_id=key[0],
            x=child["x"],
            y=child["y"],
            z=child["z"],
            team=child["team"],
            instance_id=key[1],
        )
        if native != child:
            raise ValueError("Invalid offspring birth snapshot")
        expanded.append(native)
    return expanded
