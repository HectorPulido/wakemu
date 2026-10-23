"""Request-owned equipment predicates from the actual selected actor.

Hydrated players carry database-backed authority for predicates that need it.
Small pure projections may omit those fields; an actual predicate still rejects
missing authority instead of deriving an administrator or NPC identity.
"""


def for_character(character, explicit=None):
    if explicit is not None:
        return explicit
    stored = character.get("equipment_criterion_context")
    if stored is not None:
        if not isinstance(stored, dict) or stored.get("actor_kind") != "player":
            raise ValueError("Invalid hydrated player equipment context")
        context = dict(stored)
    else:
        context = {"actor_kind": "player"}
        if "real_level" in character or "level" in character:
            context["real_level"] = character.get("real_level", character.get("level"))
    # Proposed recustomization/build projections may replace actor fields while
    # retaining the same read-only profession/social snapshot.
    for source, target in (
        ("breed", "breed_id"),
        ("account_is_admin", "is_admin"),
        ("real_level", "real_level"),
    ):
        if source in character:
            context[target] = character[source]
    level = character.get("effective_level", character.get("level"))
    if type(level) is not int or not 0 <= level <= 32767:
        raise ValueError("Missing native player equipment level")
    context["level"] = level
    if "map_id" in character:
        context["native_map_id"] = character["map_id"]
    # Native IsDay is a live game-clock predicate, not a saved actor fact.
    # Refresh even when this actor was loaded before the day boundary.
    from wakfu_server.world_clock import current_time_ms

    context["world_time_ms"] = current_time_ms()
    return context
