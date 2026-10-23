"""Native anI/anG raw offsets and anc/amX forward/transpose transforms.

Actor membership uses ana.o, while cell enumeration uses ana.n. For a
coincident origin/reference with diagonal facing these are deliberately not
inverse transforms in the client; do not substitute enumerated membership.
"""
import math
import re
from functools import lru_cache
from .combat_parameters import _float32

DIRECTIONS = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))


def _build_native_area_shape(effect):
    kind, text = effect.get("area_class"), effect.get("area_native") or ""
    if kind == "anz" and (
        match := re.fullmatch(r"Directed rectangle-(\d+)x(\d+)", text)
    ):
        width, length = map(int, match.groups())
        # anz.bEm prints 2*aNn+1, not the constructor's half-width.
        # anz.bEx preserves Y-major order; anc owns all orientation.
        if width < 1 or width % 2 != 1 or length < 1 or max(width, length) >= (1 << 31):
            raise ValueError("Invalid native directed rectangle dimensions")
        half_width = width // 2
        return (
            tuple(
                (x, y)
                for y in range(-half_width, half_width + 1)
                for x in range(length)
            ),
            False,
        )
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
    if kind == "anC" and (match := re.fullmatch(r"cone_inv-(-?\d+)", text)):
        height = int(match.group(1))
        if not -(1 << 31) <= height < (1 << 31):
            raise ValueError("Native inverse cone height must be int32")
        # anC.p reverses the X rows; anc orientation/membership is inherited.
        return (
            tuple(
                (height - 1 - row, y)
                for row in range(height)
                for y in range(-row, row + 1)
            ),
            False,
        )
    if kind == "anv" and (match := re.fullmatch(r"cone-(-?\d+)", text)):
        height = int(match.group(1))
        if not -(1 << 31) <= height < (1 << 31):
            raise ValueError("Native cone height must be int32")
        # anv.p: x starts at0 and is strictly below height; rows contain
        # every y=-x..x. Nonpositive heights preserve native empty geometry.
        return tuple((x, y) for x in range(height) for y in range(-x, x + 1)), False
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
    if kind == "anF" and (
        match := re.fullmatch(
            r"rectangular or square ring-w:(-?\d+)-(-?\d+) / h:(-?\d+)-(-?\d+)", text
        )
    ):
        inner_x, outer_x, inner_y, outer_y = map(int, match.groups())
        if inner_x > outer_x or inner_y > outer_y:
            raise ValueError("Invalid native rectangular ring bounds")
        points = []
        # anF.p preserves quadrant order and includes the inner boundary.
        for x in range(outer_x + 1):
            for y in range(outer_y + 1):
                if x < inner_x and y < inner_y:
                    continue
                points.append((x, y))
                if x:
                    points.append((-x, y))
                if y:
                    points.append((x, -y))
                if x and y:
                    points.append((-x, -y))
        # anF.bEj always false, even for a square: retain native orientation.
        return tuple(points), False
    return None


def _cacheable_area_text(text):
    # Bound retained coordinate populations, not accepted gameplay geometry.
    # Larger/custom descriptions still execute through the uncached builder.
    return (
        type(text) is str
        and len(text) <= 160
        and all(abs(int(value)) <= 32 for value in re.findall(r"-?\d+", text))
    )


def _shape_identity(effect):
    kind, text = effect.get("area_class"), effect.get("area_native") or ""
    if type(kind) is not str or not _cacheable_area_text(text):
        return None
    points = None
    if kind in ("anE", "anJ") and "native_area_points" in effect:
        points = effect["native_area_points"]
        if (
            not isinstance(points, (list, tuple))
            or len(points) > 4096
            or any(
                not isinstance(point, (list, tuple))
                or len(point) != 2
                or any(
                    type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                    for value in point
                )
                for point in points
            )
        ):
            return None
        points = tuple(tuple(point) for point in points)
    return kind, text, points


def _shape_data(effect):
    shape = _build_native_area_shape(effect)
    return shape, None if shape is None else frozenset(shape[0])


@lru_cache(maxsize=128)
def _cached_shape_data(kind, text, points):
    effect = {"area_class": kind, "area_native": text}
    if points is not None:
        effect["native_area_points"] = points
    return _shape_data(effect)


def _native_area_data(effect):
    identity = _shape_identity(effect)
    return _shape_data(effect) if identity is None else _cached_shape_data(*identity)


def native_area_shape(effect):
    """Reuse immutable offsets by full shape content, never effect identity."""
    identity = _shape_identity(effect)
    if identity is None:
        return _build_native_area_shape(effect)
    return _cached_shape_data(*identity)[0]


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


def _oriented_offsets(offsets, dx, dy):
    return tuple(dict.fromkeys((dx * x - dy * y, dy * x + dx * y) for x, y in offsets))


@lru_cache(maxsize=256)
def _cached_oriented_offsets(identity, dx, dy):
    shape, _ = _cached_shape_data(*identity)
    offsets = _oriented_offsets(shape[0], dx, dy)
    return offsets, frozenset(offsets)


def oriented_area_offsets(effect, *, origin, reference, direction=None):
    shape = native_area_shape(effect)
    if shape is None:
        raise ValueError("Unknown native oriented area")
    offsets, isotropic = shape
    if isotropic:
        return offsets
    dx, dy = native_area_rotation(origin, reference, direction)
    identity = _shape_identity(effect)
    if identity is not None:
        return _cached_oriented_offsets(identity, dx, dy)[0]
    return _oriented_offsets(offsets, dx, dy)


def oriented_area_offset_set(effect, *, origin=None, reference=None, direction=None):
    """Immutable enumerated cells; do not substitute for transpose membership."""
    shape, raw = _native_area_data(effect)
    if shape is None:
        raise ValueError("Unknown native oriented area")
    offsets, isotropic = shape
    if isotropic:
        return raw
    dx, dy = native_area_rotation(origin, reference, direction)
    identity = _shape_identity(effect)
    if identity is not None:
        return _cached_oriented_offsets(identity, dx, dy)[1]
    return frozenset(_oriented_offsets(offsets, dx, dy))


def native_area_contains(effect, *, origin, reference, point, direction=None, radius=0):
    shape, raw = _native_area_data(effect)
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
    return any(
        (x + dx, y + dy) in raw
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    )
