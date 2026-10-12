"""Real directional free-cell area witnesses, without eligibility shortcuts."""


def directional_freecell_recipient_cells(source, casting, roots, destinations):
    from wakfu_server.combat.combat_area_geometry import (
        oriented_area_offsets,
        native_area_contains,
    )

    if casting.get("free_cell") is not True or casting.get("linear") is not True:
        return []
    minimum, maximum = casting.get("minimum"), casting.get("maximum")
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or not 1 <= minimum <= maximum <= 32
    ):
        return []
    if not roots or any(
        root.get("effect_class") not in (3, 48)
        or root.get("children")
        or root.get("area_class") != "anJ"
        or root.get("native_target_selector") != {"class": "fcE", "mask": 9}
        or not root.get("native_area_points")
        for root in roots
    ):
        return []
    allowed = set(destinations)
    result = []
    anchors = sorted(
        cell
        for cell in allowed
        if (cell[0] == source[0] or cell[1] == source[1])
        and minimum <= abs(cell[0] - source[0]) + abs(cell[1] - source[1]) <= maximum
    )
    for anchor in anchors:
        for root in roots:
            for dx, dy in oriented_area_offsets(
                root, origin=anchor, reference=source, direction=None
            ):
                cell = (anchor[0] + dx, anchor[1] + dy, anchor[2])
                if (
                    cell in allowed
                    and cell not in (anchor, source)
                    and native_area_contains(
                        root, origin=anchor, reference=source, point=cell
                    )
                ):
                    if cell not in result:
                        result.append(cell)
                    if len(result) == 4:
                        return result
    return result
