"""Native anI/anG raw offsets and anc/amX forward/transpose transforms.

Actor membership uses ana.o, while cell enumeration uses ana.n. For a
coincident origin/reference with diagonal facing these are deliberately not
inverse transforms in the client; do not substitute enumerated membership.
"""
import math
import re
from .combat_parameters import _float32

DIRECTIONS = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))


def native_area_shape(effect):
    kind, text = effect.get("area_class"), effect.get("area_native") or ""
    if kind in ("anE", "anJ") and "native_area_points" in effect:
        points = effect["native_area_points"]
        if not isinstance(points, (list, tuple)) or any(
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in point
            )
            for point in points
        ):
            raise ValueError("Invalid native ordered point area")
        return tuple(tuple(point) for point in points), False
    if kind == "anJ" and (match := re.fullmatch(r"t inv-barre:(\d+)-pied:(\d+)", text)):
        width, length = map(int, match.groups())
        points = [(0, 0)]
        for y in range(1, width + 1):
            points.extend(((0, y), (0, -y)))
        points.extend((x, 0) for x in range(1, length + 1))
        return tuple(points), False
    if kind == "anI" and (match := re.fullmatch(r"t-(\d+)-(\d+)", text)):
        width, length = map(int, match.groups())
        offsets = [(x, 0) for x in range(length + 1)]
        for y in range(1, width + 1):
            offsets.extend(((length, y), (length, -y)))
        return tuple(offsets), False
    if kind == "anG" and (
        match := re.fullmatch(r"rectangle or square-(\d+)x(\d+)", text)
    ):
        width, height = map(int, match.groups())
        if width and width % 2 == 0:
            width += 1
        if height and height % 2 == 0:
            height += 1
        return (
            tuple(
                (x - width // 2, y - height // 2)
                for x in range(width)
                for y in range(height)
            ),
            width == height,
        )
    return None


def native_area_rotation(origin, reference, direction):
    dx, dy = origin[0] - reference[0], origin[1] - reference[1]
    if not dx and not dy:
        if type(direction) is not int or not 0 <= direction < 8:
            raise ValueError(
                "Coincident native area origin requires authoritative actor facing"
            )
        return DIRECTIONS[direction]
    # aBA.g -> aBz.bp, atan2 converted to float before threshold comparison.
    angle = -_float32(math.atan2(_float32(dy), _float32(dx)))
    if _float32(math.pi / 4) <= angle < _float32(3 * math.pi / 4):
        return (0, -1)
    if _float32(-math.pi / 4) <= angle < _float32(math.pi / 4):
        return (1, 0)
    if _float32(-3 * math.pi / 4) <= angle < _float32(-math.pi / 4):
        return (0, 1)
    return (-1, 0)


def oriented_area_offsets(effect, *, origin, reference, direction=None):
    shape = native_area_shape(effect)
    if shape is None:
        raise ValueError("Unknown native oriented area")
    offsets, isotropic = shape
    if isotropic:
        return offsets
    dx, dy = native_area_rotation(origin, reference, direction)
    return tuple(dict.fromkeys((dx * x - dy * y, dy * x + dx * y) for x, y in offsets))


def native_area_contains(effect, *, origin, reference, point, direction=None, radius=0):
    shape = native_area_shape(effect)
    if shape is None:
        raise ValueError("Unknown native oriented area")
    offsets, isotropic = shape
    x, y = point[0] - origin[0], point[1] - origin[1]
    if not isotropic:
        dx, dy = native_area_rotation(origin, reference, direction)
        x, y = dx * x + dy * y, -dy * x + dx * y
    if type(radius) is not int or not -128 <= radius <= 127:
        raise ValueError("Native area membership requires signed-byte physical radius")
    radius = max(0, radius)
    raw = frozenset(offsets)
    return any(
        (x + dx, y + dy) in raw
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    )
