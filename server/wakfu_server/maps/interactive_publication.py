"""Per-peer native interactive attachment and retained-state publication.

The caller serializes transform and socket writes with its connection write lock.
Native nonautomatic assets require one 13984 attachment per loaded partition;
12344 mutates retained instances without attaching duplicates.
"""
import math
import struct


def refresh_snapshots(body):
    """Decode the same validated records as world_scene_sync without catalog IO."""
    if len(body) < 2:
        raise ValueError("Truncated interactive snapshot count")
    count = struct.unpack_from(">h", body)[0]
    if count < 0:
        raise ValueError("Negative interactive snapshot count")
    records = []
    cursor = 2
    for _ in range(count):
        if len(body) - cursor < 10:
            raise ValueError("Truncated interactive snapshot record")
        _, size = struct.unpack_from(">qH", body, cursor)
        if size == 0 or size > len(body) - cursor - 10:
            raise ValueError("Invalid interactive snapshot payload length")
        records.append(body[cursor : cursor + 10 + size])
        cursor += 10 + size
    if cursor != len(body):
        raise ValueError("Trailing interactive snapshot data")
    return tuple(records)


def resource_cell(opcode, body):
    """Recognize qualified native resource coordinates; unknown layouts pass."""
    if opcode == 12782:
        return struct.unpack_from(">ii", body) if len(body) == 24 else None
    if opcode != 13135:
        return None
    cursor = 0
    coordinates = {}

    def varint():
        nonlocal cursor
        value = 0
        for index in range(10):
            if cursor == len(body):
                raise ValueError("Truncated resource varint")
            byte = body[cursor]
            cursor += 1
            if index == 9 and byte > 1:
                raise ValueError("Overflowing resource varint")
            value |= (byte & 127) << (index * 7)
            if not byte & 128:
                return value
        raise ValueError("Unterminated resource varint")

    try:
        while cursor < len(body):
            tag = varint()
            field, kind = tag >> 3, tag & 7
            if not field or field > (1 << 29) - 1:
                return None
            if kind == 0:
                value = varint()
                if field in (2, 3):
                    value = value - (1 << 64) if value >= 1 << 63 else value
                    if not -(1 << 31) <= value < (1 << 31):
                        return None
                    coordinates[field] = value
            elif kind in (1, 2, 5):
                if field in (2, 3):
                    return None
                length = varint() if kind == 2 else (8 if kind == 1 else 4)
                if length > len(body) - cursor:
                    return None
                cursor += length
            else:
                return None
    except ValueError:
        return None
    return (coordinates[2], coordinates[3]) if set(coordinates) == {2, 3} else None


_SCOPE_FIELDS = ("session_id", "generation", "account_id", "map_id", "instance_id")


def _frame(opcode, body):
    return struct.pack(">IH", len(body) + 6, opcode) + body


class InteractivePublication:
    def __init__(
        self,
        catalog,
        trace=None,
        *,
        trace_ids=None,
        trace_account_id=None,
        trace_limit=512
    ):
        self.catalog = catalog
        self.trace = trace
        self.trace_ids = None if trace_ids is None else frozenset(trace_ids)
        self.trace_account_id = trace_account_id
        self.trace_limit = max(0, int(trace_limit))
        self.trace_count = 0
        self._catalog_cache = {}
        self.clear()

    def clear(self):
        self.identity = None
        self.visible = None
        self.attached = set()

    def transform(self, data, scope):
        """Validate an entire framed write before committing publication state."""
        if not scope:
            return data
        frames = []
        cursor = 0
        while cursor < len(data):
            if len(data) - cursor < 6:
                raise ValueError("Truncated outgoing frame")
            length, opcode = struct.unpack_from(">IH", data, cursor)
            if length < 6 or length > len(data) - cursor:
                raise ValueError("Invalid outgoing frame length")
            body = data[cursor + 6 : cursor + length]
            records = refresh_snapshots(body) if opcode == 13984 else None
            if opcode == 12318 and len(body) != 8:
                raise ValueError("Invalid interactive loader position")
            frames.append((opcode, body, records, data[cursor : cursor + length]))
            cursor += length
        if not any(
            opcode in (13984, 12344, 12318, 13256, 13135, 12782)
            for opcode, _, _, _ in frames
        ):
            return data
        identity = tuple(scope.get(key) for key in _SCOPE_FIELDS)
        visible = self.visible if identity == self.identity else None
        attached = set(self.attached) if identity == self.identity else set()
        map_id = scope.get("map_id")
        if map_id not in self._catalog_cache:
            self._catalog_cache[map_id] = {
                row["id"]: dict(row) for row in self.catalog(map_id)
            }
        rows = self._catalog_cache[map_id]
        output = []
        events = []

        def emit_event(object_id, source, opcode, operation):
            events.append(
                dict(
                    scope,
                    id=object_id,
                    source_opcode=source,
                    opcode=opcode,
                    operation=operation,
                )
            )

        for opcode, body, records, original in frames:
            if opcode == 13256:
                attached.clear()
                visible = None
                output.append(original)
            elif opcode == 12318:
                x, y = struct.unpack(">ii", body)
                cx, cy = math.floor(x / 18), math.floor(y / 18)
                visible = frozenset(
                    (cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                )
                retained = set()
                for object_id in attached:
                    row = rows[object_id]
                    cell = (math.floor(row["x"] / 18), math.floor(row["y"] / 18))
                    if cell in visible:
                        retained.add(object_id)
                    else:
                        emit_event(object_id, 12318, None, "unload")
                attached = retained
                output.append(original)
            elif opcode in (13135, 12782):
                position = resource_cell(opcode, body)
                if position is None:
                    output.append(original)
                elif visible is not None:
                    cell = (math.floor(position[0] / 18), math.floor(position[1] / 18))
                    if cell in visible:
                        output.append(original)
            elif opcode == 13984:
                additions = []
                updates = []
                for record in records:
                    object_id = struct.unpack_from(">q", record)[0]
                    row = rows.get(object_id)
                    if row is None:
                        additions.append(record)
                        emit_event(object_id, opcode, 13984, "passthrough")
                        continue
                    cell = (math.floor(row["x"] / 18), math.floor(row["y"] / 18))
                    if visible is None:
                        emit_event(object_id, opcode, None, "awaiting_loader")
                        continue
                    if cell not in visible:
                        emit_event(object_id, opcode, None, "outside_visible")
                        continue
                    if row.get("auto", False) or object_id in attached:
                        updates.append(record)
                        emit_event(object_id, opcode, 12344, "update")
                    else:
                        additions.append(record)
                        attached.add(object_id)
                        emit_event(object_id, opcode, 13984, "attach")
                if additions:
                    output.append(
                        _frame(
                            13984,
                            struct.pack(">h", len(additions)) + b"".join(additions),
                        )
                    )
                output.extend(_frame(12344, record) for record in updates)
            else:
                output.append(original)
                if opcode == 12344 and len(body) >= 10:
                    object_id, size = struct.unpack_from(">qH", body)
                    if size == len(body) - 10:
                        emit_event(object_id, opcode, opcode, "update")
        result = b"".join(output)
        self.identity, self.visible, self.attached = identity, visible, attached
        for event in events:
            if (
                self.trace is None
                or self.trace_count >= self.trace_limit
                or self.trace_ids is not None
                and event["id"] not in self.trace_ids
                or self.trace_account_id is not None
                and event.get("account_id") != self.trace_account_id
            ):
                continue
            self.trace_count += 1
            self.trace(event)
        return result
