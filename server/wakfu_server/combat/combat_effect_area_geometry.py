"""Geometry of registered Qq areas; no fabricated fighter or height."""


def registered_area_cells(definition, cell, direction, *, reference=None):
    from .combat_effect_targets import area_offsets

    shape = dict(
        area_class=definition["native_shape_class"],
        area_native=definition["native_shape_description"],
    )
    if "native_area_points" in definition:
        shape["native_area_points"] = definition["native_area_points"]
    offsets = area_offsets(
        shape,
        origin=cell,
        reference=cell if reference is None else reference,
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


def contains_area_actor(row, cell, physical_radius):
    """Qq.a(PV,x,y,z): center first, then square physical-radius expansion."""
    if type(physical_radius) is not int or not -128 <= physical_radius <= 127:
        raise ValueError("Missing native area actor signed-byte radius")
    if contains_area_cell(row, cell):
        return True
    return any(
        contains_area_cell(row, (cell[0] + dx, cell[1] + dy))
        for dx in range(-physical_radius, physical_radius + 1)
        for dy in range(-physical_radius, physical_radius + 1)
    )


def refresh_area_geometry(fight, row):
    """faN coordinates delegate to the actual bgZ PV at each query boundary."""
    if row.get("native_area_contract") != "faN":
        return row
    owner_id = row.get("native_anchor_id")
    if (
        type(owner_id) is not int
        or owner_id != row.get("owner_id")
        or row.get("native_anchor_source") != "faN.bgZ"
    ):
        raise ValueError("Missing native faN owner anchor authority")
    owner = fight.actors.get(owner_id)
    if owner is None:
        raise ValueError("Missing registered native faN owner PV")
    cell = owner.position
    if (
        not isinstance(cell, (tuple, list))
        or len(cell) != 3
        or any(type(v) is not int for v in cell)
    ):
        raise ValueError("Missing native faN owner coordinates")
    from .combat_effect_area import native_effect_areas

    definition = native_effect_areas().get(str(row.get("reference")))
    if not isinstance(definition, dict) or definition.get("type") != "AURA":
        raise ValueError("Missing native faN AURA prototype")
    row["cell"] = tuple(cell)
    row["native_cells_xy"] = registered_area_cells(definition, cell, row["direction"])
    return row
