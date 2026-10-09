"""Installed default Trove long-key map topology for native PV iterator order.

Values are PV identities equal to their keys. State is plain checkpoint data;
rebuilding from its final key set would lose removed slots and rehash history.
"""
from wakfu_server import native_catalog as protocol_catalog
import bisect
import json
import math
import struct
from functools import lru_cache
from pathlib import Path


def _float32(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


@lru_cache(maxsize=1)
def _contract():
    path = Path(__file__).resolve().parents[2] / "protocol/native-trove-long-map.json"
    contract = protocol_catalog.load(path)
    if contract["load_factor"] != 0.5 or contract["auto_compaction_factor"] != 0.5:
        raise ValueError("Unaudited native Trove constructor")
    return contract


class NativeTroveLongMap:
    def __init__(self, state=None):
        self.contract = _contract()
        if state is None:
            capacity = self.contract["initial_capacity"]
            state = dict(
                keys=[0] * capacity,
                states=[0] * capacity,
                size=0,
                free=capacity,
                compact_removes=self.contract["initial_compact_removes"],
            )
        self.state = state
        if not isinstance(state, dict) or set(state) != {
            "keys",
            "states",
            "size",
            "free",
            "compact_removes",
        }:
            raise ValueError("Exact persisted native Trove topology required")
        if len(state["keys"]) != len(state["states"]):
            raise ValueError("Invalid native Trove slot arrays")
        if (
            len(state["keys"]) not in self.contract["prime_capacities"]
            or any(
                type(status) is not int or status not in (0, 1, 2)
                for status in state["states"]
            )
            or any(
                type(key) is not int or not -(1 << 63) <= key < (1 << 63)
                for key in state["keys"]
            )
            or any(
                type(state[key]) is not int
                for key in ("size", "free", "compact_removes")
            )
            or state["size"] != state["states"].count(1)
            or not 0 <= state["free"] <= len(state["keys"])
        ):
            raise ValueError("Invalid persisted native Trove topology")
        occupied = [
            key for key, status in zip(state["keys"], state["states"]) if status == 1
        ]
        if len(occupied) != len(set(occupied)):
            raise ValueError("Duplicate native Trove map identity")

    def _prime(self, minimum):
        primes = self.contract["prime_capacities"]
        index = bisect.bisect_left(primes, minimum)
        if index == len(primes):
            raise ValueError("Native Trove capacity overflow")
        return primes[index]

    def _slot(self, key, insert=False):
        if type(key) is not int or not -(1 << 63) <= key < (1 << 63):
            raise ValueError("Native signed-long PV identity required")
        keys, states = self.state["keys"], self.state["states"]
        capacity = len(keys)
        hashed = (key ^ ((key & ((1 << 64) - 1)) >> 32)) & 0x7FFFFFFF
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
                raise ValueError("Native Trove key set full")

    def _rehash(self, capacity):
        old = self.order()
        self.state["keys"] = [0] * capacity
        self.state["states"] = [0] * capacity
        for key in old:
            slot = self._slot(key, insert=True)
            self.state["keys"][slot] = key
            self.state["states"][slot] = 1
        self.state["free"] = capacity - self.state["size"]

    def put(self, key):
        slot = self._slot(key, insert=True)
        if self.state["states"][slot] == 1:
            return False
        if self.state["states"][slot] == 0:
            self.state["free"] -= 1
        self.state["keys"][slot] = key
        self.state["states"][slot] = 1
        self.state["size"] += 1
        capacity = len(self.state["keys"])
        maximum = min(capacity - 1, int(_float32(_float32(capacity) * 0.5)))
        if self.state["size"] > maximum or self.state["free"] == 0:
            self._rehash(
                self._prime(capacity * 2) if self.state["size"] > maximum else capacity
            )
        return True

    def remove(self, key):
        slot = self._slot(key)
        if slot is None:
            return False
        self.state["keys"][slot] = 0
        self.state["states"][slot] = 2
        self.state["size"] -= 1
        self.state["compact_removes"] -= 1
        if self.state["compact_removes"] <= 0:
            size = self.state["size"]
            minimum = max(size + 1, math.ceil(_float32(_float32(size) / 0.5)) + 1)
            self._rehash(self._prime(minimum))
            self.state["compact_removes"] = int(
                _float32(_float32(_float32(size) * 0.5) + 0.5)
            )
        return True

    def order(self):
        return tuple(
            self.state["keys"][index]
            for index in range(len(self.state["keys"]) - 1, -1, -1)
            if self.state["states"][index] == 1
        )

    def contains(self, key):
        return self._slot(key) is not None
