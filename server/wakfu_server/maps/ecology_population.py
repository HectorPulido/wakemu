"""Region-local population snapshots from durable server entities.

Unknown native surfaces remain explicit: callers must not use an incomplete
snapshot to grant ecological rewards or certify equilibrium.
"""
from collections import Counter
from .planting_cells import surface
from .planting import RESOURCES
from .monsters import reference
from .resource_domains import is_fixed_resource


def snapshot(
    db,
    map_id,
    instance_id,
    *,
    locate=surface,
    kinds=("plant", "monster"),
    exclude_unassigned=False
):
    """Exclude native region -1 only when explicitly requested by a trusted locator.

    Default strict behavior remains unchanged for reward/equilibrium consumers.
    Zero, missing, malformed and unresolved regions never become empty counts.
    """
    if type(map_id) is not int or not 0 < map_id < 2**31:
        raise ValueError("Invalid ecology map")
    if type(instance_id) is not int or not 0 <= instance_id < 2**63:
        raise ValueError("Invalid ecology instance")
    if (
        type(kinds) is not tuple
        or not kinds
        or len(set(kinds)) != len(kinds)
        or any(kind not in ("plant", "monster") for kind in kinds)
    ):
        raise ValueError("Invalid ecology population kinds")
    if type(exclude_unassigned) is not bool:
        raise ValueError("Invalid unassigned ecology population policy")
    regions, unresolved = {}, []

    def add(kind, identity, family, position):
        try:
            region_id = locate(map_id, *position)["region_id"]
        except ValueError:
            unresolved.append((kind, identity))
            return
        if exclude_unassigned and type(region_id) is int and region_id == -1:
            return
        if type(region_id) is not int or region_id <= 0:
            unresolved.append((kind, identity))
            return
        counts = regions.setdefault(
            region_id, {"plant": Counter(), "monster": Counter()}
        )
        counts[kind][family] += 1

    plants = (
        db.execute(
            "SELECT resource_uid,resource_reference,x,y,z FROM planted_resources "
            "WHERE map_id=%s AND instance_id=%s AND stage NOT IN (0,16)",
            (map_id, instance_id),
        )
        if "plant" in kinds
        else ()
    )
    for row in plants:
        definition = RESOURCES[row["resource_reference"]]
        # A planted monster seed is not yet a living monster.
        if not definition["monster_resource"] and not is_fixed_resource(
            row["resource_reference"]
        ):
            add(
                "plant",
                row["resource_uid"],
                definition["family_id"],
                tuple(row[key] for key in ("x", "y", "z")),
            )
    groups = (
        db.execute(
            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND status!='defeated' AND NOT EXISTS(SELECT 1 FROM objectives_public_hunts h "
            "WHERE h.map_id=combat_groups.map_id AND combat_groups.instance_id=0 "
            "AND h.group_id=combat_groups.group_id)",
            (map_id, instance_id),
        )
        if "monster" in kinds
        else ()
    )
    for group in groups:
        for member in group["members"]:
            add(
                "monster",
                member["id"],
                reference(member["ref"])["family_id"],
                tuple(member[key] for key in ("x", "y", "z")),
            )
    return {"regions": regions, "unresolved": unresolved, "complete": not unresolved}


def prepare(store, world_snapshot, limit=16):
    """External worker preparation; no live-world locks or mutations."""
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("Invalid ecology population preparation limit")
    epoch = world_snapshot.get("world_epoch")
    if type(epoch) is not str or not epoch:
        raise ValueError("Missing world epoch")
    from .monster_corpses import due_expiries
    from .monster_initial_population import pending_publications

    with store.connection() as db:
        proposals = [
            dict(row, kind="corpse_expiry", world_epoch=epoch)
            for row in due_expiries(db, limit=limit)
        ]
        if len(proposals) < limit:
            proposals.extend(
                dict(row, kind="initial_publish", world_epoch=epoch)
                for row in pending_publications(db, limit=limit - len(proposals))
            )
        completed = {
            (row["map_id"], row["instance_id"], row["region_id"])
            for row in db.execute(
                "SELECT map_id,instance_id,region_id FROM monster_initial_population"
            )
        }
    if len(proposals) == limit:
        return proposals
    from .monster_initial_population import configured_plans, prepare_zone

    # Seed configured native habitats even when no player is currently there.
    # This preserves the one-time startup population semantics.
    for plan in configured_plans(completed_habitats=completed):
        scope = tuple(plan[key] for key in ("map_id", "instance_id", "region_id"))
        if scope in completed:
            continue
        prepared = prepare_zone(store, plan)
        if prepared is not None:
            proposals.append(
                dict(prepared, kind="initial_population", world_epoch=epoch)
            )
        if len(proposals) == limit:
            break
    return proposals


def apply(store, groups, harvests, world, proposal, *, world_epoch):
    """Live world owner applies one revalidated proposal under existing fences."""
    if proposal.get("world_epoch") != world_epoch:
        return "stale"
    kind = proposal.get("kind")
    if kind not in ("corpse_expiry", "initial_population", "initial_publish"):
        raise ValueError("Unknown ecology population proposal")
    # Match combat settlement and harvesting lock order. Never call the worker
    # or rebuild map geometry while either live-world fence is held.
    with groups.lock, harvests.lock:
        if kind == "corpse_expiry":
            from .monster_corpses import publish_expiry

            with store.connection() as db, db.transaction():
                return publish_expiry(
                    db,
                    proposal,
                    lambda map_id, instance_id, packet: world.emit_location_batch(
                        map_id, instance_id, (packet,), require_all=True
                    ),
                )
        from .monster_initial_population import apply_prepared, publish_prepared

        if kind == "initial_publish":
            return publish_prepared(
                store,
                proposal,
                lambda map_id, instance_id, packets: world.emit_location_batch(
                    map_id, instance_id, packets, require_all=True
                ),
            )

        return apply_prepared(store, groups, proposal)
