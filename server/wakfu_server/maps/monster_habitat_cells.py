"""Native surface validation shared by monster simulation paths."""


def habitat_destination_allowed(
    map_id, instance_id, destination, *, parent=None, family_id=None
):
    """Require native outdoor surfaces without species or territory restrictions.

    Authored interiors and private instances retain their existing movement
    policy. Callers retain directed walk edges and occupancy checks. Regional
    affinity affects Wakfu/Stasis balance, not movement or reproduction.
    """
    from .monster_initial_population import REGIONS
    from .planting_cells import surface

    if instance_id != 0 or not any(key[0] == map_id for key in REGIONS):
        return True
    try:
        x, y, z = destination
        if any(type(value) is not int for value in (x, y, z)):
            return False
        surface(map_id, x, y, z)
        return True
    except (ValueError, KeyError, TypeError):
        return False
