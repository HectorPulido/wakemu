"""Ephemeral actor StateLedger membership, indexed by actual weak owners.

Area-manager ledgers need their separate admission proof. These indexes contain
no actor, ledger or Fight strong references and are never checkpoint fields.
"""
from collections import Counter
from weakref import WeakKeyDictionary, ref


_OWNERS = WeakKeyDictionary()
_LEDGERS = WeakKeyDictionary()


def _uids(value):
    from .combat_state_ledger import RunningState

    if type(value) is not tuple:
        return None
    result = Counter()
    for entry in value:
        if type(entry) is not RunningState or type(entry.uid) is not int:
            return None
        result[entry.uid] += 1
    return result


class _Index:
    def __init__(self):
        self.bindings = {}
        self.counts = Counter()
        self.uid_bindings = {}
        self.actor_counts = Counter()
        self.valid = True
        self.caster_valid = True
        self.caster_counts = Counter()
        self.caster_bindings = {}
        self.area_nonempty = {}
        self.dirty_casters = set()
        self.dirty_areas = set()


def reset_membership(owner):
    """Initialize/rebind at an explicit adoption boundary outside live journals."""
    _OWNERS[owner] = _Index()


def _invalidate(owner, index):
    # The journal must observe the old complete membership before fallback is
    # required. Never inspect unknown new entries or invoke their UID methods.
    freeze = getattr(owner, "_invalidate_live_scopes", None)
    if freeze is not None:
        freeze()
    _notify(owner, index.counts, {})
    index.valid = False
    index.caster_valid = False


def caster_roots(owner):
    index = _OWNERS.get(owner)
    return None if index is None or not index.caster_valid else index.caster_counts


def retired_ledger_dirty(owner):
    index = _OWNERS.get(owner)
    if index is None:
        return set(), set()
    return index.dirty_casters, index.dirty_areas


def _caster_update(index, key, entries, *, ledger=None):
    from .combat_state_ledger import RunningState

    identity = key if type(key) is int else key[-1]
    if ledger is not None and (
        type(ledger.actor_id) is not int or ledger.actor_id != identity
    ):
        index.caster_valid = False
    if type(entries) is not tuple:
        index.caster_valid = False
        return
    current = Counter()
    for entry in entries:
        if type(entry) is not RunningState:
            index.caster_valid = False
            return
        caster = entry.caster_id
        if caster is None:
            continue
        if type(caster) is not int:
            index.caster_valid = False
            return
        current[caster] += 1
    previous = index.caster_bindings.get(key, {})
    for caster in previous.keys() | current.keys():
        delta = current.get(caster, 0) - previous.get(caster, 0)
        if delta:
            count = index.caster_counts.get(caster, 0) + delta
            if count:
                index.caster_counts[caster] = count
            else:
                index.caster_counts.pop(caster, None)
            index.dirty_casters.add(caster)
    if current:
        index.caster_bindings[key] = current
    else:
        index.caster_bindings.pop(key, None)
    if type(key) is tuple and key[0] == "area":
        previous_nonempty = index.area_nonempty.get(key, False)
        nonempty = bool(entries)
        if previous_nonempty != nonempty:
            index.dirty_areas.add(identity)
        if nonempty:
            index.area_nonempty[key] = True
        else:
            index.area_nonempty.pop(key, None)


def ledger_identity_changed(ledger):
    """Identity mutation loses caster authority without changing UID semantics."""
    for owner_ref, key, actor_ref in tuple(_LEDGERS.get(ledger, ())):
        owner = owner_ref()
        index = None if owner is None else _OWNERS.get(owner)
        if index is not None:
            old = index.bindings.get(key)
            if old is not None and old[1]() is ledger:
                index.caster_valid = False
                if type(key) is tuple and key[0] == "area":
                    index.dirty_areas.add(key[-1])


def actor_identity_changed(actor):
    ledger = vars(actor).get("state_ledger")
    from .combat_state_ledger import StateLedger

    if type(ledger) is StateLedger:
        for owner_ref, key, actor_ref in tuple(_LEDGERS.get(ledger, ())):
            owner = owner_ref()
            index = None if owner is None else _OWNERS.get(owner)
            if index is not None and actor_ref() is actor:
                index.caster_valid = False


def _notify(owner, previous, current):
    callback = getattr(owner, "_notify_live_before", None)
    if callback is not None:
        for uid in previous.keys() | current.keys():
            if previous.get(uid, 0) != current.get(uid, 0):
                callback(uid)


