"""Immutable source-pinned projections for pure advisory state classification."""
from collections import OrderedDict
from collections.abc import Mapping
from sys import getsizeof
from threading import RLock
from types import MappingProxyType

_CACHE = OrderedDict()
_BOUND_CACHE = OrderedDict()
_LOCK = RLock()
_BYTES = 0
_BOUND_BYTES = 0
_MAX_ENTRIES = 4096
_BOUND_MAX_ENTRIES = 8192
_MAX_BYTES = 4 * 1024 * 1024
_MISSING = object()


def _identity(source):
    from .combat_published_catalogs import static_catalog_descriptor

    descriptor = static_catalog_descriptor(source)
    if descriptor is None or descriptor["revision"] == "0" * 64:
        return None
    return descriptor["revision"], descriptor["collection"]


def _charge(value, seen):
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    if type(value) in (str, int, float, bool, type(None)):
        return getsizeof(value)
    if type(value) is tuple:
        return getsizeof(value) + sum(_charge(child, seen) for child in value)
    raise TypeError("Mutable advisory state projection")


def _cached(key, build):
    global _BYTES, _BOUND_BYTES
    bounds = key[0] == "bounds"
    cache = _BOUND_CACHE if bounds else _CACHE
    max_entries = _BOUND_MAX_ENTRIES if bounds else _MAX_ENTRIES
    with _LOCK:
        found = cache.get(key, _MISSING)
        if found is not _MISSING:
            cache.move_to_end(key)
            return found[0]
    result = build()
    try:
        charge = _charge((key, result), set())
    except TypeError:
        return result
    if charge > _MAX_BYTES:
        return result
    with _LOCK:
        found = cache.get(key, _MISSING)
        if found is not _MISSING:
            cache.move_to_end(key)
            return found[0]
        cache[key] = result, charge
        if bounds:
            _BOUND_BYTES += charge
        else:
            _BYTES += charge
        while (
            len(cache) > max_entries
            or (_BOUND_BYTES if bounds else _BYTES) > _MAX_BYTES
        ):
            _, (_, removed) = cache.popitem(last=False)
            if bounds:
                _BOUND_BYTES -= removed
            else:
                _BYTES -= removed
    return result


def _effect_projection(row):
    if row is None:
        return None
    children = row.get("children", ())
    if (
        type(row.get("effect_class")) is not int
        or not isinstance(children, (tuple, list))
        or any(type(child) is not int for child in children)
    ):
        return row
    values = dict(
        effect_class=row["effect_class"],
        criteria=bool(row.get("criteria")),
        native_area=bool(row.get("native_area")),
        area=bool(row.get("area")),
        children=tuple(children),
    )
    if row["effect_class"] == 304:
        for field in (
            "parameter_count",
            "probability_base",
            "probability_per_level",
            "parameters",
        ):
            if field in row:
                value = row[field]
                values[field] = (
                    tuple(value)
                    if field == "parameters" and isinstance(value, (tuple, list))
                    else value
                )
    result = tuple(values.items())
    try:
        _charge(result, set())
    except TypeError:
        return row
    return result


def advisory_effect(source, reference, *, pending=(), remaining=0):
    """Batch nearby immutable DFS inputs without changing visited traversal."""
    identity = _identity(source)
    key = str(reference)
    if identity is None:
        return source.get(key)

    def build():
        keys, selected = [key], {key}
        for following in pending:
            if len(keys) >= min(16, remaining + 1):
                break
            following = str(following)
            with _LOCK:
                known = ("effect", identity, following) in _CACHE
            if following not in selected and not known:
                keys.append(following)
                selected.add(following)
        if len(keys) > 1:
            current = _MISSING
            try:
                for loaded, row in source._batch_items(keys):
                    projected = _effect_projection(row)
                    if loaded == key:
                        current = projected
                    else:
                        _cached(("effect", identity, loaded), lambda: projected)
                if current is not _MISSING:
                    return current
            except (AttributeError, KeyError, TypeError, ValueError):
                # A future sparse/corrupt row cannot alter this node's legacy
                # boundary. The exact requested record is still verified below.
                pass
        return _effect_projection(source.get(key))

    result = _cached(("effect", identity, key), build)
    return MappingProxyType(dict(result)) if type(result) is tuple else result


