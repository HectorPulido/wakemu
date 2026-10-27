"""Exact native area DTOs; directional shapes remain unrotated until each aim."""


def area_projection(effect):
    """Version1 means native float32 cardinal anchor-minus-reference rotation.

    Coincident aims use the actual caster's eight-way direction. Recipients
    use the native transpose transform followed by target-radius LOCAL offsets;
    forward enumerated cells are deliberately not a membership substitute.
    """
    from wakfu_server.combat_area_geometry import native_area_shape
    from wakfu_server.combat_effect_targets import area_offsets

    if "native_target_selector" not in effect:
        raise ValueError("Native area requires selector metadata")
    center_on_caster = effect["native_target_selector"] is None
    common = dict(
        nativeAreaCenterOnCaster=center_on_caster,
        nativeAreaUseTargetRadius=not center_on_caster,
    )
    shape = native_area_shape(effect)
    if shape is not None and not shape[1]:
        if len(shape[0]) > 4096:
            raise ValueError("Native directional area exceeds advisory offset budget")
        return dict(
            **common,
            fixedCells=[],
            nativeDirectionalArea=dict(
                version=1,
                rawOffsets=[list(point) for point in shape[0]],
                isotropic=False,
                centerOnCaster=center_on_caster,
                useTargetRadius=not center_on_caster,
            )
        )
    return dict(
        **common, fixedCells=[list(point) for point in sorted(area_offsets(effect))]
    )


def directional_geometry(row):
    """Validate this version before consuming its exact native raw offsets."""
    area = row.get("nativeDirectionalArea")
    if (
        not isinstance(area, dict)
        or type(area.get("version")) is not int
        or area["version"] != 1
        or area.get("isotropic") is not False
        or type(area.get("useTargetRadius")) is not bool
        or type(area.get("centerOnCaster")) is not bool
        or type(row.get("nativeAreaCenterOnCaster")) is not bool
        or type(row.get("nativeAreaUseTargetRadius")) is not bool
        or area["centerOnCaster"] != row["nativeAreaCenterOnCaster"]
        or area["useTargetRadius"] != row["nativeAreaUseTargetRadius"]
        or area["centerOnCaster"] == area["useTargetRadius"]
    ):
        return None
    raw = area.get("rawOffsets")
    if (
        not isinstance(raw, (list, tuple))
        or len(raw) > 4096
        or any(
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in point
            )
            for point in raw
        )
    ):
        return None
    return (
        frozenset(tuple(point) for point in raw),
        area["useTargetRadius"],
        area["centerOnCaster"],
    )


def directional_recipient(geometry, *, center, origin, point, radius, direction):
    """Exact transpose/local-radius membership, including diagonal self aims."""
    from wakfu_server.combat_area_geometry import native_area_rotation

    raw, use_radius, center_on_caster = geometry
    if not use_radius:
        radius = 0
    if type(radius) is not int or not -128 <= radius <= 127:
        raise ValueError("Native directional recipient requires signed-byte radius")
    radius = max(0, radius)
    anchor, reference = (origin, center) if center_on_caster else (center, origin)
    dx, dy = native_area_rotation(anchor, reference, direction)
    x, y = point[0] - anchor[0], point[1] - anchor[1]
    local_x, local_y = dx * x + dy * y, -dy * x + dx * y
    # Equivalent to searching every local radius offset, without a radius²
    # scan. Native raw membership is exact integer equality, never a circle.
    return any(
        abs(local_x - px) <= radius and abs(local_y - py) <= radius for px, py in raw
    )
