"""Owner-local validated scalar recipes, never live views or actor authority.

Native source writes evict through the existing scalar UID dependency graph.
Ledger replacement evicts affected recipes; current weak actor/ledger bindings
and immutable entry tuples are also checked on every use. Unsupported manager
kinds continue through the full constructor.
"""
from weakref import ref
from .combat_state import Actor
from .combat_state_ledger import StateLedger, RunningState
from .combat_state_timing import StateTimer
from .combat_summon_initialization import registered_or_detached_actor
from .combat_private_target_aura import validate_private_target_aura
from .combat_subscription_contracts import GROUP_SUBSCRIPTION_FAMILIES
from .combat_retained_collections import OwnedMap
from .combat_retained_effects import RetainedEffect, _RetainedManagerPass
from .combat_selected_retained_values import SelectedRetainedValues, _owned_frozen_value
from .combat_structural_event_view import (
    NativeRetainedEventView,
    root_carrier_witnesses,
    validate_retained_entry_identity,
    _readonly_hex_identity_fields,
)

_VIEW_INIT = NativeRetainedEventView.__init__
_VIEW_NEW = NativeRetainedEventView.__new__
_EFFECT_INIT = RetainedEffect.__init__
_EFFECT_GET = RetainedEffect.__getattribute__
_METHODS = tuple(
    (kind, name, getattr(kind, name))
    for kind, names in (
        (RetainedEffect, ("__setattr__", "__delattr__")),
        (_RetainedManagerPass, ("__init__", "consume", "resolve")),
        (
            SelectedRetainedValues,
            ("__init__", "__getattribute__", "read", "read_batch"),
        ),
    )
    for name in names
)
_ACTOR_GET = Actor.__getattribute__
_LEDGER_GET = StateLedger.__getattribute__
_ENTRIES = StateLedger.__dict__["entries"]
_READERS = (
    "get",
    "__getitem__",
    "__iter__",
    "__getattribute__",
    "__contains__",
    "keys",
    "items",
    "values",
    "__len__",
)
_MAP_READERS = tuple((name, getattr(OwnedMap, name)) for name in _READERS)


def _native_actors(routing):
    from . import combat_structural_event_view as native_view
    from . import combat_selected_retained_values as selected_values
    from . import combat_private_target_aura as private_aura
    from . import combat_subscription_runners as subscription_runners

    actors = routing.fields["actors"]
    if (
        type(actors) is not OwnedMap
        or any(name in vars(actors) for name in (*_READERS, "__getattr__"))
        or any(getattr(OwnedMap, name) is not method for name, method in _MAP_READERS)
        or "__getattr__" in OwnedMap.__dict__
        or Actor.__getattribute__ is not _ACTOR_GET
        or _ACTOR_GET is not object.__getattribute__
        or StateLedger.__getattribute__ is not _LEDGER_GET
        or _LEDGER_GET is not object.__getattribute__
        or any(name in Actor.__dict__ for name in ("id", "state_ledger", "__getattr__"))
        or "_entries" in StateLedger.__dict__
        or "__getattr__" in StateLedger.__dict__
        or StateLedger.__dict__.get("entries") is not _ENTRIES
        or any(getattr(kind, name) is not method for kind, name, method in _METHODS)
        or selected_values.SelectedRetainedValues is not SelectedRetainedValues
        or selected_values._owned_frozen_value is not _owned_frozen_value
        or native_view.registered_or_detached_actor is not registered_or_detached_actor
        or private_aura.validate_private_target_aura is not validate_private_target_aura
        or subscription_runners.GROUP_SUBSCRIPTION_FAMILIES
        is not GROUP_SUBSCRIPTION_FAMILIES
        or native_view.NativeRetainedEventView is not NativeRetainedEventView
        or native_view.root_carrier_witnesses is not root_carrier_witnesses
        or native_view.validate_retained_entry_identity
        is not validate_retained_entry_identity
        or native_view._readonly_hex_identity_fields
        is not _readonly_hex_identity_fields
        or NativeRetainedEventView.__new__ is not _VIEW_NEW
        or NativeRetainedEventView.__init__ is not _VIEW_INIT
        or RetainedEffect.__init__ is not _EFFECT_INIT
        or RetainedEffect.__getattribute__ is not _EFFECT_GET
        or _EFFECT_GET is not object.__getattribute__
    ):
        return None
    return actors


