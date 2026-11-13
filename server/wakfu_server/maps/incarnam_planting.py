"""Narrow authorization for the private Incarnam planting exercise."""


def authorize_if_tutorial(db, character, seed, resource):
    """Reject forged tutorial requests; leave every other map unchanged.

    This is checked on remote preparation, world acceptance and final commit.
    Native planting surfaces and ownership checks continue to apply.
    """
    if character.get("map_id") != 1361:
        return False
    from wakfu_server.achievements.incarnam_resources import active

    if (
        seed.get("item_reference") != 30938
        or seed.get("action_id") != 13435
        or seed.get("resource_reference") != 824
        or resource.get("resource_reference") != 824
        or not active(db, character, 5136)
    ):
        raise ValueError("Incarnam planting exercise is not available")
    return True
