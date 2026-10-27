"""Durable once-per-empty-episode plans and atomic position-only outcomes.

Planning performs no World calls. Commit callers hold the World presence fence,
group lock and harvest lock before entering SQL; no callbacks run inside SQL.
"""
from copy import deepcopy
import json
import logging

from psycopg.types.json import Jsonb

MAX_CHUNK_GROUPS = 8
MAX_CHUNK_BYTES = 224 * 1024
LOGGER = logging.getLogger(__name__)


def _episode(epoch, scope, generation):
    if (
        type(epoch) is not str
        or not epoch
        or len(scope) != 2
        or any(type(value) is not int for value in scope)
        or scope[1] != 0
        or type(generation) is not int
        or generation < 0
    ):
        raise ValueError("Invalid idle distribution episode")
    return epoch, *scope, generation


def _validate_move(move, scope):
    expected, moved = move["expected_members"], move["moved_members"]
    if type(move["group_id"]) is not int or not expected or len(expected) != len(moved):
        raise ValueError("Invalid idle distribution group")
    for old, new in zip(expected, moved):
        if {k: v for k, v in old.items() if k not in ("x", "y", "z")} != {
            k: v for k, v in new.items() if k not in ("x", "y", "z")
        }:
            raise ValueError("Idle distribution may only change positions")
        if (old["map_id"], old["instance_id"]) != tuple(scope):
            raise ValueError("Foreign idle distribution member")
        if any(type(new[k]) is not int for k in ("x", "y", "z")):
            raise ValueError("Invalid idle distribution position")


def freeze(store, *, epoch, scope, generation, moves):
    """Persist the complete plan once, including an empty successful plan."""
    episode = _episode(epoch, scope, generation)
    moves = deepcopy(list(moves))
    chunk_index = chunk_size = chunk_count = 0
    rows, seen = [], set()
    for ordinal, move in enumerate(moves):
        _validate_move(move, scope)
        if move["group_id"] in seen:
            raise ValueError("Repeated idle distribution group")
        seen.add(move["group_id"])
        size = len(json.dumps(move, separators=(",", ":")).encode())
        if size > MAX_CHUNK_BYTES:
            rows.append((ordinal, chunk_index, move, "skipped", "group_byte_budget"))
            continue
        if chunk_count and (
            chunk_count == MAX_CHUNK_GROUPS or chunk_size + size > MAX_CHUNK_BYTES
        ):
            chunk_index += 1
            chunk_size = chunk_count = 0
        rows.append((ordinal, chunk_index, move, "pending", None))
        chunk_size += size
        chunk_count += 1
    has_pending = any(row[3] == "pending" for row in rows)
    with store.connection() as db:
        run = db.execute(
            "INSERT INTO monster_idle_distribution_runs"
            "(world_epoch,map_id,instance_id,empty_generation,status,finished_at) "
            "VALUES(%s,%s,%s,%s,%s,CASE WHEN %s THEN clock_timestamp() END) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (*episode, "pending" if has_pending else "completed", not has_pending),
        ).fetchone()
        if run is None:
            return db.execute(
                "SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=%s "
                "AND map_id=%s AND instance_id=%s AND empty_generation=%s",
                episode,
            ).fetchone()["id"]
        for ordinal, chunk, move, status, reason in rows:
            db.execute(
                "INSERT INTO monster_idle_distribution_moves"
                "(run_id,ordinal,chunk_index,group_id,expected_members,moved_members,"
                "status,reason,finished_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,"
                "CASE WHEN %s THEN clock_timestamp() END)",
                (
                    run["id"],
                    ordinal,
                    chunk,
                    move["group_id"],
                    Jsonb(move["expected_members"]),
                    Jsonb(move["moved_members"]),
                    status,
                    reason,
                    status != "pending",
                ),
            )
        return run["id"]