def _replace_counts(index, previous, current, *, binding_key, actor=True):
    for uid in previous.keys() | current.keys():
        if current.get(uid, 0):
            index.uid_bindings.setdefault(uid, {})[binding_key] = None
        else:
            bucket = index.uid_bindings.get(uid)
            if bucket is not None:
                bucket.pop(binding_key, None)
                if not bucket:
                    del index.uid_bindings[uid]
        count = index.counts.get(uid, 0) - previous.get(uid, 0) + current.get(uid, 0)
        if count:
            index.counts[uid] = count
        else:
            index.counts.pop(uid, None)
        if actor:
            count = (
                index.actor_counts.get(uid, 0)
                - previous.get(uid, 0)
                + current.get(uid, 0)
            )
            if count:
                index.actor_counts[uid] = count
            else:
                index.actor_counts.pop(uid, None)


def detach_actor(owner, key):
    index = _OWNERS.get(owner)
    if index is None or key not in index.bindings:
        return
    binding = index.bindings[key]
    _notify(owner, binding[2], {})
    _replace_counts(index, binding[2], {}, binding_key=key, actor=type(key) is int)
    _caster_update(index, key, ())
    del index.bindings[key]


def attach_actor(owner, key, actor):
    from .combat_state import Actor
    from .combat_state_ledger import StateLedger

    index = _OWNERS.setdefault(owner, _Index())
    if type(key) is not int or type(actor) is not Actor:
        _invalidate(owner, index)
        return
    ledger = actor.state_ledger
    if type(ledger) is not StateLedger:
        _invalidate(owner, index)
        return
    current = _uids(ledger._entries)
    if current is None:
        _invalidate(owner, index)
        return
    old = index.bindings.get(key)
    previous = {} if old is None else old[2]
    _notify(owner, previous, current)
    _replace_counts(index, previous, current, binding_key=key)
    if type(actor.id) is not int or actor.id != key:
        index.caster_valid = False
    _caster_update(index, key, ledger._entries, ledger=ledger)
    index.bindings[key] = (ref(actor), ref(ledger), current)
    bindings = _LEDGERS.setdefault(ledger, [])
    # Remove dead and superseded entries while touching this one local ledger.
    bindings[:] = [
        entry
        for entry in bindings
        if entry[0]() is not None and not (entry[0]() is owner and entry[1] == key)
    ]
    bindings.append((ref(owner), key, ref(actor)))


def membership_live(owner):
    index = _OWNERS.get(owner)
    return None if index is None or not index.valid else index.counts.keys()


def membership_actor_live(owner):
    index = _OWNERS.get(owner)
    return None if index is None or not index.valid else index.actor_counts.keys()


def membership_bindings(owner, uid):
    """Locate current ledger owners, never cached RunningState objects.

    Multiple bindings remain visible for duplicate detection by the caller.
    Their order is binding insertion order, not a state-manager traversal proof.
    """
    if type(uid) is not int:
        return None
    index = _OWNERS.get(owner)
    if index is None or not index.valid:
        return None
    return tuple(index.uid_bindings.get(uid, ()))


def attach_detached(owner, actor):
    """Index the actual unpublished summon without enrolling it as a fighter."""
    from .combat_state import Actor
    from .combat_state_ledger import StateLedger

    index = _OWNERS.setdefault(owner, _Index())
    if type(actor) is not Actor or type(actor.id) is not int:
        _invalidate(owner, index)
        return
    ledger = actor.state_ledger
    if type(ledger) is not StateLedger:
        _invalidate(owner, index)
        return
    current = _uids(ledger._entries)
    if current is None:
        _invalidate(owner, index)
        return
    key = ("detached", actor.id)
    old = index.bindings.get(key)
    previous = {} if old is None else old[2]
    _notify(owner, previous, current)
    _replace_counts(index, previous, current, binding_key=key, actor=False)
    _caster_update(index, key, ledger._entries, ledger=ledger)
    index.bindings[key] = (ref(actor), ref(ledger), current)
    bindings = _LEDGERS.setdefault(ledger, [])
    bindings[:] = [
        entry
        for entry in bindings
        if entry[0]() is not None and not (entry[0]() is owner and entry[1] == key)
    ]
    bindings.append((ref(owner), key, ref(actor)))


def detach_detached(owner, actor, *, identity=None):
    from .combat_state import Actor

    if type(actor) is not Actor:
        return
    if identity is None:
        identity = actor.id
    if type(identity) is not int:
        return
    index = _OWNERS.get(owner)
    key = ("detached", identity)
    binding = None if index is None else index.bindings.get(key)
    if binding is not None and binding[0]() is actor:
        detach_actor(owner, key)


