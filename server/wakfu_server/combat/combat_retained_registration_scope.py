"""Operation-entry membership without copying the retained population."""
from contextlib import contextmanager

from .combat_state_membership import membership_live
from .combat_state import Actor
from .combat_state_ledger import StateLedger


_ACTOR_GETTER = Actor.__getattribute__
_ACTOR_SETTER = Actor.__setattr__
_LEDGER_GETTER = StateLedger.__getattribute__
_LEDGER_SETTER = StateLedger.__setattr__
_LEDGER_ENTRIES = StateLedger.entries


class LiveJournal:
    def __init__(self, owner, pending_at_entry=()):
        self.owner = owner
        self.pending = frozenset(pending_at_entry)
        self.previous = {}
        self.complete = False
        if membership_live(owner) is None:
            raise ValueError("Retained registration requires indexed ledger membership")

    def _current(self, uid):
        ledgers = membership_live(self.owner)
        if ledgers is None:
            raise ValueError("Retained ledger membership lost during registration")
        return uid in self.owner.source_counts or uid in ledgers

    def touch(self, uid):
        """Capture once, before either source or ledger counts are changed."""
        if not self.complete and uid not in self.previous:
            self.previous[uid] = self._current(uid)

    def freeze_membership(self):
        """Fall back before opaque mutation makes indexed reads unavailable."""
        if self.complete:
            return
        ledgers = membership_live(self.owner)
        if ledgers is None:
            raise ValueError("Retained registration fallback requires prior membership")
        for uid in self.owner.source_counts.keys() | ledgers:
            self.previous.setdefault(uid, True)
        self.complete = True

    def __contains__(self, uid):
        if uid in self.pending:
            return False
        if uid in self.previous:
            return self.previous[uid]
        if self.complete:
            return False
        return self._current(uid)


@contextmanager
def live_registration_scope(owner, pending_at_entry=()):
    journal = LiveJournal(owner, pending_at_entry)
    scopes = getattr(owner, "_live_scopes", None)
    if scopes is None:
        scopes = owner._live_scopes = []
    scopes.append(journal)
    try:
        yield journal
    finally:
        # Preserve an outer scope after a nested handler raises.
        if not scopes or scopes[-1] is not journal:
            raise RuntimeError("Retained registration scope stack mismatch")
        scopes.pop()


def registration_candidates(owner, name):
    """Unregistered source UIDs in their original source insertion order."""
    return tuple(
        uid
        for uid in owner.source_uids(name, owner.unmatched)
        if uid not in owner.records
    )


def native_membership_owner(fight):
    """Admit indexed native actors; untracked manager sources use legacy reads."""
    from .combat_retained_collections import (
        bound_collections,
        bound_area_collections,
        SOURCE_NAMES,
        AREA_SOURCE_NAMES,
    )
    from .combat_summon_initialization import detached_actors
    from .combat_state import Fight

    if (
        type(fight) is not Fight
        or Fight.__getattribute__ is not object.__getattribute__
        or Actor.__getattribute__ is not _ACTOR_GETTER
        or Actor.__setattr__ is not _ACTOR_SETTER
        or StateLedger.__getattribute__ is not _LEDGER_GETTER
        or StateLedger.__setattr__ is not _LEDGER_SETTER
        or StateLedger.entries is not _LEDGER_ENTRIES
        or "__getattr__" in Fight.__dict__
        or "__getattr__" in Actor.__dict__
        or "__getattr__" in StateLedger.__dict__
        or any(name in Actor.__dict__ for name in ("id", "state_ledger"))
        or "_entries" in StateLedger.__dict__
        or any(
            name in Fight.__dict__
            for name in (
                "actors",
                "native_retained_records",
                "native_retained_order",
                *SOURCE_NAMES,
                *AREA_SOURCE_NAMES,
            )
        )
    ):
        return None
    fields = vars(fight)
    owner = bound_collections(fields)
    if (
        owner is None
        or not owner.valid
        or not bound_area_collections(fields, owner)
        or membership_live(owner) is None
    ):
        return None
    detached = detached_actors(fight)
    if (
        type(owner.detached_actors) is not dict
        or len(detached) != len(owner.detached_actors)
        or any(owner.detached_actors.get(actor.id) is not actor for actor in detached)
    ):
        return None
    return owner


def registration_owner(fight, handler):
    import sys

    cls = type(handler)
    module = sys.modules.get(cls.__module__)
    if (
        not cls.__module__.startswith("wakfu_server.")
        or module is None
        or getattr(module, cls.__name__, None) is not cls
    ):
        return None
    return native_membership_owner(fight)
