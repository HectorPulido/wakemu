"""World-owned removal of certified native unassigned outdoor monsters.

Unknown native data never authorizes deletion. Existing administrative
tombstones preserve seed reconciliation and combat lease behavior."""

from .environmental_group_ecology import is_owned_group


def certified_unassigned(map_id, member):
    """Only an exact native surface carrying region -1 is deletion evidence."""
    from .planting_cells import surface

    try:
        region = surface(map_id, *(member[key] for key in ("x", "y", "z")))["region_id"]
    except (ValueError, KeyError, TypeError):
        return False
    return type(region) is int and region == -1


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
