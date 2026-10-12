"""Publish durable regional populations without applying character bonuses."""
from . import ecology_population, planting_cells, territory_cells


def population_region(map_id, x, y, z):
    """Use regional XY ownership, or certify exact native unassigned terrain.

    Missing region-grid coverage alone is unknown. Only an existing exact XYZ
    native surface with the explicit -1 sentinel certifies no ecosystem owner.
    """
    if any(type(value) is not int for value in (map_id, x, y, z)):
        raise ValueError("Invalid native ecology position")
    try:
        return {"region_id": territory_cells.region_at(map_id, x, y)}
    except ValueError as missing_region:
        cell = planting_cells.surface(map_id, x, y, z)
        region_id = cell.get("region_id")
        if type(region_id) is int and region_id == -1:
            return {"region_id": -1}
        raise ValueError("Unresolved native ecology ownership") from missing_region


def packet(store, character, *, open_test_policy=False):
    map_id = character["map_id"]
    instance_id = character.get("instance_id", 0)
    region_id = territory_cells.region_at(map_id, character["x"], character["y"])

    with store.connection() as db:
        population = ecology_population.snapshot(
            db, map_id, instance_id, locate=population_region, exclude_unassigned=True
        )
    if not population["complete"]:
        raise ValueError("Regional ecology population is incomplete")
    counts = population["regions"].get(region_id, {})
    return planting_cells.region_context(
        character,
        region_id,
        monster_counts=dict(counts.get("monster", {})),
        plant_counts=dict(counts.get("plant", {})),
        open_test_policy=open_test_policy,
    )
