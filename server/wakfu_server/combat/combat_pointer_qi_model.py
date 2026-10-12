"""Private source-derived QI/QL alias model; not imported by the server."""
from dataclasses import dataclass
from .combat_trove_byte_set import NativeTroveByteSet


@dataclass(eq=False)
class QK:
    identity: int
    x: int
    y: int
    radius: int = 0
    byte: int = -1
    eligible: bool = True


class PointerQI:
    """Keep object pointers, cell memberships and latest anchors independent."""

    def __init__(self, width=4, height=4):
        self.width, self.height = width, height
        self.origin = (0, 0)
        self.slots = [None] * 127
        self.cells = {}
        self.anchors = {}

    def inside(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def slot_object(self, byte):
        return self.slots[byte] if 0 <= byte < 127 else None

    def members(self, x, y):
        # Native absent and touched-empty cells are different observations.
        value = self.cells.get((x, y))
        return None if value is None else frozenset(value.order())

    def _index(self, obj, x, y):
        if not 0 <= obj.byte < 127:
            return
        if type(obj.radius) is not int or not -128 <= obj.radius <= 127:
            raise ValueError("Missing actual signed-byte radius")
        previous = self.slots[obj.byte]
        if previous is not None and previous is not obj:
            self.remove(previous)
        self.slots[obj.byte] = obj
        self.cells.setdefault((x, y), NativeTroveByteSet()).put(obj.byte)
        self.anchors[obj.byte] = (x, y)
        if obj.radius > 0:
            for dx in range(x - obj.radius, x + obj.radius + 1):
                for dy in range(y - obj.radius, y + obj.radius + 1):
                    if self.inside(dx, dy) and (dx, dy) != (x, y):
                        self.cells.setdefault((dx, dy), NativeTroveByteSet()).put(
                            obj.byte
                        )

    def ordered_members(self, x, y):
        value = self.cells.get((x, y))
        return () if value is None else value.order()

    def _unindex(self, obj):
        anchor = self.anchors.pop(obj.byte, self.origin)
        if obj.radius > 0:
            for value in self.cells.values():
                value.remove(obj.byte)
        elif anchor in self.cells:
            self.cells[anchor].remove(obj.byte)

    def register(self, obj):
        if obj is None or not obj.eligible:
            return
        free = next((i for i, value in enumerate(self.slots) if value is None), None)
        if free is not None:
            self.slots[free] = obj
            obj.byte = free
        # QI.f ignores QI.j failure and retains the object's previous byte.
        if self.inside(obj.x, obj.y):
            self._index(obj, obj.x, obj.y)

    def remove(self, obj):
        if obj is None or not obj.eligible or not 0 <= obj.byte < 127:
            return
        if self.slots[obj.byte] is obj:
            if self.inside(obj.x, obj.y):
                self._unindex(obj)
            self.slots[obj.byte] = None
        obj.byte = -1

    def move(self, obj, x, y):
        if not obj.eligible:
            return
        if self.inside(obj.x, obj.y):
            self._unindex(obj)
        if self.inside(x, y):
            self._index(obj, x, y)
        # Native QI.a does not mutate actual QK coordinates. Caller does.


@dataclass
class Retained937:
    """Only actual eYa QI operations; no inferred global/death lifecycle."""

    uid: int
    target: QK
    executed: bool = False

    def apply(self, qi):
        qi.remove(self.target)
        self.executed = True

    def remove_runner(self, qi):
        # eYa uses its actual retained target pointer, not global actor lookup.
        if self.executed:
            qi.register(self.target)