def prefetch_effects(source, references):
    """Read exact requested immutable inputs through verified bounded batches."""
    identity = _identity(source)
    if identity is None:
        return
    keys = tuple(dict.fromkeys(str(reference) for reference in references))
    with _LOCK:
        missing = [key for key in keys if ("effect", identity, key) not in _CACHE]
    for start in range(0, len(missing), 64):
        try:
            for key, row in source._batch_items(missing[start : start + 64]):
                projected = _effect_projection(row)
                _cached(("effect", identity, key), lambda: projected)
        except (AttributeError, KeyError, TypeError, ValueError):
            # Unsupported batches keep ordinary per-record validation below.
            continue


def forest_prepared(key):
    with _LOCK:
        present = key in _CACHE
        if present:
            _CACHE.move_to_end(key)
        return present


def mark_forest_prepared(key):
    _cached(key, lambda: True)


class _CurrentState(Mapping):
    def __init__(self, source, reference, definition):
        self.source, self.reference, self.definition = source, reference, definition

    def __getitem__(self, reference):
        return (
            self.definition if reference == self.reference else self.source[reference]
        )

    def __iter__(self):
        return iter(self.source)

    def __len__(self):
        return len(self.source)


class _BoundRow(Mapping):
    def __init__(self, view, reference):
        self.view, self.reference = view, reference

    def __getitem__(self, field):
        if field not in ("minimum_level", "maximum_level"):
            return self.view.source[self.reference][field]
        # Presence is retained separately: an excluded minimum must not force
        # a missing/malformed maximum to be evaluated ahead of the consumer.
        return dict(self.view.facts(self.reference))[field]

    def __iter__(self):
        return iter(self.view.source[self.reference])

    def __len__(self):
        return len(self.view.source[self.reference])


class _EffectBounds(Mapping):
    """Stream verified rows in small batches; retain only immutable bounds."""

    def __init__(self, source, identity, references):
        self.source, self.identity, self.references = source, identity, references
        self.last_reference, self.last_facts = _MISSING, None
        self.pending = None
        self.finished = False

    @staticmethod
    def project(row):
        return tuple(
            (field, row[field])
            for field in ("minimum_level", "maximum_level")
            if field in row
        )

    def rows(self):
        references = [str(reference) for reference in self.references()]
        with _LOCK:
            missing = [
                reference
                for reference in references
                if ("bounds", self.identity, reference) not in _BOUND_CACHE
            ]
        for start in range(0, len(missing), 64):
            yield from self.source._batch_items(missing[start : start + 64])

    def read(self, reference):
        if not self.finished:
            if self.pending is None:
                self.pending = iter(self.rows())
            while True:
                try:
                    key, row = next(self.pending)
                except (StopIteration, AttributeError, KeyError, TypeError, ValueError):
                    # Sparse/malformed/private test transports keep the exact
                    # original per-key error boundary and evaluation order.
                    self.pending, self.finished = None, True
                    break
                projected = self.project(row)
                _cached(("bounds", self.identity, key), lambda: projected)
                if key == reference:
                    return projected
        return self.project(self.source[reference])

    def close(self):
        pending, self.pending = self.pending, None
        if pending is not None:
            pending.close()
        self.finished = True

    def facts(self, reference):
        if type(reference) is str and reference == self.last_reference:
            return self.last_facts
        result = _cached(
            ("bounds", self.identity, reference), lambda: self.read(reference)
        )
        self.last_reference, self.last_facts = reference, result
        return result

    def __getitem__(self, reference):
        return _BoundRow(self, reference)

    def __iter__(self):
        return iter(self.source)

    def __len__(self):
        return len(self.source)


def selected_state_roots(states, reference, level):
    """Keep original state validation while reusing sealed selected root IDs."""
    from .combat_definitions import state_profile

    state_source, effect_source = states.get("states"), states.get("effects")
    state_identity, effect_identity = _identity(state_source), _identity(effect_source)
    if (
        state_identity is None
        or effect_identity is None
        or type(level) is not int
        or not -32768 <= level <= 32767
    ):
        return tuple(state_profile(states, reference, level)["effects"])
    key = ("state", state_identity, effect_identity, str(reference), level)

    def build():
        definition = state_source.get(str(reference))
        if definition is None:
            return tuple(state_profile(states, reference, level)["effects"])

        bounds = _EffectBounds(
            effect_source, effect_identity, lambda: definition["effect_ids"]
        )
        private = dict(
            states,
            states=_CurrentState(state_source, str(reference), definition),
            effects=bounds,
        )
        try:
            return tuple(state_profile(private, reference, level)["effects"])
        finally:
            bounds.close()

    return _cached(key, build)


def clear():
    global _BYTES, _BOUND_BYTES
    with _LOCK:
        _CACHE.clear()
        _BOUND_CACHE.clear()
        _BYTES = _BOUND_BYTES = 0
