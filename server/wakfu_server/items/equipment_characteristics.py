"""Ordered scalar equipment operations against native characteristic bounds."""
from functools import lru_cache

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_rows():
    return {
        int(identity): row
        for identity, row in native_catalog.load(
            DATA_ROOT / "native-actor-characteristics.json"
        )["characteristics"].items()
    }


def apply_scalar(current, row, amount, subtract):
    """Original PA.nG/oo directed capacity and signed-int arithmetic."""
    if subtract and amount > current - row["minimum"]:
        value = row["minimum"]
    elif not subtract and amount > row["maximum"] - current:
        value = row["maximum"]
    else:
        value = current - amount if subtract else current + amount
        value = ((value + (1 << 31)) % (1 << 32)) - (1 << 31)
    return min(row["maximum"], max(row["minimum"], value))


def trace(operations, *, baseline=None):
    """Materialize scalar PA state and retain each effect's actual inverse."""
    rows = native_rows()
    initial = {
        identity: row["current"] if baseline is None else baseline[identity]
        for identity, row in rows.items()
        if not row["expandable"] and not row["frozen"]
    }
    current, inverse = dict(initial), []
    for identity, amount, subtract in operations:
        if identity not in current:
            inverse.append(None)
            continue
        before = current[identity]
        current[identity] = apply_scalar(before, rows[identity], amount, subtract)
        actual = (
            (before - current[identity]) if subtract else (current[identity] - before)
        )
        actual = ((actual + (1 << 31)) % (1 << 32)) - (1 << 31)
        inverse.append((identity, actual, not subtract))
    return initial, current, inverse


def replay(operations, identities, *, baseline=None):
    """Return effective deltas after each native scalar operation clips.

    Callers supply operations in native source/slot/effect order. NPC callers
    supply their actual breed-and-level baseline instead of player defaults.
    The returned deltas remain compatible with existing snapshot consumers:
    applying one delta to the same baseline yields the already reduced value.
    Expandable resource characteristics are owned by their existing reducer.
    """
    rows = native_rows()
    initial, current = {}, {}
    for identity in identities:
        row = rows.get(identity)
        if row is None or row["expandable"] or row["frozen"]:
            raise ValueError("Unsupported ordered equipment characteristic")
        value = row["current"] if baseline is None else baseline[identity]
        if type(value) is not int or not row["minimum"] <= value <= row["maximum"]:
            raise ValueError("Invalid native equipment characteristic baseline")
        initial[identity] = current[identity] = value
    for identity, amount, subtract in operations:
        if identity not in current:
            continue
        if type(amount) is not int or not -(1 << 31) <= amount < (1 << 31):
            raise ValueError("Invalid native scalar equipment amount")
        row = rows[identity]
        if type(subtract) is not bool:
            raise ValueError("Invalid native scalar equipment operation")
        current[identity] = apply_scalar(current[identity], row, amount, subtract)
    return {
        identity: ((value - initial[identity] + (1 << 31)) % (1 << 32)) - (1 << 31)
        for identity, value in current.items()
    }
