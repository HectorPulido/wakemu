"""Declared native empty columns are LOS-transparent and path-blocked.

A Vy bld=-1 is not a walkable surface. A matching zero-height static Vz
contains no solid volume. Selecting its real index with QI bit512 preserves
Sn/QI.Z path rejection while avoiding the unrelated QI.h solid bit256.
"""
from .combat_qi_surfaces import NativeQISurfaces
from collections.abc import Mapping

POLICY = "wakemu.reconstructed-native-empty-gap-v1"
TRANSPARENT_VOID_POLICY = "wakemu.reconstructed-native-empty-gap-v2"


def native_empty_gap_indices(surfaces, columns, cells, *, transparent_void=False):
    if not isinstance(surfaces, NativeQISurfaces) or type(transparent_void) is not bool:
        raise ValueError("Missing native gap Vy authority")
    cells = tuple(cells)
    if (
        not cells
        or not isinstance(columns, Mapping)
        or any(
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            for cell in cells
        )
    ):
        raise ValueError("Missing native gap column coordinates")
    selected = {(x, y) for x, y, z in cells}
    x0, x1 = min(x for x, y, z in cells), max(x for x, y, z in cells)
    y0, y1 = min(y for x, y, z in cells), max(y for x, y, z in cells)
    if len(selected) != len(cells) or (x1 - x0 + 1) * (y1 - y0 + 1) > 32767:
        raise ValueError("Native empty-gap rectangle exceeds arena bounds")
    result = {}
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if (x, y) in selected:
                continue
            ordered = None
            for (cx, cy, width, height), values in surfaces.chunks:
                if cx <= x < cx + width and cy <= y < cy + height:
                    ordered = values.get((x, y), ())
                    break
            # Multiple surfaces, unknown void altitude, walkable surfaces and
            # any positive-height static obstacle retain the ordinary mask.
            if ordered is None or len(ordered) != 1:
                continue
            surface = ordered[0]
            static = columns.get((x, y), ())
            if surface.bld != -1 or len(static) != 1:
                continue
            altitude, height, transparent = static[0]
            if (
                type(altitude) is not int
                or type(height) is not int
                or type(transparent) is not bool
                or altitude != surface.z
                or height != 0
            ):
                continue
            if surface.z == -32768 and not (transparent_void and transparent is True):
                continue
            result[(x, y)] = 0  # The sole actual Vy, never an invented surface.
    return result


def selected_gap_indices(map_id, cells, policy):
    if policy not in (POLICY, TRANSPARENT_VOID_POLICY):
        raise ValueError("Unknown native empty-gap policy")
    from .combat_qi_surface_catalog import native_qi_surfaces
    from .combat_native_los_ray import topology_columns

    surfaces = native_qi_surfaces(map_id)
    if surfaces.map_id != map_id:
        raise ValueError("Native empty-gap map authority changed")
    return native_empty_gap_indices(
        surfaces,
        topology_columns(map_id),
        cells,
        transparent_void=policy == TRANSPARENT_VOID_POLICY,
    )


def restored_gap_indices(map_id, cells, record):
    policy = record.get("native_los_gap_policy")
    entries = record.get("native_los_gap_surfaces")
    if policy is None:
        if entries is not None:
            raise ValueError("Native gap surfaces lack declared policy")
        return None
    expected = selected_gap_indices(map_id, cells, policy)
    if entries != [[x, y, index] for (x, y), index in sorted(expected.items())]:
        raise ValueError("Persisted native empty-gap surfaces changed")
    return expected