def pending(store, *, epoch, scope, generation, limit=1):
    """Return compact durable chunk identities; rosters stay in SQL."""
    episode = _episode(epoch, scope, generation)
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid idle distribution proposal limit")
    with store.connection() as db:
        rows = db.execute(
            "SELECT r.id,m.chunk_index FROM monster_idle_distribution_runs r "
            "JOIN monster_idle_distribution_moves m ON m.run_id=r.id "
            "WHERE r.world_epoch=%s AND r.map_id=%s AND r.instance_id=%s "
            "AND r.empty_generation=%s AND r.status='pending' AND m.status='pending' "
            "GROUP BY r.id,m.chunk_index ORDER BY m.chunk_index LIMIT %s",
            (*episode, limit),
        ).fetchall()
    return [
        dict(
            kind="idle_distribution",
            world_epoch=epoch,
            scope=list(scope),
            empty_generation=generation,
            run_id=r["id"],
            chunk_index=r["chunk_index"],
        )
        for r in rows
    ]


def read_chunk(store, proposal):
    """Read immutable raw rosters for validation before acquiring World locks."""
    episode = _episode(
        proposal["world_epoch"], proposal["scope"], proposal["empty_generation"]
    )
    with store.connection() as db:
        rows = db.execute(
            "SELECT m.group_id,m.expected_members,m.moved_members FROM "
            "monster_idle_distribution_moves m JOIN monster_idle_distribution_runs r "
            "ON r.id=m.run_id WHERE r.id=%s AND r.world_epoch=%s "
            "AND r.map_id=%s AND r.instance_id=%s AND r.empty_generation=%s "
            "AND r.status='pending' AND m.chunk_index=%s AND m.status='pending' "
            "ORDER BY m.ordinal",
            (proposal["run_id"], *episode, proposal["chunk_index"]),
        ).fetchall()
    return [dict(row) for row in rows]


def prepare(store, snapshot, limit=1):
    """Freeze each newly empty scope once; later ticks only resume its chunks."""
    from .combat_terrain import map_geometry
    from .monster_idle_distribution import plan, footprint_cells
    from .monster_birth_home import ensure_homes, region_for_point

    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid idle distribution preparation limit")
    epoch = snapshot["world_epoch"]
    proposals = []
    for empty in snapshot.get("empty_scopes", ()):
        scope = (empty["map_id"], empty["instance_id"])
        if scope[1] != 0:
            continue
        generation = empty["empty_generation"]
        episode = _episode(epoch, scope, generation)
        with store.connection() as db:
            exists = db.execute(
                "SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=%s "
                "AND map_id=%s AND instance_id=%s AND empty_generation=%s",
                episode,
            ).fetchone()
            groups = (
                None
                if exists
                else [
                    dict(row)
                    for row in db.execute(
                        "SELECT group_id,status,members FROM combat_groups WHERE map_id=%s "
                        "AND instance_id=%s ORDER BY group_id",
                        scope,
                    )
                ]
            )
            if not exists:
                from .monster_population_capacity import pending_growth_groups

                reservations = pending_growth_groups(
                    db, *scope, existing_group_ids=[g["group_id"] for g in groups]
                )
        if not exists:
            try:
                # Historical defeated groups are not placement candidates. Their
                # old positions may no longer have a native territory and must
                # not prevent the living population from being distributed.
                homes = ensure_homes(
                    store,
                    *scope,
                    [group for group in groups if group["status"] != "defeated"],
                )
                occupied = {
                    cell
                    for reservation in reservations
                    for member in reservation["members"]
                    for cell in footprint_cells(member)
                }
                moves = plan(
                    groups,
                    map_geometry(scope[0]),
                    occupied=occupied,
                    limit=max(1, len(groups)),
                    home_regions=homes,
                    region_at=lambda cell, _map=scope[0]: region_for_point(_map, cell),
                )
            except (ValueError, KeyError) as exc:
                LOGGER.warning(
                    "Idle distribution planning deferred for scope %s "
                    "episode %s: %s",
                    scope,
                    generation,
                    exc,
                )
                continue
            freeze(store, epoch=epoch, scope=scope, generation=generation, moves=moves)
        candidates = pending(
            store,
            epoch=epoch,
            scope=scope,
            generation=generation,
            limit=limit - len(proposals),
        )
        for proposal in candidates:
            if not home_chunk_allowed(store, proposal):
                cancel(store, epoch=epoch, scope=scope, generation=generation)
                break
            proposals.append(proposal)
        if len(proposals) >= limit:
            break
    return proposals


