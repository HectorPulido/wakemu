"""eJV: current eGj instance GN, with native absent value minus one."""
from .combat_instance_level_group import InstanceDifficultySnapshot


def native_difficulty(actor_id, targeting, snapshot):
    if targeting is None:
        return -1
    if not isinstance(targeting, dict) or type(targeting.get("is_eGj")) is not bool:
        raise ValueError("Missing native dungeon difficulty actor type")
    if targeting["is_eGj"] is False:
        return -1
    if (
        not isinstance(snapshot, InstanceDifficultySnapshot)
        or snapshot.actor_id != actor_id
    ):
        raise ValueError("Missing actual native dungeon instance snapshot")
    return -1 if snapshot.difficulty is None else snapshot.difficulty


def runtime_difficulty(fight, actor_id, targeting):
    if targeting is None or targeting.get("is_eGj") is False:
        return native_difficulty(actor_id, targeting, None)
    from .combat_instance_publication import require_current_publication

    require_current_publication(fight)
    snapshots = getattr(fight, "native_instance_difficulty_snapshots", None)
    return native_difficulty(
        actor_id,
        targeting,
        snapshots.get(actor_id) if isinstance(snapshots, dict) else None,
    )
