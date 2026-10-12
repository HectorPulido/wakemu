"""Bounded recipient scenes derived from actual self-root/point-child geometry."""


def caster_point_recipient_cells(source, direction, roots, effects, destinations):
    from wakfu_server.combat.combat_area_geometry import (
        oriented_area_offsets,
        native_area_contains,
    )

    cells = []
    for root in roots:
        if (
            root.get("effect_class") != 330
            or root.get("native_target_selector") != {"class": "fcE", "mask": 2}
            or root.get("area_class") != "anA"
            or root.get("area_native") != "empty"
        ):
            return []
        for child_id in root.get("children", []):
            child = effects.get(str(child_id), {})
            parameters = child.get("parameters", [])
            if (
                child.get("effect_class") != 330
                or child.get("area_class") != "anE"
                or child.get("native_target_selector") != {"class": "fcE", "mask": 1}
                or len(parameters) < 5
                or parameters[4] != 0
                or not child.get("native_area_points")
            ):
                return []
            for dx, dy in oriented_area_offsets(
                child, origin=source, reference=source, direction=direction
            ):
                cell = (source[0] + dx, source[1] + dy, source[2])
                if (
                    cell in destinations
                    and cell != source
                    and native_area_contains(
                        child,
                        origin=source,
                        reference=source,
                        point=cell,
                        direction=direction,
                    )
                ):
                    if cell not in cells:
                        cells.append(cell)
    return cells[:4]
