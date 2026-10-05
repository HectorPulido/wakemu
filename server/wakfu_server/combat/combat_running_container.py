"""Scoped authoritative PL serialization; no identity inferred from runner UIDs."""
from contextlib import contextmanager
from contextvars import ContextVar

_current = ContextVar("native_running_container", default=None)


@contextmanager
def running_container_scope(container, identity):
    if type(container.get("container_present")) is not bool:
        raise ValueError("Explicit native container presence required")
    if container["container_present"]:
        kind = container.get("container_type")
        if type(kind) is not int or type(identity) is not int:
            raise ValueError("Explicit native container identity required")
        value = (kind, identity)
    else:
        value = ()
    token = _current.set(value)
    try:
        yield
    finally:
        _current.reset(token)


def running_container_payload():
    from .combat_effects import _integer

    value = _current.get()
    return b"" if not value else _integer(9, value[0]) + _integer(10, value[1])
