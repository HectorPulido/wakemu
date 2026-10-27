"""Explicit QI QK slot authority, independent of actors, affiliation and HP.

The producer must supply every slot, including reserved, unindexed objects.
This module does not infer a complete QI population from a fighter roster.
"""
from copy import deepcopy

from .combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle, ImmutableQIMasks


def _copy_byte_topology(topology):
    """Detach persisted Trove arrays without redispatching each integer.

    This is a copy optimization, not a schema validator. Unknown shapes retain
    deepcopy's behavior, including aliases and cycles, before normal validation.
    """
    if type(topology) is not dict or any(type(key) is not str for key in topology):
        return deepcopy(topology)
    copied = {}
    memo = {id(topology): copied}
    fields = {"keys", "states", "size", "free", "compact_removes"}
    for cell, state in topology.items():
        if id(state) in memo:
            copied[cell] = memo[id(state)]
            continue
        if (
            type(state) is not dict
            or state.keys() != fields
            or any(type(key) is not str for key in state)
            or any(type(state[key]) is not int for key in fields - {"keys", "states"})
            or any(
                type(state[key]) is not list
                or any(type(value) is not int for value in state[key])
                for key in ("keys", "states")
            )
        ):
            copied[cell] = deepcopy(state, memo)
            continue
        detached = dict(state)
        memo[id(state)] = detached
        for key in ("keys", "states"):
            array = state[key]
            if id(array) not in memo:
                memo[id(array)] = array.copy()
            detached[key] = memo[id(array)]
        copied[cell] = detached
    return copied


def _copy_slots(slots):
    """Detach ordinary scalar descriptors; custom graphs retain deepcopy."""
    rows = list(slots)
    fields = {"identity", "position", "radius", "indexed", "movement_blocking"}
    for row in rows:
        if row is None:
            continue
        if (
            type(row) is not dict
            or row.keys() != fields
            or type(row["identity"]) not in (list, tuple)
            or len(row["identity"]) != 2
            or type(row["identity"][0]) is not str
            or type(row["identity"][1]) is not int
            or type(row["position"]) not in (list, tuple)
            or len(row["position"]) != 2
            or any(type(value) is not int for value in row["position"])
            or type(row["radius"]) is not int
            or type(row["indexed"]) is not bool
            or type(row["movement_blocking"]) is not bool
        ):
            return deepcopy(rows)
    memo = {}
    for index, row in enumerate(rows):
        if row is None:
            continue
        previous = memo.get(id(row))
        if previous is not None:
            rows[index] = previous
            continue
        detached = row.copy()
        memo[id(row)] = detached
        for field in ("identity", "position"):
            value = row[field]
            if type(value) is list:
                copied = memo.get(id(value))
                if copied is None:
                    copied = value.copy()
                    memo[id(value)] = copied
                detached[field] = copied
        rows[index] = detached
    return rows


