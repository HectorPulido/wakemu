"""Whole-group territory homes recovered from durable birth provenance.

Foreign species retain the actual territory in which they were established.
An explicit legacy fallback is pinned once; it is never presented as proof of
the historical birthplace. No actor fields are rewritten by this module.
"""
import logging
from functools import lru_cache
from psycopg.types.json import Jsonb

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=32768)
def _allowed_home(map_id, home, point, radii):
    from .combat_obstacle_condition import footprint

    try:
        return all(
            region_for_point(map_id, (x, y, point[2])) == home
            for radius in radii
            for x, y in footprint(point[:2], radius)
        )
    except (ValueError, KeyError):
        return False


def home_destination_allowed(map_id, home, point, *, radii=(0,)):
    """Keep physical monster footprints in their actual home, not a species list."""
    if home is None:
        return True
    return _allowed_home(map_id, home, tuple(point), tuple(sorted(set(radii))))


def region_for_point(map_id, point):
    """Resolve native territory ownership without any family suitability gate."""
    return _region_for_point(map_id, tuple(point))


@lru_cache(maxsize=65536)
def _region_for_point(map_id, point):
    from .territory_cells import region_at
    from .planting_cells import surface

    x, y, z = point
    region = region_at(map_id, x, y)
    try:
        native_surface = surface(map_id, x, y, z)
    except ValueError:
        # Walkable maps need not expose a planting surface at every height.
        return region
    if native_surface["region_id"] != region:
        raise ValueError("Monster birth territory and native surface disagree")
    return region


def home_for_group(store, map_id, instance_id, group_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT region_id FROM monster_group_birth_homes WHERE map_id=%s "
            "AND instance_id=%s AND group_id=%s",
            (map_id, instance_id, group_id),
        ).fetchone()
    return None if row is None else row["region_id"]


