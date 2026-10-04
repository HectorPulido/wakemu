"""Execution-local Qe owner objects shared by native authority providers.

Native Qe.bfq keeps the actual PL/fyW object. A sibling can replace the live
state while that object remains the current iterator's owner. Nothing here is
stored on Fight, checkpointed, or available to a later event after scope exit.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_scopes = ContextVar("native_state_container_scopes", default=())


@contextmanager
def state_container_scope(fight, entries):
    token = _scopes.set(_scopes.get() + ((fight, dict(entries)),))
    try:
        yield
    finally:
        _scopes.reset(token)


def resolve_state_container(fight, uid):
    entries = [
        entry
        for actor in fight.actors.values()
        for entry in actor.state_ledger.entries
        if entry.uid == uid
    ]
    if len(entries) > 1:
        raise ValueError("Missing unique native state effect container")
    if entries:
        return entries[0]
    for owner, scope in reversed(_scopes.get()):
        if owner is fight and uid in scope:
            return scope[uid]
    raise ValueError("Missing unique native state effect container")
