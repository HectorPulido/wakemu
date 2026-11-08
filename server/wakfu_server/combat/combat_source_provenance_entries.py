"""Native provenance key ownership, without caching row authority.

Only the native producer creates this mapping. Existing dictionaries are not
promoted in place: their aliases and legacy lookup behavior remain intact.
Like the other native owned mappings, writes must use the mapping API rather
than explicitly calling dict mutation methods on this instance.
"""
from copy import deepcopy, _keep_alive


class SourceProvenanceEntries(dict):
    """Keep exact-string key eligibility in constant time between mutations.

    Rows remain the caller's actual objects and are validated freshly by each
    consumer. A foreign key or opaque bulk writer permanently declines the
    local query path; ordinary dictionary behavior is still preserved.
    """

    def __init__(self, *args, **kwargs):
        if not hasattr(self, "_native_key_serial"):
            self._native_key_serial = 0
            self._native_keys = True
        dict.__init__(self)
        if args or kwargs:
            self.update(*args, **kwargs)

    @property
    def keys_are_native(self):
        return self._native_keys is True

    def _check_key(self, key):
        if type(key) is not str:
            # Revoke before hashing/comparing the supplied object: its callback
            # must not observe a still-admitted map during a foreign write.
            self._native_key_serial += 1
            self._native_keys = False

    def __setitem__(self, key, value):
        self._check_key(key)
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        self._check_key(key)
        dict.__delitem__(self, key)

    def setdefault(self, key, default=None):
        self._check_key(key)
        return dict.setdefault(self, key, default)

    def pop(self, key, *default):
        self._check_key(key)
        return dict.pop(self, key, *default)

    def popitem(self):
        return dict.popitem(self)

    def clear(self):
        # Clearing content does not manufacture new native ownership proof.
        dict.clear(self)

    def update(self, *args, **kwargs):
        admitted = self._native_keys is True
        serial = self._native_key_serial
        self._native_keys = False
        safe_source = not args
        if len(args) == 1:
            source = args[0]
            safe_source = (
                type(source) is dict
                and all(type(key) is str for key in dict.keys(source))
            ) or (
                type(source) is SourceProvenanceEntries
                and (source is self and admitted or source.keys_are_native)
            )
        safe_source = safe_source and all(type(key) is str for key in dict.keys(kwargs))
        if not safe_source:
            self._native_key_serial += 1
        try:
            # Retain CPython's partial update and exception behavior for custom
            # mappings and iterators. They remain ineligible even on success.
            dict.update(self, *args, **kwargs)
        finally:
            self._native_keys = (
                admitted and safe_source and self._native_key_serial == serial
            )

    def __ior__(self, other):
        self.update(other)
        return self

    @classmethod
    def fromkeys(cls, iterable, value=None):
        result = cls()
        for key in iterable:
            result[key] = value
        return result

    def __copy__(self):
        result = type(self)()
        result._native_keys = False
        serial = result._native_key_serial
        dict.update(result, self)
        result._native_keys = (
            self.keys_are_native and result._native_key_serial == serial
        )
        return result

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        result._native_keys = False
        serial = result._native_key_serial
        native_keys = self.keys_are_native
        for key, value in dict.items(self):
            copied_key = deepcopy(key, memo)
            native_keys = native_keys and type(copied_key) is str
            # The native producer emits exact scalar dictionaries. Keep each
            # row mutable and distinct from its source, but avoid recursive
            # scalar dispatch when no callback can run during the copy.
            if (
                type(value) is dict
                and id(value) not in memo
                and all(
                    type(name) is str
                    and id(name) not in memo
                    and id(item) not in memo
                    and (
                        item is None
                        or type(item) is int
                        or type(item) is str
                        or type(item) is bool
                    )
                    for name, item in dict.items(value)
                )
            ):
                copied_value = dict.copy(value)
                memo[id(value)] = copied_value
                _keep_alive(value, memo)
            else:
                copied_value = deepcopy(value, memo)
            dict.__setitem__(result, copied_key, copied_value)
        result._native_keys = native_keys and result._native_key_serial == serial
        return result
