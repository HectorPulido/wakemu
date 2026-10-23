"""Exact environmental group ownership fences for ordinary ecology.

These queries never acquire an environmental scope lock. They may be used while
holding the ordinary monster-population fence without reversing lock order.
Ownership is identity based; an ordinary monster of the same breed is unaffected.
"""


def exclusion_sql(alias="combat_groups", *, active_only=False):
    if alias not in ("combat_groups", "g") or type(active_only) is not bool:
        raise ValueError("Invalid environmental ecology query scope")
    return (
        "NOT EXISTS(SELECT 1 FROM environmental_owned_groups environmental_owned "
        f"WHERE (environmental_owned.map_id,environmental_owned.world_instance_id,environmental_owned.group_id)="
        f"({alias}.map_id,{alias}.instance_id,{alias}.group_id)"
        + (" AND environmental_owned.retired_at_ms IS NULL" if active_only else "")
        + ")"
    )


def is_owned_group(db, key):
    """Include historical ownership when guarding mutation or settlement."""
    return (
        db.execute(
            "SELECT 1 FROM environmental_owned_groups WHERE map_id=%s "
            "AND world_instance_id=%s AND group_id=%s",
            tuple(key),
        ).fetchone()
        is not None
    )


def owned_monster_ids(db, map_id, instance_id):
    """Return actual owned identities, including historical tombstones."""
    return {
        row["monster_id"]
        for row in db.execute(
            "SELECT m.monster_id FROM environmental_owned_group_members m "
            "JOIN environmental_owned_groups o USING(instance_id,group_ordinal) "
            "WHERE o.map_id=%s AND o.world_instance_id=%s",
            (map_id, instance_id),
        )
    }
