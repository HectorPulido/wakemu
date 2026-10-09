"""Explicit QI QK slot authority, independent of actors, affiliation and HP.

The producer must supply every slot, including reserved, unindexed objects.
This module does not infer a complete QI population from a fighter roster.
"""
from copy import deepcopy

from .combat_qi_snapshot import NativeQISnapshot, RegisteredObstacle


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
        self.slots = deepcopy(list(slots))
        self.byte_topology = deepcopy(byte_topology)
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
        self.snapshot()

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
        occupancy = self.snapshot().U(x, y)
        if frozenset(order) != (frozenset() if occupancy is None else occupancy):
            raise ValueError("Native QL topology disagrees with registered occupancy")
        return order

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
