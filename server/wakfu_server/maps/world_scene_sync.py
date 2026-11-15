"""Bounded dynamic hydration after movement loads native scene partitions.

Native Vc/Ve partitions are 18 cells square with a 3x3 visible neighborhood.
Updates to unloaded objects are discarded by cEX/bEG and cdy removes their
registry entries on unload. Replay dynamic state while an accepted walk loads
its partitions; never continuously resend a whole map or its base geometry.
"""

import weakref
from wakfu_server import world_static, dungeon_instances
from .movement import _default_native, _release_native


def _coordinates(position):
    # Full characters include binary inventory and achievement sections.
    return (
        (position["x"], position["y"]) if isinstance(position, dict) else position[:2]
    )


def chunk(position):
    return tuple(
        _default_native().call("navigation.chunk", position=_coordinates(position))
    )


def neighborhood(center):
    return frozenset(
        tuple(row)
        for row in _default_native().call("navigation.neighborhood", center=center)
    )


def _chunk_snapshots(map_id, selected_chunk, entrances):
    from .scene_wire_native import selected_snapshots

    return selected_snapshots(map_id, (selected_chunk,), entrances)


def dynamic_snapshots(map_id, chunks):
    """Select all loaded partitions in one native immutable-index lookup."""
    from .scene_wire_native import selected_snapshots

    return selected_snapshots(
        map_id, chunks, dungeon_instances.entry_object_ids(map_id)
    )


def snapshot_ids(bodies):
    from .scene_wire_native import snapshot_ids as native_snapshot_ids

    return native_snapshot_ids(bodies)


def refresh_snapshots(body):
    from .scene_wire_native import refresh_snapshots as native_refresh_snapshots

    return native_refresh_snapshots(body)


class SceneSync:
    """Socket/catalog adapter for a Rust-owned finite replay schedule."""

    def __init__(self, *, native=None):
        self._spatial = _default_native() if native is None else native
        self._handle = self._spatial.call("navigation.scene_new")["handle"]
        self._finalizer = weakref.finalize(
            self, _release_native, self._spatial, "navigation.scene_drop", self._handle
        )

    def _state(self):
        return self._spatial.call("navigation.scene_state", handle=self._handle)

    @property
    def identity(self):
        identity = self._state()["identity"]
        return None if identity is None else tuple(identity)

    @property
    def pending(self):
        return {
            due: frozenset(tuple(region) for region in regions)
            for due, regions in self._state()["pending"]
        }

    @property
    def last_regions(self):
        return frozenset(tuple(region) for region in self._state()["last_regions"])

    def clear(self):
        self._spatial.call("navigation.scene_clear", handle=self._handle)

    def arm(self, map_id, instance_id, steps, now):
        self._spatial.call(
            "navigation.scene_arm",
            handle=self._handle,
            map_id=map_id,
            instance_id=instance_id,
            steps=[_coordinates(step) for step in steps],
            now=now,
        )

    def poll(self, map_id, instance_id, now):
        result = self._spatial.call(
            "navigation.scene_poll",
            handle=self._handle,
            map_id=map_id,
            instance_id=instance_id,
            now=now,
        )
        regions = frozenset(tuple(region) for region in result["regions"])
        return dynamic_snapshots(map_id, regions) if regions else ()
