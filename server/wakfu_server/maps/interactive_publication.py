"""Per-peer native interactive attachment and retained-state publication.

The caller serializes transform and socket writes with its connection write lock.
Native nonautomatic assets require one 13984 attachment per loaded partition;
12344 mutates retained instances without attaching duplicates.
"""

import math
import struct


def refresh_snapshots(body):
    """Share the native snapshot decoder without importing map catalogs."""
    from .scene_wire_native import refresh_snapshots as decode

    return decode(body)


def resource_cell(opcode, body, *, planting_only=False):
    """Recognize qualified native resource coordinates; unknown layouts pass."""
    if opcode == 12782:
        return struct.unpack_from(">ii", body) if len(body) == 24 else None
    if opcode != 13135:
        return None
    cursor = 0
    coordinates = {}
    fields = {}
    planting_layout = True

    def varint():
        nonlocal cursor, planting_layout
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
                if index and byte == 0:
                    planting_layout = False
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
                if field not in range(1, 9) or field in fields:
                    planting_layout = False
                fields[field] = value
                if field in (2, 3):
                    value = value - (1 << 64) if value >= 1 << 63 else value
                    if not -(1 << 31) <= value < (1 << 31):
                        return None
                    coordinates[field] = value
            elif kind in (1, 2, 5):
                planting_layout = False
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
    if planting_only:
        # Qualify only planting.resource_packet's complete public zk layout.
        # Other protobuf forms remain visible but are never deduplicated.
        if (
            not planting_layout
            or tuple(fields) != tuple(range(1, 9))
            or not 0 < fields[1] < 1 << 31
            or not 0 <= fields[5] < 128
            or any(fields[field] != 0 for field in (6, 7, 8))
        ):
            return None
        altitude = fields[4] - (1 << 64) if fields[4] >= 1 << 63 else fields[4]
        if not -(1 << 15) <= altitude < 1 << 15:
            return None
    return (coordinates[2], coordinates[3]) if set(coordinates) == {2, 3} else None


def _resource_appearance(body):
    """Read only the already qualified eight public varint fields.

    Keep publication independent of inventory/world catalogs: this boundary
    must also run during ordinary socket writes before gameplay initialization.
    """
    if resource_cell(13135, body, planting_only=True) is None:
        return None
    fields = {}
    cursor = 0
    while cursor < len(body):
        field = body[cursor] >> 3  # Qualified tags 8--64 occupy one byte.
        cursor += 1
        value, shift = 0, 0
        while True:
            byte = body[cursor]
            cursor += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                break
            shift += 7
        fields[field] = value
    return fields


def _resource_stage_body(body, stage):
    cursor = 0
    while cursor < len(body):
        tag = body[cursor]
        start = cursor + 1
        cursor = start
        while body[cursor] & 128:
            cursor += 1
        cursor += 1
        if tag == 40:
            return body[:start] + bytes((stage,)) + body[cursor:]
    raise ValueError("Public resource appearance has no stage")


def _resource_stage_packet(body, stage):
    fields = _resource_appearance(body)
    if fields is None:
        raise ValueError("Unknown public resource appearance")
    signed = lambda value: value - (1 << 64) if value >= 1 << 63 else value
    return _frame(
        12782,
        struct.pack(
            ">iihhqi",
            signed(fields[2]),
            signed(fields[3]),
            signed(fields[4]),
            stage,
            0,
            0,
        ),
    )


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
        trace_limit=512,
        attachment_projector=None,
    ):
        self.catalog = catalog
        self.trace = trace
        self.trace_ids = None if trace_ids is None else frozenset(trace_ids)
        self.trace_account_id = trace_account_id
        self.trace_limit = max(0, int(trace_limit))
        self.trace_count = 0
        self.attachment_projector = attachment_projector
        self._catalog_cache = {}
        self.clear()

    def clear(self):
        self.identity = None
        self.visible = None
        self.attached = set()
        self.resource_appearances = {}

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
            opcode in (13984, 12344, 12318, 13256, 13974, 13135, 12782)
            for opcode, _, _, _ in frames
        ):
            return data
        identity = tuple(scope.get(key) for key in _SCOPE_FIELDS)
        visible = self.visible if identity == self.identity else None
        attached = set(self.attached) if identity == self.identity else set()
        resource_appearances = (
            dict(self.resource_appearances) if identity == self.identity else {}
        )
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
            # Native ciu handles every 13974 by clearing cdE, even when the
            # map and instance are unchanged and no 13256 precedes it.
            if opcode in (13256, 13974):
                attached.clear()
                resource_appearances.clear()
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
                resource_appearances = {
                    position: payload
                    for position, payload in resource_appearances.items()
                    if (math.floor(position[0] / 18), math.floor(position[1] / 18))
                    in visible
                }
                output.append(original)
            elif opcode in (13135, 12782):
                position = resource_cell(opcode, body)
                if position is None:
                    # Unknown resource traffic cannot certify that a previous
                    # appearance still exists, including unknown12782 retirements.
                    resource_appearances.clear()
                    output.append(original)
                elif visible is not None:
                    cell = (math.floor(position[0] / 18), math.floor(position[1] / 18))
                    if cell in visible:
                        if opcode == 12782:
                            _x, _y, _z, stage, owner, metadata = struct.unpack(
                                ">iihhqi", body
                            )
                            previous = resource_appearances.get(position)
                            if (
                                previous is not None
                                and 0 < stage < 128
                                and owner == metadata == 0
                            ):
                                # cFJ mutates the resource already registered at
                                # XY. Only stage zero starts native retirement;
                                # growth must not forget this peer's appearance.
                                resource_appearances[position] = _resource_stage_body(
                                    previous, stage
                                )
                            else:
                                resource_appearances.pop(position, None)
                        elif (
                            resource_cell(opcode, body, planting_only=True) is not None
                        ):
                            previous = resource_appearances.get(position)
                            if previous == body:
                                continue
                            before = (
                                _resource_appearance(previous)
                                if previous is not None
                                else None
                            )
                            after = _resource_appearance(body)
                            if before is not None and all(
                                before[field] == after[field]
                                for field in (1, 2, 3, 4, 6, 7, 8)
                            ):
                                # A snapshot of an existing resource's new
                                # stage is a native cFJ update, not another
                                # cFL constructor at the occupied XY.
                                output.append(_resource_stage_packet(body, after[5]))
                                if after[5] == 0:
                                    resource_appearances.pop(position, None)
                                else:
                                    resource_appearances[position] = body
                                continue
                            resource_appearances[position] = body
                        else:
                            resource_appearances.pop(position, None)
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
                        projected = (
                            None
                            if self.attachment_projector is None
                            else self.attachment_projector(row, scope)
                        )
                        if projected is None:
                            additions.append(record)
                        else:
                            output.append(_frame(*projected))
                        attached.add(object_id)
                        emit_event(
                            object_id,
                            opcode,
                            13984 if projected is None else projected[0],
                            "attach",
                        )
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
        self.resource_appearances = resource_appearances
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
