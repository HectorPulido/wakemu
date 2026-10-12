"""Remove authoritative defeated NPC groups from retained exploration scenes."""

from .combat_monster_world import remove_message


def defeated_snapshot(db, map_id, instance_id, *, lease=None):
    """Return world-only ctA removals, excluding revived or replaced groups.

    Call while holding the group registry lock through delivery. A complete
    exploration replay is additive on the native client; omitted defeated
    groups do not remove actors retained before entering spectator mode.
    A terminal publication additionally fences the completed lease revision.
    """
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
    ):
        raise ValueError("Invalid world cleanup scope")
    clause, params = "", [map_id, instance_id]
    if lease is not None:
        key, generation, fight_id, revision = lease
        if tuple(key[:2]) != (map_id, instance_id):
            raise ValueError("World cleanup lease belongs to another location")
        clause = " AND group_id=%s AND revision=%s"
        params.extend((key[2], revision + 1))
    rows = db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
        "AND status='defeated'" + clause + " ORDER BY group_id",
        params,
    )
    identities = []
    for row in rows:
        for member in row["members"]:
            if (member.get("map_id"), member.get("instance_id", 0)) != (
                map_id,
                instance_id,
            ):
                raise ValueError("Defeated group contains a foreign world actor")
            identities.append(member["id"])
    packets = tuple(
        remove_message(identities[offset : offset + 255])
        for offset in range(0, len(identities), 255)
    )
    from wakfu_server.ecology_admin import admin_removed_packets

    return packets + tuple(admin_removed_packets(db, map_id, instance_id))
