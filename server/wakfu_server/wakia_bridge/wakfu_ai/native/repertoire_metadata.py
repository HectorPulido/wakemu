"""Turn/catalogue-local spell templates, never state certificates."""
from collections import OrderedDict
from copy import deepcopy
import sys

from .native_deadline import check


class SpellMetadataCache:
    """Reuse static spell records while current ownership and bounds stay fresh.

    One instance belongs to one native turn catalogue scope or an isolated
    NativeSession. Catalogue and source implementation are pinned and guarded
    by its owner. The builder must only
    return casting/class/inventory/advisory definitions for the spell/level;
    dynamic prerequisites, target envelopes and owned-spell selection belong
    outside this cache.
    """

    def __init__(self, *, max_entries=256, max_bytes=16 * 1024 * 1024):
        if any(
            type(value) is not int or value < 1 for value in (max_entries, max_bytes)
        ):
            raise ValueError("Invalid spell metadata cache bound")
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self._records = OrderedDict()
        self._bytes = 0
        self.metrics = dict(hits=0, misses=0)

    def _size(self, row):
        pending, seen, size = [row], set(), 0
        while pending:
            if len(seen) % 256 == 0:
                check()
            value = pending.pop()
            if id(value) in seen:
                continue
            seen.add(id(value))
            size += sys.getsizeof(value)
            if size > self.max_bytes:
                return None
            if type(value) is dict:
                for key, child in value.items():
                    pending.extend((key, child))
            elif type(value) in (list, tuple, set, frozenset):
                pending.extend(value)
            elif type(value) not in (
                str,
                bytes,
                bytearray,
                int,
                float,
                bool,
                type(None),
            ):
                # Future opaque definitions still travel in full; do not retain
                # them under an incorrectly estimated memory budget.
                return None
        check()
        return size

    def rows(self, owned, builder):
        result = []
        for spell, level in sorted(owned.items()):
            check()
            key = spell, level
            if key in self._records:
                self.metrics["hits"] += 1
                private, _ = self._records[key]
                self._records.move_to_end(key)
                row = deepcopy(private)
            else:
                self.metrics["misses"] += 1
                row = deepcopy(builder(spell, level))
                check()
                size = self._size(row)
                if size is not None:
                    private = deepcopy(row)
                    check()
                    self._records[key] = private, size
                    self._bytes += size
                    self._records.move_to_end(key)
                    while (
                        len(self._records) > self.max_entries
                        or self._bytes > self.max_bytes
                    ):
                        _, (_, old_size) = self._records.popitem(last=False)
                        self._bytes -= old_size
            check()
            result.append(row)
        return result