def home_chunk_allowed(store, proposal):
    """Fence frozen legacy plans before Ecology sends them to World."""
    from .monster_birth_home import ensure_homes, home_destination_allowed
    from .monster_idle_distribution import native_physical_radius

    scope = tuple(proposal["scope"])
    planned = read_chunk(store, proposal)
    groups = [
        dict(group_id=move["group_id"], members=move["expected_members"])
        for move in planned
    ]
    homes = ensure_homes(store, *scope, groups)
    for move in planned:
        home = homes.get(move["group_id"])
        if home is None:
            return False
        for member in move["moved_members"]:
            if not home_destination_allowed(
                scope[0],
                home,
                (member["x"], member["y"], member["z"]),
                radii=(native_physical_radius(member["ref"]),),
            ):
                return False
    return True


def _cancel(db, run_id):
    db.execute(
        "UPDATE monster_idle_distribution_moves SET status='cancelled',"
        "finished_at=clock_timestamp() WHERE run_id=%s AND status='pending'",
        (run_id,),
    )
    db.execute(
        "UPDATE monster_idle_distribution_runs SET status='cancelled',"
        "finished_at=clock_timestamp() WHERE id=%s AND status='pending'",
        (run_id,),
    )


def cancel(store, *, epoch, scope, generation):
    episode = _episode(epoch, scope, generation)
    with store.connection() as db:
        row = db.execute(
            "SELECT id FROM monster_idle_distribution_runs WHERE world_epoch=%s "
            "AND map_id=%s AND instance_id=%s AND empty_generation=%s FOR UPDATE",
            episode,
        ).fetchone()
        if row is not None:
            _cancel(db, row["id"])


def validate_chunk(store, proposal):
    """Prepare catalog/roster authority outside all World and SQL write locks."""
    scope = tuple(proposal["scope"])
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_obstacle_condition import footprint
    from .combat_terrain import map_geometry
    from .monster_population_capacity import physical_groups, pending_growth_groups

    planned = read_chunk(store, proposal)
    for move in planned:
        _validate_move(move, scope)
    # Commit checks every living/reserved footprint, not only moved groups.
    # Resolve their finite species union before entering World/write locks.
    with store.connection() as db:
        living = physical_groups(db, *scope)
        reservations = pending_growth_groups(
            db, *scope, existing_group_ids=[row["group_id"] for row in living]
        )
    references = {
        str(member["ref"])
        for move in planned
        for field in ("expected_members", "moved_members")
        for member in move[field]
    } | {
        str(member["ref"])
        for group in (*living, *reservations)
        for member in group["members"]
    }
    profiles = native_actor_catalog()["npc_profiles"]
    radii = {}
    for reference in sorted(references):
        radius = profiles[reference]["physical_radius"]
        if type(radius) is not int or not -128 <= radius <= 127:
            raise ValueError("Invalid native signed-byte obstacle radius")
        radii[reference] = radius
    native = {tuple(cell) for cell in map_geometry(scope[0])["cells"]}
    for move in planned:
        occupied = set()
        for member in move["moved_members"]:
            actual = {
                (x, y, member["z"])
                for x, y in footprint(
                    (member["x"], member["y"]), radii[str(member["ref"])]
                )
            }
            if not actual <= native or actual & occupied:
                raise ValueError("Idle distribution leaves native terrain or overlaps")
            occupied.update(actual)
    return dict(proposal=deepcopy(proposal), moves=planned, radii=radii)


