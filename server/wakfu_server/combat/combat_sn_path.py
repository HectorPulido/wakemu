"""Exact native Sn straight-path traversal over authoritative physical Vy columns."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from contextlib import nullcontext
from .combat_casting_range import int32
from .combat_conditions import UnknownCondition


@dataclass(frozen=True)
class NativePhysicalSurface:
    z: int
    bld: int
    ble: int
    blf: int
    thickness: int
    through: bool

    def __post_init__(self):
        for value, lower, upper in (
            (self.z, -32768, 32767),
            (self.bld, -128, 127),
            (self.ble, -128, 127),
            (self.blf, -32768, 32767),
            (self.thickness, -128, 127),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("Invalid native physical Vy field")
        if type(self.through) is not bool:
            raise ValueError("Missing native Vy.bLf authority")


def _murfin(start, end):
    """Sm.a(Vy,Vy), including signed bLE masks."""
    if start.ble == end.ble:
        return True
    if (start.ble & 48) != (end.ble & 48) and ((start.ble & 48) | (end.ble & 48)) != 48:
        return False
    if (start.ble & -208) == (end.ble & -208):
        return True
    mode, other = start.ble & 192, end.ble & 192
    same_id = (start.ble & 15) == (end.ble & 15)
    if mode == 0:
        return other in (0, 64)
    if mode == 128:
        return same_id and other in (128, 192)
    if mode == 64:
        return other in (0, 64) or (other == 192 and same_id)
    if mode == 192:
        return same_id and other in (64, 128, 192)
    return False


def native_sm_transitions(start_index, start, end, *, height, jump):
    """Return ordered Sm.boE entries; preserve native single/multiple branches."""
    source = start[start_index]
    accepted = []
    for index, candidate in enumerate(end):
        if candidate.bld == -1 or candidate.through:
            continue
        difference = candidate.z - source.z
        if not (source.blf & 64 and candidate.blf & 64) and abs(difference) > jump:
            continue
        if not _murfin(source, candidate):
            continue
        if len(end) == 1:
            if difference > 0 and start_index != len(start) - 1:
                ceiling = int32(candidate.z + height)
                for above in start[start_index + 1 :]:
                    if above.z - above.thickness >= ceiling:
                        break
                    if not above.through:
                        return ()
            return (index,)
        destination_ceiling = int32(candidate.z + height)
        combined_ceiling = max(destination_ceiling, int32(source.z + height))
        rejected = False
        for above in end[index + 1 :]:
            if above.z - above.thickness >= combined_ceiling:
                if difference <= 0 or start_index == len(start) - 1:
                    break
                for source_above in start[start_index + 1 :]:
                    if source_above.z - source_above.thickness >= destination_ceiling:
                        break
                    # Native bytecode reads candidate.bLf here, not source_above.
                    if not candidate.through:
                        rejected = True
                        break
                if not rejected:
                    break
            if rejected:
                break
            if not above.through:
                rejected = True
                break
        if not rejected:
            accepted.append(index)
            if len(accepted) > 32:
                # Native fixed Sm.boE[32] overflow is caught by Sn.a loop.
                raise IndexError("Native Sm transition buffer exceeded")
    return tuple(accepted)


class NativeSnPathAuthority:
    """Bound fcj callback. Columns and masks must represent the actual QI.

    target_exclusion supplies native unregister/restore scope when an actual
    target obstacle exists. It must not clear unrelated flags or infer actors.
    Private traversal caches disappear on return, the equivalent of Sn.bal.
    """

    def __init__(
        self,
        *,
        source,
        target,
        height,
        radius,
        jump,
        physical_column,
        qi_z=None,
        is_qi=None,
        target_obstacle_present=None,
        target_exclusion=None
    ):
        for value, minimum, maximum in (
            (height, -(1 << 31), (1 << 31) - 1),
            (radius, -128, 127),
            (jump, -32768, 32767),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Missing native Sn movement configuration")
        if type(is_qi) is not bool or type(target_obstacle_present) is not bool:
            raise UnknownCondition(
                "Missing actual native Sn environment or target identity"
            )
        if target_obstacle_present and not callable(target_exclusion):
            raise UnknownCondition(
                "Missing native target obstacle exclusion/restoration"
            )
        self.source, self.target = source, target
        self.height, self.radius, self.jump = height, radius, jump
        self.physical_column, self.qi_z = physical_column, qi_z
        self.is_qi = is_qi
        self.target_exclusion = (
            target_exclusion if target_obstacle_present else nullcontext
        )

    def __call__(self, path_option):
        if type(path_option) is not bool:
            raise ValueError("Missing selected native cwN flag")
        with self.target_exclusion():
            return self._walk(path_option)

    def _walk(self, path_option):
        source, target = self.source, self.target
        if source is None or target is None:
            return False
        for point in (source, target):
            if (
                not isinstance(point, (tuple, list))
                or len(point) != 3
                or any(type(value) is not int for value in point)
                or not all(-(1 << 31) <= value < (1 << 31) for value in point[:2])
                or not -32768 <= point[2] <= 32767
            ):
                raise UnknownCondition("Missing native Sn full aBn endpoints")
        if tuple(source) == tuple(target):
            return True
        if source[0] != target[0] and source[1] != target[1]:
            return False
        if not callable(self.physical_column):
            raise UnknownCondition("Missing actual ordered native Sn physical columns")
        if path_option and self.is_qi and not callable(self.qi_z):
            raise UnknownCondition("Missing actual native Sn QI.Z authority")
        axis = 1 if source[0] == target[0] else 0
        delta = int32(target[axis] - source[axis])
        distance = delta if delta == -(1 << 31) else abs(delta)
        direction = 1 if target[axis] > source[axis] else -1
        cache = {}
        surface_count = 0

        def column(x, y):
            nonlocal surface_count
            key = (x, y)
            if key not in cache:
                result = self.physical_column(x, y)
                if result is None:
                    cache[key] = ()
                elif not isinstance(result, (tuple, list)) or any(
                    not isinstance(row, NativePhysicalSurface) for row in result
                ):
                    raise UnknownCondition("Missing authoritative native Vy column")
                else:
                    surface_count += len(result)
                    if surface_count > 3072:
                        raise IndexError("Native Sn physical buffer exceeded")
                    cache[key] = tuple(result)
            return cache[key]

        x, y = source[:2]
        current = column(x, y)
        # VA.a finds the last exact short altitude, including blocked surfaces.
        index = next(
            (i for i in range(len(current) - 1, -1, -1) if current[i].z == source[2]),
            None,
        )
        if index is None:
            return False
        try:
            for _ in range(max(0, distance)):
                nx = int32(x + (direction if axis == 0 else 0))
                ny = int32(y + (direction if axis == 1 else 0))
                following = column(nx, ny)
                if not following:
                    return False
                destinations = native_sm_transitions(
                    index, current, following, height=self.height, jump=self.jump
                )
                if not destinations:
                    return False
                if path_option and self.is_qi:
                    blocked = self.qi_z(x, y)
                    if type(blocked) is not bool:
                        raise UnknownCondition("Missing exact native Sn QI.Z result")
                    if blocked:
                        return False
                x, y, current, index = nx, ny, following, destinations[0]
        except (IndexError, OverflowError):
            return False
        return True


class NativeSnColumns:
    """Complete ordered VB.a columns from the offline physical bulk export."""

    def __init__(self, data, *, map_id, source_sha256):
        if (
            not isinstance(data, dict)
            or data.get("schema") != "native-Sn-Vy-columns-v1"
            or type(map_id) is not int
            or map_id <= 0
            or type(data.get("map_id")) is not int
            or data.get("map_id") != map_id
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(char not in "0123456789abcdef" for char in source_sha256)
            or data.get("source_sha256") != source_sha256
            or not isinstance(data.get("chunks"), list)
        ):
            raise ValueError("Missing matching native Sn physical provenance")
        self.chunks = []
        self.map_id, self.source_sha256 = map_id, source_sha256
        seen_bounds = set()
        for chunk in data["chunks"]:
            if not isinstance(chunk, dict):
                raise ValueError("Missing complete native Sn physical chunk")
            bounds = tuple(chunk.get(key) for key in ("x", "y", "width", "height"))
            if (
                any(type(value) is not int for value in bounds)
                or bounds[2:] != (18, 18)
                or not all(-(1 << 31) <= value < (1 << 31) - 18 for value in bounds[:2])
                or bounds in seen_bounds
                or not isinstance(chunk.get("columns"), list)
            ):
                raise ValueError("Invalid native Sn physical chunk bounds")
            x, y, width, height = bounds
            for old_bounds, _ in self.chunks:
                ox, oy, ow, oh = old_bounds
                if x < ox + ow and ox < x + width and y < oy + oh and oy < y + height:
                    raise ValueError("Overlapping native Sn chunk bounds")
            seen_bounds.add(bounds)
            columns = {}
            for column in chunk["columns"]:
                if not isinstance(column, list) or len(column) != 3:
                    raise ValueError("Invalid native Sn ordered physical column")
                cx, cy, rows = column
                if (
                    type(cx) is not int
                    or type(cy) is not int
                    or not x <= cx < x + width
                    or not y <= cy < y + height
                    or (cx, cy) in columns
                    or not isinstance(rows, list)
                    or any(not isinstance(row, list) or len(row) != 6 for row in rows)
                ):
                    raise ValueError("Invalid native Sn ordered physical surfaces")
                columns[cx, cy] = tuple(NativePhysicalSurface(*row) for row in rows)
            self.chunks.append((bounds, columns))

    @classmethod
    def from_published(cls, map_id):
        """Load only the published protocol catalog; no private/runtime search."""
        import hashlib
        import json
        from pathlib import Path

        if type(map_id) is not int or map_id <= 0:
            raise ValueError("Invalid native Sn map identity")
        directory = Path(__file__).parents[2] / "protocol" / "native-sn-columns"
        try:
            publication = protocol_catalog.load(directory / "publication.json")
            manifest_bytes = protocol_catalog.read_bytes(directory / "manifest.json")
            if publication.get(
                "schema"
            ) != "native-Sn-publication-v1" or hashlib.sha256(
                manifest_bytes
            ).hexdigest() != publication.get(
                "bulk_manifest_sha256"
            ):
                raise ValueError("Native Sn publication manifest changed")
            manifest = json.loads(manifest_bytes)
            if manifest.get("schema") != "native-Sn-Vy-bulk-v1":
                raise ValueError("Wrong published native Sn bulk schema")
            rows = [
                row
                for row in manifest.get("maps", [])
                if row.get("status") == "exported" and row.get("map_id") == map_id
            ]
            if len(rows) != 1:
                raise UnknownCondition("No proven published native Sn physical map")
            row = rows[0]
            raw = protocol_catalog.read_bytes(directory / (str(map_id) + ".json"))
            if hashlib.sha256(raw).hexdigest() != row.get("output_sha256"):
                raise ValueError("Published native Sn physical map changed")
            return cls(
                json.loads(raw),
                map_id=map_id,
                source_sha256=row["source_sha256"],
            )
        except FileNotFoundError as error:
            raise UnknownCondition(
                "Missing published native Sn physical catalog"
            ) from error

    def column(self, x, y):
        if any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in (x, y)
        ):
            raise ValueError("Invalid native Sn physical coordinates")
        for (cx, cy, width, height), columns in self.chunks:
            if cx <= x < cx + width and cy <= y < cy + height:
                return columns.get((x, y), ())
        return None
