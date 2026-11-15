"""Binary scene snapshots; immutable catalog inputs, native bounded indexes."""

from functools import lru_cache
from collections import OrderedDict
import threading
import struct
from types import MappingProxyType

from .spatial_native import NativeSpatialError, get_spatial


class _SourceIdentity:
    def __init__(self, source):
        self.source = source

    def __hash__(self):
        return id(self.source)

    def __eq__(self, other):
        return isinstance(other, _SourceIdentity) and self.source is other.source


def _call(op, buffers=(), integers=()):
    return get_spatial().call_binary(op, buffers=buffers, integers=integers)


def _unpack_list(data):
    if len(data) < 4:
        raise RuntimeError("Native scene result lacks its count")
    count = struct.unpack_from(">I", data)[0]
    rows, cursor = [], 4
    for _ in range(count):
        if cursor + 4 > len(data):
            raise RuntimeError("Native scene result is truncated")
        size = struct.unpack_from(">I", data, cursor)[0]
        cursor += 4
        if size > len(data) - cursor:
            raise RuntimeError("Native scene result has an invalid length")
        rows.append(data[cursor : cursor + size])
        cursor += size
    if cursor != len(data):
        raise RuntimeError("Native scene result has trailing bytes")
    return tuple(rows)


def _register(map_id, entrances):
    from wakfu_server import world_static, native_catalog

    # Only cold registration reads the whole immutable map. Patched fixture
    # providers remain content-addressed and deliberately bypass the fast cache.
    rows = world_static.objects(map_id)
    positions = b"".join(struct.pack(">dd", row["x"], row["y"]) for row in rows)
    return _call(
        10,
        buffers=(
            native_catalog.release().encode(),
            world_static._DUNGEON_ENTRY_STATE,
            positions,
            *(
                (
                    world_static._DUNGEON_ENTRY_STATE
                    if row["id"] in entrances
                    else world_static.dynamic_state(map_id, row["id"])
                )
                for row in rows
            ),
        ),
        integers=(
            map_id,
            len(rows),
            len(entrances),
            *(row["id"] for row in rows),
            *entrances,
        ),
    )


@lru_cache(maxsize=64)
def _registered(
    map_id,
    source_identity,
    revision,
    entrances,
    object_provider,
    state_provider,
    override_payload,
):
    return _register(map_id, entrances)


def _select(
    map_id,
    source_identity,
    revision,
    entrances,
    object_provider,
    state_provider,
    chunks,
    override_payload,
):
    immutable = source_identity is not None

    def key():
        if immutable:
            return _registered(
                map_id,
                source_identity,
                revision,
                entrances,
                object_provider,
                state_provider,
                override_payload,
            )
        return _register(map_id, entrances)

    integers = tuple(axis for selected in chunks for axis in selected)
    try:
        return _unpack_list(_call(11, buffers=(key(),), integers=integers))
    except NativeSpatialError as error:
        if error.code != "scene_cache_miss":
            raise
        _registered.cache_clear()
        return _unpack_list(_call(11, buffers=(key(),), integers=integers))


_FINISHED_LIMIT = 32 * 1024 * 1024
_finished = OrderedDict()
_finished_bytes = 0
_finished_lock = threading.Lock()


def _selected_cached(
    map_id,
    source_identity,
    revision,
    entrances,
    object_provider,
    state_provider,
    chunks,
    override_payload,
):
    # Cache final immutable bytes, with both entry and byte bounds. The native
    # module remains the only owner of spatial partition membership.
    global _finished_bytes
    key = (
        map_id,
        source_identity,
        revision,
        entrances,
        object_provider,
        state_provider,
        chunks,
        override_payload,
    )
    with _finished_lock:
        found = _finished.get(key)
        if found is not None:
            _finished.move_to_end(key)
            return found
    result = _select(*key)
    size = sum(map(len, result))
    if size > _FINISHED_LIMIT:
        return result
    with _finished_lock:
        if key in _finished:
            return _finished[key]
        while _finished and (
            len(_finished) >= 4096 or _finished_bytes + size > _FINISHED_LIMIT
        ):
            _, old = _finished.popitem(last=False)
            _finished_bytes -= sum(map(len, old))
        _finished[key] = result
        _finished_bytes += size
    return result


def selected_snapshots(map_id, chunks, entrances):
    from wakfu_server import world_static, native_catalog

    entrances = tuple(sorted(entrances))
    chunks = tuple(tuple(point) for point in chunks)
    if any(
        len(point) != 2 or any(type(axis) is not int for axis in point)
        for point in chunks
    ):
        raise ValueError("Scene partitions require two integer coordinates")
    chunks = tuple(sorted(set(chunks)))
    if not chunks:
        return ()
    source = world_static._MAPS.get(map_id)
    immutable = (
        isinstance(source, MappingProxyType)
        and isinstance(world_static._DYNAMIC_STATES, MappingProxyType)
        and world_static.objects is world_static._IMMUTABLE_OBJECT_PROVIDER
        and world_static.dynamic_state is world_static._IMMUTABLE_STATE_PROVIDER
    )
    select = _selected_cached if immutable else _select
    return select(
        map_id,
        (
            (_SourceIdentity(source), _SourceIdentity(world_static._DYNAMIC_STATES))
            if immutable
            else None
        ),
        native_catalog.release(),
        entrances,
        world_static.objects,
        world_static.dynamic_state,
        chunks,
        world_static._DUNGEON_ENTRY_STATE,
    )


def snapshot_bodies(rows, entrance_ids=()):
    from wakfu_server import world_static

    entrances = frozenset(entrance_ids)
    rows = tuple(rows)
    return _unpack_list(
        _call(
            12,
            buffers=tuple(
                (
                    world_static._DUNGEON_ENTRY_STATE
                    if row["id"] in entrances
                    else (
                        row["payload"]
                        if "payload" in row
                        else bytes.fromhex(row["payload_hex"])
                    )
                )
                for row in rows
            ),
            integers=tuple(row["id"] for row in rows),
        )
    )


def snapshot_ids(bodies):
    result = _call(13, buffers=tuple(bodies))
    if len(result) % 8:
        raise RuntimeError("Native scene identity output is malformed")
    return [value[0] for value in struct.iter_unpack(">q", result)]


def refresh_snapshots(body):
    return _unpack_list(_call(14, buffers=(body,)))


def resource_packets(rows, chunks=None):
    rows = tuple(rows)
    selected = () if chunks is None else tuple(chunks)
    integers = (
        -1 if chunks is None else len(selected),
        len(rows),
        *(axis for point in selected for axis in point),
        *(
            row[key]
            for row in rows
            for key in ("resource_reference", "x", "y", "z", "stage")
        ),
    )
    return [(13135, body) for body in _unpack_list(_call(15, integers=integers))]