def detach_area(owner, key, *, role):
    detach_actor(owner, ("area", role, key))


def attach_area(owner, key, row, *, role):
    from .combat_area_membership import OwnedAreaRow
    from .combat_state_ledger import StateLedger

    index = _OWNERS.setdefault(owner, _Index())
    if (
        type(key) is not int
        or type(row) is not OwnedAreaRow
        or type(role) is not str
        or role not in ("native_effect_areas", "native_retired_area_managers")
        or any(type(field) is not str for field in row)
    ):
        _invalidate(owner, index)
        return
    binding_key = ("area", role, key)
    observers = getattr(row, "_membership_owners", [])
    observers[:] = [
        item
        for item in observers
        if item[0]() is not None
        and not (item[0]() is owner and item[1:] == (role, key))
    ]
    observers.append((ref(owner), role, key))
    row._membership_owners = observers
    if "state_ledger" not in row:
        detach_actor(owner, binding_key)
        return
    ledger = row["state_ledger"]
    if type(ledger) is not StateLedger:
        _invalidate(owner, index)
        return
    current = _uids(ledger._entries)
    if current is None:
        _invalidate(owner, index)
        return
    old = index.bindings.get(binding_key)
    previous = {} if old is None else old[2]
    _notify(owner, previous, current)
    _replace_counts(index, previous, current, binding_key=binding_key, actor=False)
    _caster_update(index, binding_key, ledger._entries, ledger=ledger)
    index.bindings[binding_key] = (ref(row), ref(ledger), current)
    bindings = _LEDGERS.setdefault(ledger, [])
    bindings[:] = [
        entry
        for entry in bindings
        if entry[0]() is not None
        and not (entry[0]() is owner and entry[1] == binding_key)
    ]
    bindings.append((ref(owner), binding_key, ref(row)))


def entries_changing(ledger, value):
    """Notify before publishing replacement membership; no native effects run."""
    bindings = _LEDGERS.get(ledger)
    if not bindings:
        return
    current = _uids(value)
    changes = []
    surviving = []
    for owner_ref, key, actor_ref in bindings:
        owner, actor = owner_ref(), actor_ref()
        if owner is None or actor is None:
            continue
        index = _OWNERS.get(owner)
        old = None if index is None else index.bindings.get(key)
        if type(key) is tuple and key[0] == "detached":
            actual = owner.detached_actors.get(key[1])
            current_ledger = actor.state_ledger
        elif type(key) is tuple:
            _, role, identity = key
            actual = owner.area_sources[role].get(identity)
            current_ledger = actor.get("state_ledger")
        else:
            actual = owner.actors.get(key)
            current_ledger = actor.state_ledger
        if (
            old is None
            or old[0]() is not actor
            or old[1]() is not ledger
            or actual is not actor
            or current_ledger is not ledger
        ):
            continue
        surviving.append((owner_ref, key, actor_ref))
        if current is None:
            _invalidate(owner, index)
            continue
        changes.append((owner, index, key, old, current.copy()))
    # Do all potentially rejecting journal callbacks before changing any counts.
    for owner, index, key, old, new in changes:
        from .combat_selected_scalar_proof import invalidate_ledger_recipes

        invalidate_ledger_recipes(owner, key, old[2].keys() | new.keys())
        _notify(owner, old[2], new)
    for owner, index, key, old, new in changes:
        _replace_counts(index, old[2], new, binding_key=key, actor=type(key) is int)
        _caster_update(index, key, value, ledger=ledger)
        index.bindings[key] = (old[0], old[1], new)
    bindings[:] = surviving


def actor_ledger_replaced(actor, old_ledger):
    """Rebind owners of this exact actor after an explicit ledger assignment."""
    from .combat_state_ledger import StateLedger

    if type(old_ledger) is not StateLedger:
        return
    for owner_ref, key, actor_ref in tuple(_LEDGERS.get(old_ledger, ())):
        owner = owner_ref()
        if owner is None or actor_ref() is not actor:
            continue
        from .combat_selected_scalar_proof import invalidate_ledger_recipes

        invalidate_ledger_recipes(owner, key, _uids(old_ledger.entries))
        if type(key) is tuple and key[0] == "detached":
            if owner.detached_actors.get(key[1]) is actor:
                attach_detached(owner, actor)
        elif type(key) is int and owner.actors.get(key) is actor:
            attach_actor(owner, key, actor)
