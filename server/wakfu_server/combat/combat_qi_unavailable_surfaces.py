"""Exclude native missing-height columns from authored arena populations."""
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


def exclude_unavailable_surfaces(arena, surfaces, cells):
    """Keep real floors intact; mark missing native Vy as QI-unavailable.

    The exact -257 sentinel makes original QI.P/Q/R false: neither border nor
    whole-map population nor local target surface. Its clear bit256 does not
    manufacture a solid QI wall where there is no floor. Original static Vz
    ray occlusion and registered actor/area LOS obstacles remain authoritative.
    """
    if not isinstance(surfaces, NativeQISurfaces) or surfaces.map_id != arena["map_id"]:
        raise ValueError("Unavailable terrain requires matching native Vy authority")
    selected = {(x, y) for x, y, z in cells}
    masks = list(arena["cell_masks"])
    x0, y0, width = arena["x"], arena["y"], arena["width"]
    for offset, mask in enumerate(masks):
        x, y = x0 + offset % width, y0 + offset // width
        if (x, y) in selected:
            continue
        column = ()
        for (cx, cy, cw, ch), columns in surfaces.chunks:
            if cx <= x < cx + cw and cy <= y < cy + ch:
                column = columns.get((x, y), ())
                break
        index = mask & 63
        if index >= len(column) or column[index].z == -32768:
            masks[offset] = -257
    return dict(arena, cell_masks=masks)
