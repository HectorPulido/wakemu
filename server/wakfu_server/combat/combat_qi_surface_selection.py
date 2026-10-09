"""Select arena mask indices from actual ordered native Vy columns."""
from .combat_qi_surfaces import NativeQISurfaces


def native_surface_indices(surfaces, cells):
    if not isinstance(surfaces, NativeQISurfaces):
        raise ValueError("Missing authoritative native QI surfaces")
    result = {}
    for cell in cells:
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            or not -32768 <= cell[2] <= 32767
        ):
            raise ValueError("Invalid native arena surface coordinates")
        x, y, z = cell
        if (x, y) in result:
            raise ValueError("Arena requires one selected altitude per cell")
        ordered = None
        for (cx, cy, width, height), columns in surfaces.chunks:
            if cx <= x < cx + width and cy <= y < cy + height:
                ordered = columns.get((x, y), ())
                break
        if ordered is None:
            raise ValueError("Arena cell has no matching native QI chunk")
        matches = [index for index, surface in enumerate(ordered) if surface.z == z]
        if len(matches) != 1:
            raise ValueError("Arena altitude has no unique native QI surface")
        index = matches[0]
        if index > 63:
            raise ValueError("Arena surface index exceeds native QI mask capacity")
        result[(x, y)] = index
    if not result:
        raise ValueError("Missing selected native arena surfaces")
    return result
