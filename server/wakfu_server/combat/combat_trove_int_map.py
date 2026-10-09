"""TIntObjectHashMap topology; HashFunctions.hash(int) returns its operand."""
from .combat_trove_long_map import NativeTroveLongMap


class NativeTroveIntMap(NativeTroveLongMap):
    def _slot(self, key, insert=False):
        if type(key) is not int or not -(1 << 31) <= key < (1 << 31):
            raise ValueError("Native signed-int map key required")
        keys, states = self.state["keys"], self.state["states"]
        capacity = len(keys)
        hashed = key & 0x7FFFFFFF
        index = start = hashed % capacity
        step = 1 + hashed % (capacity - 2)
        removed = None
        while True:
            status = states[index]
            if status == 0:
                return (removed if removed is not None else index) if insert else None
            if status == 1 and keys[index] == key:
                return index
            if status == 2 and removed is None:
                removed = index
            index = (index - step) % capacity
            if index == start:
                if insert and removed is not None:
                    return removed
                raise ValueError("Native Trove int key set full")
