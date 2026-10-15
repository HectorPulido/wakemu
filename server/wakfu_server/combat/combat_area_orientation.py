"""Verified fbb orientation PVs for native eWF, independent of fighters."""


def orientation_area_pv(fight, identity):
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_effect_area import native_effect_areas
    from .combat_simple_area import verified_simple_area

    pv = registered_area_pv(fight, identity)
    if pv is None:
        return None
    row = retained_area_pv_row(fight, identity)
    definition = native_effect_areas().get(str(row.get("reference")))
    # fbb overrides both Qq.bcy and Qq.a(aAS). Other Qq subtypes must
    # retain their own contracts; the base setter itself is a no-op.
    verified_simple_area(row, definition)
    direction = row.get("direction")
    if type(direction) is not int or direction not in range(-1, 10):
        raise ValueError("Missing native fbb orientation")
    pv.direction = direction
    return pv


def set_area_direction(fight, actor, direction):
    from .combat_state_managers import retained_area_pv_row
    from .combat_effect_area_geometry import registered_area_cells
    from .combat_effect_area import native_effect_areas

    orientation_area_pv(fight, actor.id)
    if type(direction) is not int or direction not in range(-1, 10):
        raise ValueError("Missing native fbb direction value")
    row = retained_area_pv_row(fight, actor.id)
    definition = native_effect_areas()[str(row["reference"])]
    cells = registered_area_cells(definition, row["cell"], direction)
    row["direction"] = direction
    row["native_cells_xy"] = cells
    actor.direction = direction
