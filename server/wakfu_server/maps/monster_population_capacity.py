"""Map-scoped monster population plus durable, not-yet-materialized births."""


def pending_growth_groups(db, map_id, instance_id, *, existing_group_ids=()):
    """Return unique unpublished planted groups not already in combat_groups."""
    existing = set(existing_group_ids)
    rows = db.execute(
        "SELECT group_payload FROM planting_growth_outbox "
        "WHERE published=FALSE AND group_payload IS NOT NULL "
        "AND (resource->>'map_id')::integer=%s "
        "AND (resource->>'instance_id')::bigint=%s "
        "UNION ALL "
        "SELECT group_payload FROM planting_receipts "
        "WHERE published=FALSE AND success AND group_payload IS NOT NULL "
        "AND (resource->>'map_id')::integer=%s "
        "AND (resource->>'instance_id')::bigint=%s",
        (map_id, instance_id, map_id, instance_id),
    ).fetchall()
    candidates = {}
    for row in rows:
        group = row["group_payload"]
        key = group.get("key") if isinstance(group, dict) else None
        members = group.get("members") if isinstance(group, dict) else None
        if (
            not isinstance(key, list)
            or len(key) != 3
            or key[:2] != [map_id, instance_id]
            or type(key[2]) is not int
            or not isinstance(members, list)
            or not members
            or any(not isinstance(member, dict) for member in members)
        ):
            raise ValueError("Invalid pending planted monster group reservation")
        group_id = key[2]
        if group_id in existing:
            continue
        prior = candidates.get(group_id)
        if prior is not None and prior != members:
            raise ValueError("Conflicting planted monster group reservations")
        candidates[group_id] = members
    return [
        dict(key=[map_id, instance_id, group_id], members=members)
        for group_id, members in candidates.items()
    ]


def snapshot(db, map_id, instance_id, *, groups=None):
    """Count living groups and durable growth reservations in one SQL scope."""
    if groups is None:
        groups = list(
            db.execute(
                "SELECT group_id,members FROM combat_groups "
                "WHERE map_id=%s AND instance_id=%s AND status!='defeated'",
                (map_id, instance_id),
            )
        )
    else:
        groups = list(groups)
    existing_ids = {row["group_id"] for row in groups if "group_id" in row}
    reservations = pending_growth_groups(
        db, map_id, instance_id, existing_group_ids=existing_ids
    )
    return dict(
        groups=groups,
        reservations=reservations,
        members=sum(len(row["members"]) for row in groups)
        + sum(len(group["members"]) for group in reservations),
        group_count=len(groups) + len(reservations),
    )


def has_capacity(counts, *, add_members, add_groups, max_members, max_groups):
    """Check an addition without evicting populations that already exceed caps."""
    return (
        counts["members"] + add_members <= max_members
        and counts["group_count"] + add_groups <= max_groups
    )