def reuse(routing, identity, pending):
    proof = routing.owner._selected_scalar_proofs
    recipe = proof.event_recipes.get(identity)
    if recipe is None:
        return None
    actors = _native_actors(routing)
    certificate, prior_pending, pending_dependencies, bindings, entries, known = recipe
    if (
        actors is None
        or proof.managers.get(identity) is not certificate
        or pending.intersection(pending_dependencies) != prior_pending
    ):
        proof.event_recipes.pop(identity, None)
        return None
    for key, actor_ref, ledger_ref, states in bindings:
        actor, ledger = actor_ref(), ledger_ref()
        if (
            actor is None
            or ledger is None
            or actors.get(key) is not actor
            or type(actor) is not Actor
            or type(actor.id) is not int
            or actor.id != key
            or actor.state_ledger is not ledger
            or type(ledger) is not StateLedger
            or ledger.entries is not states
        ):
            proof.event_recipes.pop(identity, None)
            return None
    result = object.__new__(NativeRetainedEventView)
    result.fight = routing.fight
    result.entries = entries
    result.by_uid = {entry.uid: entry for entry in entries}
    result.known = dict(known)
    return result


def _plain_scalar(value):
    return (
        value is None or type(value) is int or type(value) is bool or type(value) is str
    )


def _scalar_carrier(state):
    # Holding a ledger tuple is bounded scalar storage only. A custom timer or
    # attached payload may contain an owner/Fight backedge and is not admitted.
    if type(state) is not RunningState:
        return False
    for key, value in vars(state).items():
        if type(key) is not str:
            return False
        if _plain_scalar(value):
            continue
        if type(value) is tuple and all(type(item) is int for item in value):
            continue
        if (
            key == "timer"
            and type(value) is StateTimer
            and all(
                type(name) is str and (_plain_scalar(item))
                for name, item in vars(value).items()
            )
        ):
            continue
        return False
    return True


def remember(routing, identity, pending, managers, view):
    proof = routing.owner._selected_scalar_proofs
    certificate = proof.managers.get(identity)
    actors = _native_actors(routing)
    if certificate is None or actors is None:
        return
    # The fresh view already validates scalar wire identities. Nonprivate
    # area rows have no geometry dependency; nullable groups resolve their
    # caster through the same registered actor binding retained below.
    ids = certificate[0]
    if routing.owner.source_uids("native_owned_spatial_effects", ids):
        return
    area_ids = frozenset(routing.owner.source_uids("native_owned_area_effects", ids))
    group_ids = routing.owner.sources["native_owned_group_effects"]
    for entry in view.entries:
        if (
            type(entry) is not RetainedEffect
            or entry.effect_class == 307
            or not all(
                type(key) is str and _plain_scalar(value)
                for key, value in vars(entry).items()
            )
        ):
            return
        if entry.uid in area_ids or entry.target_id is None:
            actor = managers.by_identity.get(entry.manager_id)
            if (
                type(actor) is not Actor
                or type(entry.manager_id) is not int
                or actors.get(entry.manager_id) is not actor
            ):
                return  # Detached and area managers retain full validation.
            if entry.uid in area_ids:
                row = routing.owner.sources["native_owned_area_effects"][entry.uid]
                if row.get("native_private_area") is not None:
                    return
            elif (
                entry.uid not in group_ids
                or entry.effect_class not in GROUP_SUBSCRIPTION_FAMILIES
            ):
                return
    bindings = []
    for key, actor in managers.by_identity.items():
        if (
            type(key) is not int
            or type(actor) is not Actor
            or actors.get(key) is not actor
            or type(actor.id) is not int
            or actor.id != key
            or type(actor.state_ledger) is not StateLedger
            or type(actor.state_ledger.entries) is not tuple
            or not all(_scalar_carrier(state) for state in actor.state_ledger.entries)
        ):
            return
        bindings.append(
            (key, ref(actor), ref(actor.state_ledger), actor.state_ledger.entries)
        )
    # Pending registrations affect only this manager's view when they name a
    # selected carrier, one of its dependency roots, an emitted selected row,
    # or a state in the selected manager's own ledger. Unrelated registrations
    # must not force this view to be rebuilt. Construct this small dependency
    # set once; reuse intersects the current pending set without scanning other
    # managers or their ledgers.
    dependencies = set(certificate[0])
    dependencies.update(certificate[1])
    for entry in view.entries:
        if type(entry.uid) is not int:
            return
        dependencies.add(entry.uid)
        if entry.owner_uid is not None:
            if type(entry.owner_uid) is not int:
                return
            dependencies.add(entry.owner_uid)
    selected_actor = managers.by_identity.get(identity)
    if (
        type(identity) is not int
        or type(selected_actor) is not Actor
        or actors.get(identity) is not selected_actor
        or type(selected_actor.state_ledger) is not StateLedger
        or type(selected_actor.state_ledger.entries) is not tuple
    ):
        return
    for state in selected_actor.state_ledger.entries:
        if type(state) is not RunningState or type(state.uid) is not int:
            return
        dependencies.add(state.uid)
    pending_dependencies = frozenset(dependencies)
    proof.event_recipes[identity] = (
        certificate,
        pending.intersection(pending_dependencies),
        pending_dependencies,
        tuple(bindings),
        view.entries,
        tuple(view.known.items()),
    )