def commit(store, groups, proposal, *, episode_current, prepared=None):
    """CAS positions and acknowledge a bounded chunk in the same transaction.

    ``episode_current`` is sampled by the caller while holding its presence
    fence. Keep that fence held until return. ``prepared`` must be obtained via
    validate_chunk before acquiring World locks; this path never loads catalogs.
    """
    if type(episode_current) is not bool:
        raise ValueError("Missing idle distribution presence fence")
    if prepared is None or prepared["proposal"] != proposal:
        raise ValueError("Missing prepared idle distribution chunk")
    episode = _episode(
        proposal["world_epoch"], proposal["scope"], proposal["empty_generation"]
    )
    scope = tuple(proposal["scope"])
    from .combat_obstacle_condition import footprint

    def cells(members):
        return {
            (x, y, m["z"])
            for m in members
            for x, y in footprint((m["x"], m["y"]), prepared["radii"][str(m["ref"])])
        }

    outcomes = []
    with store.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("monster-population:" + ":".join(map(str, scope)),),
        )
        run = db.execute(
            "SELECT * FROM monster_idle_distribution_runs WHERE id=%s "
            "AND world_epoch=%s AND map_id=%s AND instance_id=%s "
            "AND empty_generation=%s FOR UPDATE",
            (proposal["run_id"], *episode),
        ).fetchone()
        if run is None or run["status"] != "pending":
            return []
        if not episode_current:
            _cancel(db, run["id"])
            return []
        moves = db.execute(
            "SELECT * FROM monster_idle_distribution_moves WHERE run_id=%s "
            "AND chunk_index=%s AND status='pending' ORDER BY ordinal FOR UPDATE",
            (run["id"], proposal["chunk_index"]),
        ).fetchall()
        if len(moves) > MAX_CHUNK_GROUPS:
            raise ValueError("Idle distribution chunk exceeds group budget")
        if [
            dict(
                group_id=m["group_id"],
                expected_members=m["expected_members"],
                moved_members=m["moved_members"],
            )
            for m in moves
        ] != prepared["moves"]:
            # Another delivery already acknowledged some rows; it is safe to
            # retry the remaining chunk with a fresh read outside World locks.
            return []
        living_rows = list(
            db.execute(
                "SELECT group_id,members FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND status!='defeated'",
                scope,
            )
        )
        from .monster_population_capacity import pending_growth_groups

        reservations = pending_growth_groups(
            db, *scope, existing_group_ids=[row["group_id"] for row in living_rows]
        )
        if any(
            str(member["ref"]) not in prepared["radii"]
            for group in (*living_rows, *reservations)
            for member in group["members"]
        ):
            # A new species appeared after preparation. Leave the chunk pending
            # for fresh preparation; never ignore a blocker or load under locks.
            return []
        living = {row["group_id"]: cells(row["members"]) for row in living_rows}
        reserved = cells([m for r in reservations for m in r["members"]])
        for move in moves:
            row = db.execute(
                "SELECT members,instance_id FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s AND group_id=%s AND status='available' FOR UPDATE",
                (*scope, move["group_id"]),
            ).fetchone()
            status = "skipped"
            destination = cells(move["moved_members"])
            blocked = reserved | set().union(
                *(
                    occupied
                    for gid, occupied in living.items()
                    if gid != move["group_id"]
                )
            )
            if (
                row is not None
                and row["members"] == move["expected_members"]
                and not destination & blocked
            ):
                durable = move["moved_members"]
                db.execute(
                    "UPDATE combat_groups SET members=%s,revision=revision+1 "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    (Jsonb(durable), *scope, move["group_id"]),
                )
                status = "applied"
                living[move["group_id"]] = destination
            db.execute(
                "UPDATE monster_idle_distribution_moves SET status=%s,"
                "finished_at=clock_timestamp() WHERE run_id=%s AND ordinal=%s",
                (status, run["id"], move["ordinal"]),
            )
            outcomes.append(dict(group_id=move["group_id"], status=status))
        db.execute(
            "UPDATE monster_idle_distribution_runs SET status='completed',"
            "finished_at=clock_timestamp() WHERE id=%s AND NOT EXISTS("
            "SELECT 1 FROM monster_idle_distribution_moves WHERE run_id=%s "
            "AND status='pending')",
            (run["id"], run["id"]),
        )
    return outcomes
