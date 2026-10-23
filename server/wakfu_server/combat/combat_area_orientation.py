"""Original Qq orientation getters and the separate fbb mutable setter."""


def creation_area_pv(fight, identity, *, _seen=frozenset()):
    """Read actual Qq XYZ/bcy without requiring the fbb setter contract.

    Qq delegates facing to its owner or NORTH_EAST(7). faY always returns7;
    faW/fbb prefer their stored facing. Other registered subtypes inherit Qq.
    """
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_summon_initialization import registered_or_detached_actor

    if identity in _seen:
        raise ValueError("Cyclic native area orientation ownership")
    pv = registered_area_pv(fight, identity)
    if pv is None:
        return None
    row = retained_area_pv_row(fight, identity)
    contract = row["native_area_contract"]
    if contract == "faY":
        pv.direction = 7
        return pv
    if contract in ("faW", "fbb"):
        if "direction" not in row:
            raise ValueError("Missing native stored area orientation authority")
        direction = row["direction"]
        if direction is not None:
            if type(direction) is not int or direction not in range(-1, 10):
                raise ValueError("Invalid native stored area orientation")
            pv.direction = direction
            return pv
    if "owner_id" not in row:
        raise ValueError("Missing native area orientation owner authority")
    owner_id = row["owner_id"]
    if owner_id is None:
        pv.direction = 7
        return pv
    if type(owner_id) is not int:
        raise ValueError("Invalid native area orientation owner identity")
    owner = registered_or_detached_actor(fight, owner_id)
    if owner is None:
        owner = creation_area_pv(fight, owner_id, _seen=_seen | {identity})
    direction = getattr(owner, "direction", None)
    if type(direction) is not int or direction not in range(-1, 10):
        raise ValueError("Missing native area orientation owner facing")
    pv.direction = direction
    return pv


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
