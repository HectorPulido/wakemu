"""Planting locations from live server ownership, never stale SQL coordinates."""

from .haven_bag_garden import active_character as garden_character


LOCATION_KEYS = ("map_id", "instance_id", "x", "y", "z")


def _validate_location(character):
    for key, lower, upper in (
        ("map_id", 1, (1 << 31) - 1),
        ("instance_id", 0, (1 << 63) - 1),
        ("x", -(1 << 31), (1 << 31) - 1),
        ("y", -(1 << 31), (1 << 31) - 1),
        ("z", -(1 << 15), (1 << 15) - 1),
    ):
        value = character.get(key)
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError("Invalid authoritative planting location")


def active_character(stored, players, *, store=None, expected_location=None):
    """Keep SQL item/profession data and overlay one matching live location."""
    if not isinstance(stored, dict) or any(
        type(stored.get(key)) is not int or stored[key] <= 0
        for key in ("id", "account_id")
    ):
        raise ValueError("Invalid planting actor identity")
    matches = [player for player in players if player.get("id") == stored["id"]]
    if len(matches) != 1:
        raise ValueError("Planting requires one active actor location")
    live = matches[0]
    if live.get("account_id") != stored["account_id"]:
        raise ValueError("Planting actor account does not match its active session")
    if live.get("_ecology_active", True) is not True:
        raise ValueError("Planting actor is not active outside combat")
    _validate_location(live)
    if expected_location is not None:
        if not isinstance(expected_location, dict):
            raise ValueError("Invalid prepared planting origin")
        _validate_location(expected_location)
        if any(live[key] != expected_location[key] for key in LOCATION_KEYS):
            raise ValueError("Planting origin changed during preparation")
    if live["map_id"] in (9, 1440) and live["instance_id"] > 0:
        return garden_character(stored, [live], store=store)
    return {**stored, **{key: live[key] for key in LOCATION_KEYS}}


def owned_character(stored, world, positions, *, store=None, generation=None):
    """Use the current generation's buffered public location or private scene."""
    with world.lock:
        entry = world.players.get(stored["id"])
        if (
            entry is None
            or (generation is not None and entry[0] != generation)
            or (stored["id"], entry[0]) in world._ecology_inactive
        ):
            raise ValueError("Planting actor is no longer active in the world")
        generation, _, live = entry
        live = dict(live)
    # Validate ownership before consulting the account's position owner.
    validated = active_character(stored, [live], store=store)
    if live["map_id"] in (9, 1440) and live["instance_id"] > 0:
        validated["direction"] = live["direction"]
        return validated
    current = positions.merge(stored["account_id"], generation, stored)
    if any(current[key] != live[key] for key in ("map_id", "instance_id")):
        raise ValueError("Planting position owner belongs to another scene")
    result = active_character(stored, [current], store=store)
    result["direction"] = current["direction"]
    return result
