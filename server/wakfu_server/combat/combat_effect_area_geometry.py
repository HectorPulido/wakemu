"""Geometry of registered Qq areas; no fabricated fighter or height."""


def registered_area_cells(definition, cell, direction):
    from .combat_effect_targets import area_offsets

    offsets = area_offsets(
        dict(
            area_class=definition["native_shape_class"],
            area_native=definition["native_shape_description"],
        ),
        origin=cell,
        reference=cell,
        direction=direction,
    )
    return tuple(sorted((cell[0] + x, cell[1] + y) for x, y in offsets))


def contains_area_cell(row, cell):
    if cell is None:
        return False
    footprint = row.get("native_cells_xy")
    if footprint is None:
        if row.get("native_hour_contract") is True:
            footprint = [row["cell"][:2]]
        else:
            raise ValueError("Missing native registered area geometry")
    return tuple(cell[:2]) in {tuple(p) for p in footprint}
