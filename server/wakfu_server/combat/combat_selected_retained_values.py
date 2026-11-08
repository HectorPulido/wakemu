"""Operation-owned frozen row reuse; never selected ownership authority."""
from operator import is_
from .combat_retained_collections import TrackedRow
from weakref import ref


_ROW_VALUE_METHODS = tuple(
    (name, getattr(TrackedRow, name))
    for name in (
        "__init__",
        "__setattr__",
        "__delattr__",
        "__setitem__",
        "__delitem__",
        "clear",
        "pop",
        "popitem",
        "update",
        "setdefault",
        "__ior__",
        "_changed",
        "get",
        "values",
        "items",
        "keys",
        "__iter__",
        "__getitem__",
        "__len__",
        "__getattribute__",
    )
)
_ROW_READ_NAMES = (
    "get",
    "values",
    "items",
    "keys",
    "__iter__",
    "__getitem__",
    "__len__",
)


def _owned_frozen_value(record):
    """Return only immutable value metadata; never a cached ownership decision."""
    from .combat_retained_runtime import _retained_record, _cacheable_retained_record
    from .combat_retained_effects import RetainedEffect

    if type(record) is not TrackedRow:
        return None
    attributes = vars(record)
    if any(name in attributes for name in _ROW_READ_NAMES) or any(
        getattr(TrackedRow, name) is not original
        for name, original in _ROW_VALUE_METHODS
    ):
        object.__setattr__(record, "_retained_value", None)
        return None
    entry = attributes.get("_retained_value")
    if type(entry) is RetainedEffect:
        return entry
    if not _cacheable_retained_record(record):
        return None
    entry = _retained_record(record)
    object.__setattr__(record, "_retained_value", entry)
    return entry


class SelectedRetainedValues:
    def __init__(self, fight, *, keep_current=True):
        from .combat_retained_runtime import _RETAINED_POPULATIONS

        self.owner = ref(fight)
        # Borrow detached primitive values only. Never replace the full owner's
        # population with a selected subset or retain a native view/manager.
        self.previous = _RETAINED_POPULATIONS.get(fight, {})
        self.current = {}
        self.keep_current = keep_current

    def read_batch(self, fight, ids, records):
        """Reuse the method proof only between callback-free warm row reads.

        Look up each UID immediately before reading it: a fallback constructor
        can replace a later row. No proof escapes this one selected batch.
        """
        from .combat_retained_collections import OwnedMap

        if (
            type(self) is not SelectedRetainedValues
            or type(ids) is not tuple
            or any(type(uid) is not int for uid in ids)
            or SelectedRetainedValues.read is not _NATIVE_SELECTED_READ
            or "read" in vars(self)
        ):
            return tuple(self.read(fight, uid, records[uid]) for uid in ids)
        output = []
        methods_known = False
        for uid in ids:
            # A custom lookup can mutate classes or following rows. Its original
            # lookup/read order is preserved, and it carries no proof forward.
            native_lookup = type(records) is dict or (
                type(records) is OwnedMap and OwnedMap.__getitem__ is dict.__getitem__
            )
            if not native_lookup:
                methods_known = False
            record = records[uid]
            if not methods_known:
                methods_known = all(
                    getattr(TrackedRow, name) is original
                    for name, original in _ROW_VALUE_METHODS
                )
            if (
                native_lookup
                and methods_known
                and SelectedRetainedValues.__getattribute__ is object.__getattribute__
                and SelectedRetainedValues.read is _NATIVE_SELECTED_READ
                and "read" not in vars(self)
                and type(vars(self).get("owner")) is ref
                and vars(self)["owner"]() is fight
                and type(record) is TrackedRow
            ):
                from .combat_retained_effects import RetainedEffect

                attributes = vars(record)
                if not any(name in attributes for name in _ROW_READ_NAMES):
                    entry = attributes.get("_retained_value")
                    if type(entry) is RetainedEffect:
                        output.append(entry)
                        continue
            methods_known = False
            output.append(self.read(fight, uid, record))
        return tuple(output)

    def read(self, fight, uid, record):
        from .combat_retained_runtime import _retained_record

        if (
            self.owner() is not fight
            or type(uid) is not int
            or (type(record) is not dict and type(record) is not TrackedRow)
        ):
            return _retained_record(record)
        entry = _owned_frozen_value(record)
        if entry is not None:
            return entry
        cached = self.current.get(uid, self.previous.get(uid))
        if cached is not None and len(record) == len(cached[1][0]):
            # The baseline ordered guard compares type tuples. Preserve exact
            # identities even for custom metaclasses with overloaded equality.
            keys_are_strings = all(map(is_, map(type, record), (str,) * len(record)))
            if keys_are_strings:
                if tuple(record) == cached[1][0]:
                    types_identical = all(
                        map(is_, map(type, record.values()), cached[1][1])
                    )
                else:
                    old_types = dict(zip(cached[1][0], cached[1][1]))
                    types_identical = all(
                        type(value) is old_types.get(key)
                        for key, value in record.items()
                    )
                # Exact key and value types above reproduce the baseline's
                # type guard; only detached content equality remains.
                if types_identical and cached[0] == record:
                    return cached[2]
        if not self.keep_current:
            # A manager query reads each selected UID and parent witness once.
            # Do not build a detached snapshot that this query cannot reuse.
            return _retained_record(record)
        cacheable = len(record) <= 17 and all(
            type(key) is str
            and len(key) <= 64
            and (
                type(value) is int
                or type(value) is bool
                or type(value) is str
                or type(value) is type(None)
            )
            and (type(value) is not str or len(value) <= 128)
            and (type(value) is not int or value.bit_length() <= 64)
            for key, value in record.items()
        )
        entry = _retained_record(record)
        if cacheable:
            self.current[uid] = (
                dict(record),
                (tuple(record), tuple(map(type, record.values()))),
                entry,
            )
        else:
            self.current.pop(uid, None)
        return entry


# A batch may bypass read() only while its original public implementation holds.
_NATIVE_SELECTED_READ = SelectedRetainedValues.read