class NativeQIRegistry:
    def __init__(self, arena, slots, *, touched_cells=None, byte_topology=None):
        if not isinstance(arena, dict):
            raise ValueError("Missing serialized native QI rectangle")
        self.terrain = NativeQISnapshot(arena)
        if touched_cells is not None and not isinstance(
            touched_cells, (list, tuple, set, frozenset)
        ):
            raise ValueError("Missing native QL touched-cell checkpoint")
        self.touched_cells = set()
        for cell in () if touched_cells is None else touched_cells:
            if (
                not isinstance(cell, (list, tuple))
                or len(cell) != 2
                or any(type(n) is not int for n in cell)
                or not self.terrain.aK(*cell)
            ):
                raise ValueError("Invalid native QL touched cell")
            self.touched_cells.add(tuple(cell))
        if not isinstance(slots, (list, tuple)) or len(slots) != 127:
            raise ValueError("Missing complete native QI slot population")
        self.slots = _copy_slots(slots)
        self.byte_topology = _copy_byte_topology(byte_topology)
        if byte_topology is not None and not isinstance(byte_topology, dict):
            raise ValueError("Missing native QL byte topology checkpoint")
        identities = set()
        for row in self.slots:
            if row is None:
                continue
            self._validate(row)
            identity = tuple(row["identity"])
            if identity in identities:
                raise ValueError("Duplicate native QK slot identity")
            identities.add(identity)
        self._query_membership(None)

    def capture_fresh_cell_topology(self, registration_order):
        """Only fresh QI creation may supply the original registration order."""
        if self.byte_topology is not None:
            raise ValueError("Cannot rebuild an existing native QL topology")
        if len(registration_order) != len(set(registration_order)) or set(
            registration_order
        ) != {i for i, row in enumerate(self.slots) if row is not None}:
            raise ValueError("Missing exact fresh QK registration order")
        self.byte_topology = {}
        for slot in registration_order:
            self._index_topology(slot)

    def _index_topology(self, slot):
        if self.byte_topology is None:
            return
        from .combat_trove_byte_set import NativeTroveByteSet

        row = self.slots[slot]
        if not row["indexed"]:
            return
        footprint = NativeQISnapshot(
            dict(
                x=self.terrain.x,
                y=self.terrain.y,
                width=self.terrain.width,
                height=self.terrain.height,
                cell_masks=self.terrain.masks,
            ),
            obstacles=[RegisteredObstacle(slot, *row["position"], row["radius"])],
        ).occupancy
        for x, y in footprint:
            key = f"{x},{y}"
            value = NativeTroveByteSet(self.byte_topology.get(key))
            value.put(slot)
            self.byte_topology[key] = value.state

    def _remove_topology(self, slot):
        if self.byte_topology is None:
            return
        from .combat_trove_byte_set import NativeTroveByteSet

        for state in self.byte_topology.values():
            NativeTroveByteSet(state).remove(slot)

    def ordered_U(self, x, y):
        """Actual persisted descending Trove iterator; never sort final members."""
        if not self.terrain.aK(x, y):
            return ()
        if self.byte_topology is None:
            raise ValueError("Missing actual native QL byte iterator topology")
        from .combat_trove_byte_set import NativeTroveByteSet

        state = self.byte_topology.get(f"{x},{y}")
        order = () if state is None else NativeTroveByteSet(state).order()
        occupancy = self._query_membership((x, y))
        if frozenset(order) != (frozenset() if occupancy is None else occupancy):
            raise ValueError("Native QL topology disagrees with registered occupancy")
        return order

    def _query_membership(self, query):
        """Revalidate the entire live population, materializing one cell only.

        No earlier validation or checkpoint equality is treated as a proof.
        The temporary covered-column dict preserves snapshot's touched-update
        order; publish it only after every obstacle has passed all guards.
        """
        if (
            type(self) is not NativeQIRegistry
            or type(self.terrain) is not NativeQISnapshot
            or type(self.touched_cells) is not set
            or "snapshot" in self.__dict__
            or any(name in self.terrain.__dict__ for name in ("aK", "_int32"))
        ):
            snapshot = self.snapshot()
            return None if query is None else snapshot.U(*query)
        # Match snapshot's descriptor construction before terrain validation.
        obstacles = [
            RegisteredObstacle(slot, *row["position"], row["radius"])
            for slot, row in enumerate(self.slots)
            if row is not None and row["indexed"]
        ]
        terrain = self.terrain
        values = (terrain.x, terrain.y, terrain.width, terrain.height)
        if any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in values
        ):
            raise ValueError("Missing serialized native QI rectangle")
        masks = terrain.masks
        if (
            terrain.width < 1
            or terrain.height < 1
            or terrain.width * terrain.height > 32767
            or not isinstance(masks, (list, tuple))
            or len(masks) != terrain.width * terrain.height
        ):
            raise ValueError("Missing serialized native QI signed-short masks")
        ImmutableQIMasks(masks)
        covered, members, seen = {}, set(), set()
        inside = NativeQISnapshot.aK
        for obstacle in obstacles:
            if (
                not isinstance(obstacle, RegisteredObstacle)
                or any(
                    type(value) is not int
                    for value in (
                        obstacle.obstacle_id,
                        obstacle.x,
                        obstacle.y,
                        obstacle.radius,
                    )
                )
                or not 0 <= obstacle.obstacle_id <= 126
                or not -128 <= obstacle.radius <= 127
                or any(
                    not -(1 << 31) <= value < (1 << 31)
                    for value in (obstacle.x, obstacle.y)
                )
                or obstacle.obstacle_id in seen
            ):
                raise ValueError("Invalid native registered QK obstacle")
            radius = max(0, obstacle.radius)
            if radius == 0 and not inside(terrain, obstacle.x, obstacle.y):
                raise ValueError(
                    "Native radius-zero obstacle is outside QI registration bounds"
                )
            if (
                any(
                    not -(1 << 31) <= endpoint < (1 << 31)
                    for endpoint in (
                        obstacle.x - radius,
                        obstacle.x + radius,
                        obstacle.y - radius,
                        obstacle.y + radius,
                    )
                )
                or obstacle.x + radius == (1 << 31) - 1
                or obstacle.y + radius == (1 << 31) - 1
            ):
                raise ValueError(
                    "Native QK footprint exceeds proven terminating int32 domain"
                )
            seen.add(obstacle.obstacle_id)
            if radius == 0:
                cell = (obstacle.x, obstacle.y)
                covered[cell] = None
                if query == cell:
                    members.add(obstacle.obstacle_id)
                continue
            for x in range(obstacle.x - radius, obstacle.x + radius + 1):
                for y in range(obstacle.y - radius, obstacle.y + radius + 1):
                    if inside(terrain, x, y):
                        cell = (x, y)
                        covered[cell] = None
                        if query == cell:
                            members.add(obstacle.obstacle_id)
        self.touched_cells.update(covered)
        return frozenset(members)

    def serialized_byte_topology(self):
        return deepcopy(self.byte_topology)

    @staticmethod
    def _validate(row):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("identity"), (list, tuple))
            or len(row["identity"]) != 2
            or row["identity"][0] not in ("actor", "effect_area")
            or type(row["identity"][1]) is not int
            or type(row.get("indexed")) is not bool
            or type(row.get("movement_blocking")) is not bool
            or type(row.get("radius")) is not int
            or not -128 <= row["radius"] <= 127
            or not isinstance(row.get("position"), (list, tuple))
            or len(row["position"]) != 2
            or any(
                type(n) is not int or not -(1 << 31) <= n < (1 << 31)
                for n in row["position"]
            )
        ):
            raise ValueError("Missing native registered QK descriptor")

    def snapshot(self):
        obstacles = [
            RegisteredObstacle(slot, *row["position"], row["radius"])
            for slot, row in enumerate(self.slots)
            if row is not None and row["indexed"]
        ]
        arena = dict(
            x=self.terrain.x,
            y=self.terrain.y,
            width=self.terrain.width,
            height=self.terrain.height,
            cell_masks=self.terrain.masks,
        )
        snapshot = NativeQISnapshot(arena, obstacles=obstacles)
        # QL removal clears the existing byte set; it does not make that
        # cell's entry absent. Preserve that distinction across checkpoints.
        self.touched_cells.update(snapshot.occupancy)
        for cell in self.touched_cells:
            snapshot.occupancy.setdefault(cell, frozenset())
        return snapshot

    def register(self, row):
        """QI.f: reserve first-free slot before checking the anchor bounds.

        This operation accepts only QK objects with proven bcO=true. Objects
        with bcO=false bypass QI.f and retain their constructor bcN=-1.
        """
        self._validate(row)
        if any(
            existing is not None
            and tuple(existing["identity"]) == tuple(row["identity"])
            for existing in self.slots
        ):
            raise ValueError("Native QK already registered")
        slot = next(
            (i for i, existing in enumerate(self.slots) if existing is None), None
        )
        if slot is None:
            # QI.j logs and returns -1 without assigning a slot.
            return -1
        captured = deepcopy(row)
        captured["indexed"] = self.terrain.aK(*captured["position"])
        self.slots[slot] = captured
        try:
            self.snapshot()
        except ValueError:
            self.slots[slot] = None
            raise
        self._index_topology(slot)
        return slot

    def remove(self, slot, identity):
        """Identity-checked QI.g removal for a proven registered QK."""
        row = self._owned(slot, identity)
        if row["indexed"] and not self.terrain.aK(*row["position"]):
            raise ValueError(
                "Native out-of-bounds indexed removal requires QL checkpoint"
            )
        self._remove_topology(slot)
        self.slots[slot] = None

    def move(self, slot, identity, position):
        """QI.a(QK,x,y), followed by the caller's actual coordinate update.

        Native relocation adds the new footprint even when the previous
        indexing was toggled off; an out-of-bounds destination keeps its slot.
        """
        row = self._owned(slot, identity)
        updated = deepcopy(row)
        updated["position"] = position
        self._validate(updated)
        if row["indexed"] and not self.terrain.aK(*row["position"]):
            raise ValueError(
                "Native out-of-bounds indexed movement requires QL checkpoint"
            )
        updated["indexed"] = self.terrain.aK(*position)
        self.slots[slot] = updated
        try:
            self.snapshot()
        except ValueError:
            self.slots[slot] = row
            raise
        self._remove_topology(slot)
        self._index_topology(slot)

    def move_carried(self, slot, identity, position):
        """eGj.a(IIS) while buX: mutate QK coordinates without QL insertion."""
        row = self._owned(slot, identity)
        if row["indexed"]:
            raise ValueError("Carried QK must have actual disabled indexing")
        updated = deepcopy(row)
        updated["position"] = position
        self._validate(updated)
        self.slots[slot] = updated
        try:
            self.snapshot()
        except ValueError:
            self.slots[slot] = row
            raise

    def toggle(self, slot, identity, enabled):
        """QI.a(QK,boolean): change QL membership, retaining the QK slot."""
        row = self._owned(slot, identity)
        if type(enabled) is not bool:
            raise ValueError("Invalid native QK indexing toggle")
        if not self.terrain.aK(*row["position"]):
            return  # Both native true and false return before changing QL.
        before = row["indexed"]
        row["indexed"] = enabled
        try:
            self.snapshot()
        except ValueError:
            row["indexed"] = before
            raise
        if enabled:
            self._index_topology(slot)
        else:
            self._remove_topology(slot)

    def _owned(self, slot, identity):
        if type(slot) is not int or not 0 <= slot <= 126:
            raise ValueError("Missing native QK slot")
        row = self.slots[slot]
        if row is None or tuple(row["identity"]) != tuple(identity):
            raise ValueError("Native QK slot identity mismatch")
        return row

    def serialized_slots(self):
        return deepcopy(self.slots)

    def serialized_cells(self):
        return [list(cell) for cell in sorted(self.touched_cells)]