def ensure_homes(store, map_id, instance_id, groups):
    """Pin missing homes before ecology can move, redistribute or reproduce.

    Sources and ancestors are read without World locks. The final insert uses
    ON CONFLICT so concurrent observations never replace a previously pinned
    home. Dead parents remain valid provenance for their living descendants.
    """
    requested = {
        g.get("group_id", g.get("key", (None, None, None))[2]): g
        for g in groups
        if g.get("members")
    }
    if instance_id != 0 or not requested:
        return {}
    with store.connection() as db:
        homes = {
            r["group_id"]: dict(r)
            for r in db.execute(
                "SELECT * FROM monster_group_birth_homes WHERE map_id=%s AND instance_id=%s",
                (map_id, instance_id),
            )
        }
        if requested.keys() <= homes.keys():
            return {gid: homes[gid]["region_id"] for gid in requested}
        durable = {
            r["group_id"]: dict(r)
            for r in db.execute(
                "SELECT group_id,members,status FROM combat_groups WHERE map_id=%s "
                "AND instance_id=%s",
                (map_id, instance_id),
            )
        }
        initial = list(
            db.execute(
                "SELECT region_id,group_id,initial_members FROM monster_initial_population "
                "WHERE map_id=%s AND instance_id=%s",
                (map_id, instance_id),
            )
        )
        plantings = list(
            db.execute(
                "SELECT operation_id AS source_key,resource,group_payload FROM planting_receipts "
                "WHERE group_payload IS NOT NULL AND (resource->>'map_id')::int=%s "
                "AND (resource->>'instance_id')::bigint=%s UNION ALL "
                "SELECT resource_uid::text,resource,group_payload FROM planting_growth_outbox "
                "WHERE group_payload IS NOT NULL AND (resource->>'map_id')::int=%s "
                "AND (resource->>'instance_id')::bigint=%s",
                (map_id, instance_id, map_id, instance_id),
            )
        )
        births = list(
            db.execute(
                "SELECT monster_id,cycle,parent_group_id,child_group_id,child FROM "
                "monster_reproduction_receipts WHERE map_id=%s AND instance_id=%s "
                "AND child_id IS NOT NULL AND child_group_id<>parent_group_id",
                (map_id, instance_id),
            )
        )
        arches = list(
            db.execute(
                "SELECT group_id,region_id,spawn_id FROM archmonster_spawn_births "
                "WHERE map_id=%s AND world_instance_id=%s",
                (map_id, instance_id),
            )
        )
        environmental = list(
            db.execute(
                "SELECT g.group_id,e.region_id,g.instance_id,g.group_ordinal FROM "
                "environmental_owned_groups g JOIN environmental_event_instances e "
                "ON e.instance_id=g.instance_id WHERE g.map_id=%s "
                "AND g.world_instance_id=%s AND e.region_id IS NOT NULL",
                (map_id, instance_id),
            )
        )
        genesis = list(
            db.execute(
                "SELECT id,outcome FROM ecology_admin_operations WHERE "
                "command IN ('!genesis','!genesis-all') AND outcome->'created_groups' IS NOT NULL"
            )
        )

    sources, repro = {}, {}

    def source(gid, region, kind, key, anchor=None):
        if gid in durable and type(region) is int and region > 0:
            sources.setdefault(
                gid,
                dict(
                    region_id=region,
                    source_kind=kind,
                    source_key=str(key),
                    anchor=anchor,
                ),
            )

    def point(member):
        return [member[k] for k in ("x", "y", "z")]

    for row in initial:
        if row["initial_members"]:
            source(
                row["group_id"],
                row["region_id"],
                "initial_population",
                row["region_id"],
                point(row["initial_members"][0]),
            )
    for row in plantings:
        payload, resource = row["group_payload"], row["resource"]
        if payload.get("key", ())[:2] != [map_id, instance_id]:
            continue
        anchor = point(resource)
        source(
            payload["key"][2],
            region_for_point(map_id, anchor),
            "planting",
            row["source_key"],
            anchor,
        )
    for row in arches:
        source(row["group_id"], row["region_id"], "archmonster_birth", row["spawn_id"])
    for row in environmental:
        source(
            row["group_id"],
            row["region_id"],
            "environmental_birth",
            f'{row["instance_id"]}:{row["group_ordinal"]}',
        )
    for row in genesis:
        outcome = row["outcome"]
        scopes = {
            tuple(s)
            for s in outcome.get("scopes", ())
            if len(s) == 3 and s[:2] == [map_id, instance_id]
        }
        if len(scopes) != 1:
            continue
        region = next(iter(scopes))[2]
        for created in outcome.get("created_groups", ()):
            key = created.get("key", ())
            if key[:2] == [map_id, instance_id]:
                source(key[2], region, "genesis_scope", row["id"])
    for row in births:
        repro.setdefault(row["child_group_id"], row)

    resolving = set()

    def resolve(gid, *, ancestor=False):
        if gid in homes:
            return homes[gid]
        if gid in resolving or gid not in durable:
            return None
        resolving.add(gid)
        resolved = sources.get(gid)
        if resolved is None and gid in repro:
            birth = repro[gid]
            parent = resolve(birth["parent_group_id"], ancestor=True)
            anchor = point(birth["child"])
            if parent is not None:
                resolved = dict(
                    region_id=parent["region_id"],
                    source_kind="reproduction_parent",
                    source_key=str(birth["parent_group_id"]),
                    anchor=anchor,
                )
            else:
                resolved = dict(
                    region_id=region_for_point(map_id, anchor),
                    source_kind="reproduction_birth",
                    source_key=f'{birth["monster_id"]}:{birth["cycle"]}',
                    anchor=anchor,
                )
        if resolved is None and not ancestor and durable[gid]["members"]:
            anchor = point(durable[gid]["members"][0])
            kind = "legacy_current_fallback"
            resolved = dict(
                region_id=region_for_point(map_id, anchor),
                source_kind=kind,
                source_key="first_ecology_observation",
                anchor=anchor,
            )
            if kind == "legacy_current_fallback":
                LOGGER.warning(
                    "Pinned legacy monster home from current position, "
                    "not historical birth proof: map=%s instance=%s group=%s region=%s",
                    map_id,
                    instance_id,
                    gid,
                    resolved["region_id"],
                )
        resolving.remove(gid)
        if resolved is not None:
            homes[gid] = resolved
        return resolved

    for gid in requested:
        resolve(gid)
    additions = {
        gid: home
        for gid, home in homes.items()
        if "recorded_at" not in home and gid in durable
    }
    if additions:
        with store.connection() as db:
            for gid, home in additions.items():
                db.execute(
                    "INSERT INTO monster_group_birth_homes(map_id,instance_id,group_id,"
                    "region_id,source_kind,source_key,anchor) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        map_id,
                        instance_id,
                        gid,
                        home["region_id"],
                        home["source_kind"],
                        home["source_key"],
                        None if home["anchor"] is None else Jsonb(home["anchor"]),
                    ),
                )
            # A concurrent first observation may have won with another source;
            # always return the actual immutable ledger, not our losing plan.
            return {
                r["group_id"]: r["region_id"]
                for r in db.execute(
                    "SELECT group_id,region_id FROM monster_group_birth_homes WHERE map_id=%s "
                    "AND instance_id=%s AND group_id=ANY(%s)",
                    (map_id, instance_id, list(requested)),
                )
            }
    return {gid: homes[gid]["region_id"] for gid in requested if gid in homes}
