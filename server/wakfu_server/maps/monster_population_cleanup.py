"""Periodic removal of certified native unassigned outdoor monster surfaces.

Unknown native data never authorizes deletion. Existing administrative
population tombstones preserve seed reconciliation and combat lease behavior.
The ecology delivery queue durably retries publication after the SQL commit.
"""
from copy import deepcopy
import time

from .environmental_group_ecology import exclusion_sql, is_owned_group

_SCAN_STATE = None
_SCAN_SECONDS = 60
_SCAN_GROUPS = 512


def certified_unassigned(map_id, member):
    """Only an exact native surface carrying region -1 is deletion evidence."""
    from .planting_cells import surface

    try:
        region = surface(map_id, *(member[key] for key in ("x", "y", "z")))["region_id"]
    except (ValueError, KeyError, TypeError):
        return False
    return type(region) is int and region == -1


def prepare(store, snapshot, limit=16, *, clock=time.monotonic):
    """Sweep bounded pages of public outdoor groups every elapsed minute."""
    global _SCAN_STATE
    # Standalone legacy planners do not own the external worker maintenance loop.
    if "planning_tick" not in snapshot:
        return []
    epoch = snapshot.get("world_epoch")
    if type(epoch) is not str or not epoch:
        raise ValueError("Missing cleanup world epoch")
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid cleanup preparation limit")
    now = clock()
    if _SCAN_STATE is not None and _SCAN_STATE[0] == epoch:
        if now - _SCAN_STATE[1] < _SCAN_SECONDS:
            return []
        cursor = _SCAN_STATE[2]
    else:
        cursor = (-1, -(1 << 63))
    from .monster_initial_population import REGIONS

    outdoor_maps = sorted({map_id for map_id, _ in REGIONS})
    excluded = set(snapshot.get("excluded_ids", ()))
    proposals = []
    examined = 0
    with store.connection() as db:
        rows = db.execute(
            "SELECT map_id,instance_id,group_id,members FROM combat_groups "
            "WHERE instance_id=0 AND status='available' AND map_id=ANY(%s) "
            "AND " + exclusion_sql() + " "
            "AND NOT EXISTS(SELECT 1 FROM developer_item_test_groups t WHERE "
            "(t.map_id,t.instance_id,t.group_id)=(combat_groups.map_id,combat_groups.instance_id,combat_groups.group_id)) "
            "AND (map_id,group_id)>(%s,%s) ORDER BY map_id,group_id LIMIT %s",
            (outdoor_maps, *cursor, _SCAN_GROUPS),
        )
        for row in rows:
            examined += 1
            cursor = (row["map_id"], row["group_id"])
            bad = [
                member["id"]
                for member in row["members"]
                if member["id"] not in excluded
                and certified_unassigned(row["map_id"], member)
            ]
            if not bad:
                continue
            proposals.append(
                dict(
                    kind="cleanup_unassigned",
                    world_epoch=epoch,
                    scope=[row["map_id"], row["instance_id"]],
                    group_id=row["group_id"],
                    expected_members=deepcopy(list(row["members"])),
                    actor_ids=bad,
                )
            )
            if len(proposals) >= limit:
                break
    if examined < _SCAN_GROUPS and len(proposals) < limit:
        cursor = (-1, -(1 << 63))
    _SCAN_STATE = (epoch, now, cursor)
    return proposals


def apply(store, groups, harvests, world, proposal, *, world_epoch):
    """Remove only certified actors, then publish under the world group fence."""
    if proposal.get("world_epoch") != world_epoch:
        return {"status": "stale_epoch"}
    from psycopg.types.json import Jsonb
    from .monster_initial_population import REGIONS
    from .combat_monster_world import remove_message, spawn_group

    scope = tuple(proposal["scope"])
    if (
        len(scope) != 2
        or scope[1] != 0
        or not any(key[0] == scope[0] for key in REGIONS)
    ):
        raise ValueError("Invalid cleanup scope")
    requested = set(proposal["actor_ids"])
    expected = list(proposal["expected_members"])
    if not requested or not requested <= {member["id"] for member in expected}:
        raise ValueError("Invalid cleanup actors")
    # Native IO is deliberately outside the live-world fences.
    if any(
        not certified_unassigned(scope[0], member)
        for member in expected
        if member["id"] in requested
    ):
        return {"status": "stale_group"}
    key = (*scope, proposal["group_id"])
    with groups.lock, harvests.lock:
        if {member["id"] for member in expected} & set(harvests.targets):
            return {"status": "harvesting"}
        with store.connection() as db, db.transaction():
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("monster-population:" + ":".join(map(str, scope)),),
            )
            row = db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
                key,
            ).fetchone()
            if is_owned_group(db, key):
                return {"status": "environmental_owned"}
            if row is None or row["status"] == "fighting":
                return {"status": "stale_group"}
            if {member["id"] for member in row["members"]} & set(harvests.targets):
                return {"status": "harvesting"}
            removed = set(row["ecology_admin_removed_ids"])
            duplicate = requested <= removed
            if not duplicate:
                if row["status"] != "available" or list(row["members"]) != expected:
                    return {"status": "stale_group"}
                db.execute(
                    "UPDATE combat_groups SET ecology_admin_removed_ids=%s,revision=revision+1 "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    (Jsonb(sorted(removed | requested)), *key),
                )
                ids = sorted(requested)
                for table in (
                    "monster_maturation_timers",
                    "monster_reproduction_timers",
                ):
                    db.execute(
                        f"DELETE FROM {table} WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s)",
                        (*scope, ids),
                    )
                db.execute(
                    "UPDATE monster_maturation_outbox SET published=TRUE "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s AND monster_id=ANY(%s)",
                    (*key, ids),
                )
                db.execute(
                    "UPDATE monster_reproduction_outbox o SET published=TRUE FROM monster_reproduction_receipts r "
                    "WHERE o.map_id=r.map_id AND o.instance_id=r.instance_id AND o.monster_id=r.monster_id "
                    "AND o.cycle=r.cycle AND o.map_id=%s AND o.instance_id=%s AND o.group_id=%s "
                    "AND (o.monster_id=ANY(%s) OR r.child_id=ANY(%s))",
                    (*key, ids, ids),
                )
            current = db.execute(
                "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()
        # Rebuild the current group, never a stale prepared survivor snapshot.
        # A failed send leaves this proposal in the durable ecology retry queue.
        old_ids = {member["id"] for member in expected}
        old_ids.update(member["id"] for member in current["members"])
        packets = [remove_message(tuple(sorted(old_ids)))]
        if current["status"] == "available" and current["members"]:
            packets.append((12608, spawn_group(current["members"], group_id=key[2])))
        world.emit_location_batch(*scope, packets, require_all=True)
        return {"status": "applied", "removed": len(requested), "duplicate": duplicate}
