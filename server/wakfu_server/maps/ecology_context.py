"""Publish durable regional populations without applying character bonuses."""
from . import ecology_population, planting_cells, territory_cells


def packet(store, character, *, open_test_policy=False):
    map_id = character["map_id"]
    instance_id = character.get("instance_id", 0)
    region_id = territory_cells.region_at(map_id, character["x"], character["y"])

    def locate(map_id, x, y, z):
        # Ecology ownership is regional, independently of whether an entity's
        # occupied cell is plantable. The native region grid ignores altitude.
        return {"region_id": territory_cells.region_at(map_id, x, y)}

    with store.connection() as db:
        population = ecology_population.snapshot(db, map_id, instance_id, locate=locate)
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
