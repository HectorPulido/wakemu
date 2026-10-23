"""Geometry of registered Qq areas; no fabricated fighter or height."""
from functools import lru_cache


@lru_cache(maxsize=2048)
def _footprint_membership(footprint):
    # Only immutable coordinate values are retained, never a row or a fight.
    return frozenset(tuple(point) for point in footprint)


def _area_membership(row):
    footprint = row.get("native_cells_xy")
    if footprint is None:
        if row.get("native_hour_contract") is True:
            footprint = (tuple(row["cell"][:2]),)
        else:
            raise ValueError("Missing native registered area geometry")
    if isinstance(footprint, tuple):
        if len(footprint) > 4096:
            return frozenset(tuple(point) for point in footprint)
        try:
            return _footprint_membership(footprint)
        except TypeError:
            # Checkpoints can contain mutable point lists inside a tuple.
            pass
    immutable = tuple(tuple(point) for point in footprint)
    if len(immutable) > 4096:
        return frozenset(immutable)
    return _footprint_membership(immutable)


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
    return tuple(cell[:2]) in _area_membership(row)


def contains_area_actor(row, cell, physical_radius):
    """Qq.a(PV,x,y,z): center first, then square physical-radius expansion."""
    if type(physical_radius) is not int or not -128 <= physical_radius <= 127:
        raise ValueError("Missing native area actor signed-byte radius")
    footprint = _area_membership(row)
    if tuple(cell[:2]) in footprint:
        return True
    return any(
        (cell[0] + dx, cell[1] + dy) in footprint
        for dx in range(-physical_radius, physical_radius + 1)
        for dy in range(-physical_radius, physical_radius + 1)
    )


@lru_cache(maxsize=1024)
def _aura_cells(reference, shape_class, description, points, cell, direction):
    definition = dict(
        native_shape_class=shape_class, native_shape_description=description
    )
    if points is not None:
        definition["native_area_points"] = points
    return registered_area_cells(definition, cell, direction)


def _refresh_cells(definition, reference, cell, direction):
    from .combat_area_geometry import _cacheable_area_text

    shape_class = definition["native_shape_class"]
    description = definition["native_shape_description"]
    points = definition.get("native_area_points")
    # Cache only the canonical published shape forms. Malformed definitions
    # still reach the existing shape validator, including after a warm hit.
    if (
        type(shape_class) is not str
        or not _cacheable_area_text(description)
        or type(direction) is not int
        or (
            "native_area_points" in definition
            and (
                not isinstance(points, (tuple, list))
                or len(points) > 4096
                or any(
                    not isinstance(point, (tuple, list))
                    or len(point) != 2
                    or any(type(value) is not int for value in point)
                    for point in points
                )
            )
        )
    ):
        return registered_area_cells(definition, cell, direction)
    immutable_points = (
        None if points is None else tuple(tuple(point) for point in points)
    )
    return _aura_cells(
        reference, shape_class, description, immutable_points, tuple(cell), direction
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
    row["native_cells_xy"] = _refresh_cells(
        definition, str(row.get("reference")), cell, row["direction"]
    )
    return row
