"""Native outdoor territory boundaries shared by monster simulation paths."""


def habitat_destination_allowed(
    map_id, instance_id, destination, *, parent=None, family_id=None
):
    """Reject unowned surfaces and cross-territory outdoor population leaks.

    Authored interiors and private instances retain their existing movement
    policy. Walk edges establish reachability, but never territory ownership.
    """
    from .monster_initial_population import REGIONS
    from .planting_cells import surface
    from .territory_cells import region_at

    if instance_id != 0 or not any(key[0] == map_id for key in REGIONS):
        return True
    try:
        x, y, z = destination
        if any(type(value) is not int for value in (x, y, z)):
            return False
        region_id = surface(map_id, x, y, z)["region_id"]
        if region_id <= 0 or region_at(map_id, x, y) != region_id:
            return False
        habitat = REGIONS.get((map_id, region_id))
        if habitat is None or habitat.get("monster_capacity", 0) <= 0:
            return False
        if family_id is not None and family_id not in {
            row["family_id"] for row in habitat["monster_families"]
        }:
            return False
        if parent is not None:
            px, py, pz = (parent[key] for key in ("x", "y", "z"))
            if (
                surface(map_id, px, py, pz)["region_id"] != region_id
                or region_at(map_id, px, py) != region_id
            ):
                return False
        return True
    except (ValueError, KeyError, TypeError):
        return False
