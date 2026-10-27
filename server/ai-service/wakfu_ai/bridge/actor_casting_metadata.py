"""Bounded immutable selected-level costs for advisory actor repertoires."""
from collections import OrderedDict, namedtuple
from sys import getsizeof
from threading import RLock


CostMetadata = namedtuple("CostMetadata", "options categories conditional")
_RECORDS = OrderedDict()
_LOCK = RLock()
_BYTES = 0
_MAX_ENTRIES = 512
_MAX_BYTES = 1024 * 1024


def _metadata(record, index):
    options = (record["costs"][index],) + tuple(
        rule["levels"][index] for rule in record.get("conditional", ())
    )
    return CostMetadata(
        tuple(tuple(values[:3]) for values in options),
        tuple(record.get("categories") or ()),
        bool(record.get("conditional")),
    )


def _size(value, seen):
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    if type(value) in (str, bytes, int, float, bool, type(None)):
        return getsizeof(value)
    if isinstance(value, tuple):
        return getsizeof(value) + sum(_size(child, seen) for child in value)
    raise TypeError("Mutable advisory casting metadata")


def selected_cost_metadata(spell, level):
    """Reuse only sealed publication rows; private and zero tables remain live.

    The projection contains no legality, condition result, actor modifier or
    ownership. Those must still be evaluated against each current actor.
    """
    global _BYTES
    from wakfu_server import combat_native_spell_casting as casting
    from wakfu_server.combat_published_catalogs import static_catalog_descriptor

    if type(level) is not int or level < 0:
        # Preserve the original table's validation before inspecting a source.
        casting.native_casting_table(spell, level)
    getter = getattr(casting, "catalog", None)
    source = getter() if level > 0 and callable(getter) else None
    descriptor = None if source is None else static_catalog_descriptor(source)
    if (
        descriptor is None
        or descriptor["revision"] == "0" * 64
        or source.representation != "native_json"
    ):
        options = {} if source is None else {"casting": source}
        return _metadata(*casting.native_casting_table(spell, level, **options))
    key = (descriptor["revision"], descriptor["collection"], str(spell), level)
    with _LOCK:
        found = _RECORDS.get(key)
        if found is not None:
            _RECORDS.move_to_end(key)
            return found[0]
    projection = getattr(casting, "selected_casting_projection", None)
    selected = None
    if callable(projection):
        try:
            selected = projection(spell, level, casting=source)
        except (KeyError, IndexError, TypeError, ValueError):
            pass
    if selected is not None and getattr(selected, "cost_categories", None) is not None:
        result = CostMetadata(
            (tuple(selected.baseline[:3]),)
            + tuple(tuple(rule[1][:3]) for rule in selected.rules),
            selected.cost_categories,
            bool(selected.rules),
        )
    else:
        result = _metadata(*casting.native_casting_table(spell, level, casting=source))
    try:
        charge = _size((key, result), set())
    except TypeError:
        return result
    if charge > _MAX_BYTES:
        return result
    with _LOCK:
        found = _RECORDS.get(key)
        if found is not None:
            _RECORDS.move_to_end(key)
            return found[0]
        _RECORDS[key] = result, charge
        _BYTES += charge
        while len(_RECORDS) > _MAX_ENTRIES or _BYTES > _MAX_BYTES:
            _, (_, removed) = _RECORDS.popitem(last=False)
            _BYTES -= removed
    return result


def _clear_cache():
    global _BYTES
    with _LOCK:
        _RECORDS.clear()
        _BYTES = 0


selected_cost_metadata.cache_clear = _clear_cache
