"""Bounded dynamic hydration after movement loads native scene partitions.

Native Vc/Ve partitions are 18 cells square with a 3x3 visible neighborhood.
Updates to unloaded objects are discarded by cEX/bEG and cdy removes their
registry entries on unload. Replay dynamic state while an accepted walk loads
its partitions; never continuously resend a whole map or its base geometry.
"""
import math
import struct
from functools import lru_cache
from wakfu_server import world_static, dungeon_instances

CHUNK_SIZE = 18
STEP_SECONDS = 0.5
RETRY_SECONDS = 1.0
TAIL_SECONDS = 3.0
MAX_STEPS = 256


def chunk(position):
    if isinstance(position, dict):
        x, y = position["x"], position["y"]
    else:
        x, y = position[:2]
    return math.floor(x / CHUNK_SIZE), math.floor(y / CHUNK_SIZE)


def neighborhood(center):
    x, y = center
    return frozenset((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))


@lru_cache(maxsize=4096)
def _chunk_snapshots(map_id, selected_chunk, entrances):
    """Cache immutable bytes per asset partition and current route identities."""
    rows = tuple(
        {
            "id": row["id"],
            "payload_hex": (
                world_static._DUNGEON_ENTRY_STATE
                if row["id"] in entrances
                else world_static.dynamic_state(map_id, row["id"])
            ).hex(),
        }
        for row in world_static.objects(map_id)
        if chunk((row["x"], row["y"])) == selected_chunk
    )
    return world_static._snapshot_bodies(rows)


def dynamic_snapshots(map_id, chunks):
    """Encode only selected partitions, using the current route registration."""
    entrances = frozenset(dungeon_instances.entry_object_ids(map_id))
    return tuple(
        body
        for selected_chunk in sorted(frozenset(chunks))
        for body in _chunk_snapshots(map_id, selected_chunk, entrances)
    )


def snapshot_ids(bodies):
    """Identify exactly which object states were queued for client delivery."""
    identities = []
    for body in bodies:
        count = struct.unpack_from(">h", body)[0]
        cursor = 2
        for _ in range(count):
            identity, length = struct.unpack_from(">qh", body, cursor)
            identities.append(identity)
            cursor += 10 + length
    return identities


def refresh_snapshots(body):
    """Convert a complete 13984 batch to native in-place 12344 updates.

    cwL reads a long identity and unsigned short payload length. cEY resolves
    cdE.mL and updates the retained scene instance instead of creating another.
    Validate the entire batch before exposing any updates to the caller.
    """
    if len(body) < 2:
        raise ValueError("Truncated interactive snapshot count")
    count = struct.unpack_from(">h", body)[0]
    if count < 0:
        raise ValueError("Negative interactive snapshot count")
    cursor = 2
    updates = []
    for _ in range(count):
        if len(body) - cursor < 10:
            raise ValueError("Truncated interactive snapshot record")
        identity, length = struct.unpack_from(">qH", body, cursor)
        cursor += 10
        if length == 0 or length > len(body) - cursor:
            raise ValueError("Invalid interactive snapshot payload length")
        updates.append(
            struct.pack(">qH", identity, length) + body[cursor : cursor + length]
        )
        cursor += length
    if cursor != len(body):
        raise ValueError("Trailing interactive snapshot data")
    return tuple(updates)


class SceneSync:
    """Coalesce finite replay checkpoints for one exploration peer."""

    def __init__(self):
        self.identity = None
        self.pending = {}
        self.last_regions = frozenset()

    def clear(self):
        self.identity = None
        self.pending.clear()
        self.last_regions = frozenset()

    def arm(self, map_id, instance_id, steps, now):
        steps = tuple(steps)
        if not 1 <= len(steps) <= MAX_STEPS or not math.isfinite(now):
            raise ValueError("Invalid accepted scene movement schedule")
        identity = (map_id, instance_id)
        centers = tuple(chunk(step) for step in steps)
        relevant = frozenset().union(*(neighborhood(center) for center in centers))
        # Redirections retain outstanding updates only for still-relevant
        # partitions. Never carry another map/instance's state into this scene.
        retained_pending = {}
        if self.identity == identity:
            for due, regions in self.pending.items():
                regions = regions & relevant
                if regions:
                    # Preserve an update that became due while handling the
                    # previous request; merge overdue batches for prompt poll.
                    due = min(due, math.floor(now)) if due <= now else due
                    retained_pending[due] = (
                        retained_pending.get(due, frozenset()) | regions
                    )
        self.pending = retained_pending
        self.identity = identity
        # Coordinates do not acknowledge client registration. A nearby object
        # may load late or be recreated within an overlapping neighborhood.
        # Retry the complete local neighborhood, including origin overlap.
        destination = neighborhood(centers[-1])
        duration = len(steps) * STEP_SECONDS
        for tick in range(1, math.ceil(duration + TAIL_SECONDS) + 1):
            elapsed = tick * RETRY_SECONDS
            index = min(max(int(elapsed / STEP_SECONDS) - 1, 0), len(centers) - 1)
            # Shared second boundaries coalesce rapid redirects instead of
            # accumulating a separate retry chain for every click.
            due = math.ceil(now) + elapsed
            self.pending[due] = self.pending.get(due, frozenset()) | (
                neighborhood(centers[index]) | destination
            )

    def poll(self, map_id, instance_id, now):
        self.last_regions = frozenset()
        if self.identity != (map_id, instance_id):
            self.clear()
            return ()
        due = [deadline for deadline in self.pending if deadline <= now]
        if not due:
            return ()
        regions = frozenset().union(*(self.pending.pop(deadline) for deadline in due))
        self.last_regions = regions
        return dynamic_snapshots(map_id, regions) if regions else ()
