"""Actor projections shared only while evaluating a read-only cell selection."""
from contextlib import contextmanager
from contextvars import ContextVar


_selection = ContextVar("combat_condition_actor_selection", default=None)


@contextmanager
def condition_actor_selection_scope(*, enabled=True):
    """Isolate each selection; release all projections before effects execute."""
    parent = _selection.get()
    if not enabled and parent is None:
        yield
        return
    token = _selection.set({} if enabled else None)
    try:
        yield
    finally:
        if not enabled and parent is not None:
            # An arbitrary nested callback can mutate actors. Existing outer
            # readers keep these dict references, so invalidate them in place.
            for _, _, cache in parent.values():
                cache.clear()
        _selection.reset(token)


def current_condition_actor_cache(adapter, preview):
    """Return this adapter/preview's memo, or None outside pure filtering."""
    selection = _selection.get()
    if selection is None:
        return None
    key = (id(adapter), id(preview))
    entry = selection.get(key)
    if entry is None:
        # Strong references prevent identity reuse during this short scope.
        entry = (adapter, preview, {})
        selection[key] = entry
    return entry[2]
