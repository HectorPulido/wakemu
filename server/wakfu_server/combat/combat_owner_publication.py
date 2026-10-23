"""Resolve each authenticated company owner's actual live publication source."""


def publication_for_world_member(world, member, *, map_id, instance_id):
    """Capture the actual peer briefly; admission revalidates its live lease."""
    with world.lock:
        entry = world.players.get(member["id"])
        if (
            entry is None
            or len(entry) != 3
            or entry[0] != member["generation"]
            or entry[2].get("id") != member["id"]
            or entry[2].get("account_id") != member["account_id"]
        ):
            raise ValueError("Company owner has no matching live world session")
        peer = entry[1]
    scope_provider = getattr(peer, "native_instance_scope", None)
    tracker = getattr(peer, "instance_publications", None)
    scope = scope_provider() if callable(scope_provider) else None
    if (
        not isinstance(scope, tuple)
        or len(scope) != 5
        or scope
        != (
            member["account_id"],
            member["generation"],
            member["id"],
            map_id,
            instance_id,
        )
        or tracker is None
    ):
        raise ValueError(
            "Company owner publication belongs to another session or instance"
        )
    return tracker, scope
