"""Declared owned content uses persistent visits or an explicit native entry gate.

Only the installed owned-quest/story archetypes qualify. Native proximity,
entry items, effective-level policy, party and lease ownership keep their normal
producers. Source-declared strict gates evaluate the original criterion without bypasses.
Other routes retain their existing criterion callback unchanged.
"""

from contextlib import nullcontext

from wakfu_server import dungeon_instances, dungeon_entry_access

_MISSION_NAMES = (
    "IsAchievementActive",
    "IsAchievementRunning",
    "IsAchievementComplete",
    "IsAchievementObjectiveComplete",
)


def entry_policy(store, route, *, db=None):
    """Select a declared native gate or the existing persistent visit policy."""
    if not route.criterion.strip():
        return None
    with store.connection() if db is None else nullcontext(db) as db:
        row = db.execute(
            "SELECT q.configuration->'topology'->'owned_quest_encounter' AS quest_policy,"
            "q.configuration->'topology'->'owned_story_controller' AS story_policy,"
            "q.configuration->'topology'->'owned_object_trials' AS trial_policy "
            "FROM dungeon_runtime_active_configurations a JOIN dungeon_runtime_configurations q "
            "ON q.route_key=a.route_key AND q.policy_version=a.policy_version WHERE a.route_key=%s",
            (dungeon_instances.canonical_context_key(route),),
        ).fetchone()
    if row is None:
        return None
    selected = None
    if row["quest_policy"] is not None:
        from wakfu_server.achievements.owned_quest_encounters import policy

        selected = policy(
            dict(topology=dict(owned_quest_encounter=row["quest_policy"]))
        )
    elif row["story_policy"] is not None:
        from wakfu_server.owned_story_controller import policy

        selected = policy(
            dict(topology=dict(owned_story_controller=row["story_policy"]))
        )
    elif row.get("trial_policy") is not None:
        from wakfu_server import owned_object_trials

        selected = owned_object_trials.policy(
            dict(topology=dict(owned_object_trials=row["trial_policy"]))
        )
    if selected is None:
        return None
    native = selected.get("enforce_native_entry_criterion", False)
    if type(native) is not bool:
        raise ValueError("Owned native entry criterion policy must be boolean")
    if native:
        return "native"
    return (
        "persistent"
        if any(name in route.criterion for name in _MISSION_NAMES)
        else None
    )


def qualifies(store, route, *, db=None):
    return entry_policy(store, route, db=db) == "persistent"


def allowed(store, character, route, *, enforce_native_entry_criterion=False):
    """Authorize a declared visit or native gate without rewriting its criterion."""
    if type(enforce_native_entry_criterion) is not bool:
        raise ValueError("Owned native entry criterion policy must be boolean")
    if enforce_native_entry_criterion:
        from wakfu_server import dungeon_achievement_authority, dungeon_criteria

        return dungeon_criteria.evaluate(
            store,
            route.criterion,
            character=character,
            queries=dungeon_achievement_authority.queries(store, character["id"]),
        )
    return dungeon_entry_access.evaluate_owned_visit(
        store,
        route.criterion,
        character=character,
        destination_map_id=route.start_map_id,
    )
