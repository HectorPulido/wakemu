"""Project an owned company into its current private scene without moving storage.

Bag and ranch sessions retain the exterior return location in PostgreSQL. Hero
membership changes keep that durable location and publish only a private view;
this adapter never transfers the host's ownership to a visiting account.
"""

LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")
SCENE_KEYS = ("haven_bag", "haven_bag_visitor", "haven_ranch_session")


def authorize(session, character, generation):
    """Validate the existing scene capability, accepting any supported scene."""
    if session is None:
        return
    if not session.owns(character):
        raise ValueError("Hero roster requires its current private scene session")
    validate_lease = getattr(session, "validate_lease", None)
    if validate_lease is not None:
        validate_lease(generation)


def project(roster, session, character, generation):
    """Keep each hero's inventory/build while using the selected actor's scene."""
    if session is None:
        return roster
    authorize(session, character, generation)
    leader = roster["leader"]
    if leader["id"] != character["id"] or any(
        actor["account_id"] != character["account_id"]
        for actor in (leader, *roster["heroes"])
    ):
        raise ValueError("Private hero roster belongs to another account or leader")
    scene = {key: character[key] for key in LOCATION_KEYS}
    scene.update({key: character[key] for key in SCENE_KEYS if key in character})
    return {
        **roster,
        "leader": {**leader, **scene},
        "heroes": tuple({**hero, **scene} for hero in roster["heroes"]),
    }
