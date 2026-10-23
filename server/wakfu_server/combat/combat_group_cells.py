"""eYg cell mode: ordered native parent area and selected fight heights.

anc/amX stores a LinkedHashSet in bEl insertion order. Isotropic families have
bEj=true, so amZ uses translation rather than orientation. Only the existing
proven point/empty/circle/ring/symmetric-cross geometry is accepted.
"""
import re
from .combat_effect_targets import area_offsets, UnsupportedEffectArea
from .combat_area_geometry import native_area_shape, oriented_area_offsets


def ordered_offsets(effect, *, origin=None, reference=None, direction=None):
    shape = native_area_shape(effect)
    if shape is not None:
        if shape[1]:
            return shape[0]
        if origin is None or reference is None:
            raise UnsupportedEffectArea(
                "Native group directional area requires caster/origin"
            )
        return oriented_area_offsets(
            effect, origin=origin, reference=reference, direction=direction
        )
    verified = area_offsets(effect)
    kind, description = effect.get("area_class"), effect.get("area_native")
    if kind == "anD":
        ordered = [(0, 0)]
    elif kind == "anA":
        ordered = []
    elif kind == "anu":
        radius = int(re.fullmatch(r"circle-(\d+)", description)[1])
        ordered = [
            (x, y)
            for x in range(-radius, radius + 1)
            for y in range(-(radius - abs(x)), radius - abs(x) + 1)
        ]
    elif kind == "anH":
        low, high = sorted(
            map(int, re.fullmatch(r"ring-(\d+)-(\d+)", description).groups())
        )
        ordered = []
        for x in range(high + 1):
            for y in range(max(0, low - x), max(0, high - x) + 1):
                ordered.append((x, y))
                if y:
                    ordered.append((x, -y))
                if x:
                    ordered.append((-x, y))
                    if y:
                        ordered.append((-x, -y))
    elif kind == "any":
        low, high = sorted(
            map(int, re.fullmatch(r"crossRing-(\d+)-(\d+)", description).groups())
        )
        ordered = [
            (dx * n, dy * n)
            for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
            for n in range(low, high + 1)
        ]
    elif kind == "anw":
        radius = int(re.fullmatch(r"cross-h(\d+)b(\d+)-g(\d+)d(\d+)", description)[1])
        ordered = [(0, 0)]
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
            ordered.extend((dx * n, dy * n) for n in range(1, radius + 1))
    elif kind == "anx":
        top, bottom, left, right = map(
            int,
            re.fullmatch(
                r"crossDiag-h(-?\d+)b(-?\d+)-g(-?\d+)d(-?\d+)", description
            ).groups(),
        )
        # Original anx.p appends center, g, d, h, b; bEj=true means world XY.
        # Its positive-index loops preserve empty nonpositive arms.
        ordered = [(0, 0)]
        for length, (dx, dy) in (
            (left, (-1, 1)),
            (right, (1, -1)),
            (top, (-1, -1)),
            (bottom, (1, 1)),
        ):
            ordered.extend((dx * n, dy * n) for n in range(1, length + 1))
    else:
        raise UnsupportedEffectArea("Missing native group area order")
    # Verify no accidental difference with the resolver's proven geometry.
    if frozenset(ordered) != verified:
        raise UnsupportedEffectArea(
            "Ordered native area disagrees with target geometry"
        )
    return tuple(dict.fromkeys(ordered))


def group_cells(fight, effect, center, *, caster_id=None):
    """eYg.at uses QI.R, QI.X and aK before dispatching each child.

    Own fight bootstrap has one selected native height per registered terrain
    cell. Missing columns are excluded, and ambiguous columns are rejected.
    Occupants do not make these cells invalid; child selectors decide targets.
    """
    heights = {}
    for x, y, z in fight.walkable:
        if (x, y) in heights and heights[x, y] != z:
            raise ValueError(
                "Group routing requires one native fight altitude per column"
            )
        if z == -32768:
            continue
        heights[x, y] = z
    x, y, _ = center
    reference, direction = None, None
    shape = native_area_shape(effect)
    if shape is not None and not shape[1]:
        caster = fight.actors.get(caster_id)
        if caster is None:
            from .combat_effect_area_targets import retained_area_source_target

            caster = retained_area_source_target(fight, caster_id)
        if caster is None:
            raise ValueError("Native directional group area requires caster snapshot")
        reference, direction = caster.position, getattr(caster, "direction", None)
    return tuple(
        (x + dx, y + dy, heights[x + dx, y + dy])
        for dx, dy in ordered_offsets(
            effect, origin=center, reference=reference, direction=direction
        )
        if (x + dx, y + dy) in heights
    )
