"""Keep reconstructed owned training groups out of other players' scenes."""

from .rii_lesson_auto_start import KEYS
from .rii_free_practice import KEY as PRACTICE_KEY, KIND as PRACTICE_KIND


def group_owners(db, groups):
    """Find group owners only from authenticated training receipts."""
    entries = [
        (group, actor)
        for group in groups
        for actor in group["members"]
        if actor.get("ref") in (2335, 5458, 5466, 5585)
        and type(actor.get("id")) is int
        and actor["id"] < 0
    ]
    if not entries:
        return {}
    definitions = {
        5458: (("rii-guardian-actor:", "reconstructed_rii_guardian_actor"),),
        5466: tuple(KEYS.values()),
        2335: ((PRACTICE_KEY, PRACTICE_KIND),),
        5585: ((PRACTICE_KEY, PRACTICE_KIND),),
    }
    keys = [
        prefix + str(-actor["id"])
        for _, actor in entries
        for prefix, _ in definitions[actor["ref"]]
    ]
    rows = db.execute(
        "SELECT character_id,event_key,payload FROM character_achievement_events "
        "WHERE event_key=ANY(%s)",
        (keys,),
    ).fetchall()
    receipts = {row["event_key"]: row for row in rows}
    owners = {}
    for group, actor in entries:
        for prefix, kind in definitions[actor["ref"]]:
            row = receipts.get(prefix + str(-actor["id"]))
            if row is None:
                continue
            owner, payload = row["character_id"], row["payload"]
            if (
                isinstance(payload, dict)
                and payload.get("kind") == kind
                and payload.get("owner") == owner
                and payload.get("actor_id") == actor["id"]
                and payload.get("ref") == actor["ref"]
            ):
                previous = owners.setdefault(group["key"], owner)
                if previous != owner:
                    raise ValueError(
                        "Rii training group has conflicting owner receipts"
                    )
    return owners


def visible_groups(db, groups, character_id):
    """Keep owned training dummies out of later world snapshots.

    Their creation explicitly publishes them when admitting the encounter.
    Existing receipts may predate cleanup; do not replay those stale actors.
    """
    owners = group_owners(db, groups)
    return [group for group in groups if group["key"] not in owners]


def owned_actor_ids(db, actors, character_id):
    """Identify only exact owned dojo actors for world-scene cleanup."""
    groups = [
        {"key": (1388, 0, index + 1), "members": [actor]}
        for index, actor in enumerate(actors)
    ]
    owners = group_owners(db, groups)
    return [
        group["members"][0]["id"]
        for group in groups
        if owners.get(group["key"]) == character_id
    ]


def scene_cleanup(db, map_id, instance_id):
    """Retire retained private actors before replaying an exploration scene.

    Native world snapshots are additive. Omitting an unavailable or privately
    owned sack cannot remove a descriptor published by an earlier marker.
    Include historical groups, but retire only actors with exact receipts.
    """
    if map_id not in (1387, 1388) or instance_id != 0:
        return ()
    from wakfu_server.combat_monster_world import remove_message

    rows = db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s "
        "ORDER BY group_id",
        (map_id, instance_id),
    ).fetchall()
    actors = [actor for row in rows for actor in row["members"]]
    groups = [
        {"key": (map_id, instance_id, index + 1), "members": [actor]}
        for index, actor in enumerate(actors)
    ]
    owners = group_owners(db, groups)
    identities = sorted(
        {group["members"][0]["id"] for group in groups if group["key"] in owners}
    )
    return tuple(
        remove_message(identities[offset : offset + 255])
        for offset in range(0, len(identities), 255)
    )
