"""Ordered native Vy surfaces for QI.i/j, separate from movement and LOS."""
from dataclasses import dataclass
from .combat_qi_snapshot import NativeQISnapshot


@dataclass(frozen=True, slots=True)
class NativeSurface:
    z: int
    bld: int


class NativeQISurfaces:
    def __init__(self, data, *, map_id, source_sha256):
        if (
            type(map_id) is not int
            or map_id <= 0
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(char not in "0123456789abcdef" for char in source_sha256)
            or not isinstance(data, dict)
            or data.get("schema") != "native-QI-Vy-columns-v1"
            or data.get("map_id") != map_id
            or type(data.get("map_id")) is not int
            or data.get("source_sha256") != source_sha256
        ):
            raise ValueError("Missing matching native QI surface provenance")
        chunks = data.get("chunks")
        if not isinstance(chunks, list):
            raise ValueError("Missing complete ordered native QI chunks")
        self.chunks = []
        self.map_id, self.source_sha256 = map_id, source_sha256
        # Surface values are immutable and heavily repeated across a map. Keep
        # interning local to this provider, without retaining a global catalog.
        interned = {}
        for chunk in chunks:
            if not isinstance(chunk, dict):
                raise ValueError("Invalid native QI surface chunk")
            bounds = tuple(chunk.get(key) for key in ("x", "y", "width", "height"))
            if (
                any(type(value) is not int for value in bounds)
                or not -(1 << 31) <= bounds[0] < (1 << 31)
                or not -(1 << 31) <= bounds[1] < (1 << 31)
                or bounds[2] <= 0
                or bounds[3] <= 0
                or bounds[0] + bounds[2] >= (1 << 31)
                or bounds[1] + bounds[3] >= (1 << 31)
            ):
                raise ValueError("Native QI chunk bounds exceed proven domain")
            x, y, width, height = bounds
            columns = chunk.get("columns")
            if not isinstance(columns, list):
                raise ValueError("Missing complete native QI chunk columns")
            parsed = {}
            for column in columns:
                if not isinstance(column, list) or len(column) != 3:
                    raise ValueError("Invalid ordered native Vy column")
                cx, cy, surfaces = column
                if (
                    type(cx) is not int
                    or type(cy) is not int
                    or not x <= cx < x + width
                    or not y <= cy < y + height
                    or (cx, cy) in parsed
                    or not isinstance(surfaces, list)
                ):
                    raise ValueError("Invalid native Vy column coordinates")
                ordered = []
                for surface in surfaces:
                    if (
                        not isinstance(surface, list)
                        or len(surface) != 2
                        or type(surface[0]) is not int
                        or type(surface[1]) is not int
                        or not -32768 <= surface[0] <= 32767
                        or not -128 <= surface[1] <= 127
                    ):
                        raise ValueError("Invalid signed native Vy surface")
                    key = (surface[0], surface[1])
                    value = interned.get(key)
                    if value is None:
                        value = interned[key] = NativeSurface(*surface)
                    ordered.append(value)
                parsed[(cx, cy)] = tuple(ordered)
            self.chunks.append((bounds, parsed))

    def X(self, qi, x, y):
        """QI.X: mask-selected Vy.bbl in the first matching VD chunk."""
        if not isinstance(qi, NativeQISnapshot) or not qi.aK(x, y):
            raise ValueError("Native QI.X requires an in-bounds coordinate")
        index = qi.masks[(y - qi.y) * qi.width + x - qi.x] & 63
        for (cx, cy, width, height), columns in self.chunks:
            if cx <= x < cx + width and cy <= y < cy + height:
                ordered = columns.get((x, y), ())
                return -32768 if index >= len(ordered) else ordered[index].z
        return -32768

    def i(self, qi, x, y, z):
        if not isinstance(qi, NativeQISnapshot):
            raise ValueError("Missing actual serialized native QI masks")
        if type(z) is not int or not -32768 <= z <= 32767:
            raise ValueError("Invalid native QI requested short altitude")
        if not qi.aK(x, y):
            return None
        index = qi.masks[(y - qi.y) * qi.width + x - qi.x] & 63
        for (cx, cy, width, height), columns in self.chunks:
            if cx <= x < cx + width and cy <= y < cy + height:
                ordered = columns.get((x, y), ())
                if index >= len(ordered) or ordered[index].z != z:
                    return None
                return ordered[index]
        return None

    def j(self, qi, x, y, z):
        surface = self.i(qi, x, y, z)
        return surface is not None and surface.bld != -1
