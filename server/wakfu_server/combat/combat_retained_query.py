"""Fresh manager-local retained authority, independent of encounter scopes.

Stage 1 builds routing from current primitive storage per query. No ownership,
view or live-row proof survives this call. Stage 2 can replace Routing with an
owned mutation index without changing the query/validation contract.
"""
from .combat_owned_container_facts import OwnedContainerFacts
from .combat_owned_container_row import OwnedContainerRow

from .combat_source_parent_index import OwnedStateSourceRow

from collections import Counter
from types import SimpleNamespace
from .combat_state import Fight, Actor
from .combat_state_ledger import StateLedger, RunningState
from .combat_state_managers import state_manager, state_managers
from .combat_retained_effects import _RetainedManagerPass
from .combat_structural_uid_index import SOURCE_MAPS

_SOURCE_FIGHT_GET = Fight.__getattribute__
_SOURCE_ACTOR_GET = Actor.__getattribute__
_SOURCE_LEDGER_GET = StateLedger.__getattribute__
_SOURCE_ENTRIES = StateLedger.__dict__["entries"]
_SOURCE_MANAGER = state_manager
_SOURCE_MANAGERS = state_managers
_FIELDS = (
    "actors",
    "native_retained_records",
    "native_retained_order",
    "state_wire_payloads",
    "native_effect_areas",
    "native_retired_area_managers",
    "native_owned_state_containers",
    "native_retained_tracking",
    *SOURCE_MAPS,
)


def _plain_rows(rows):
    return (type(rows) is dict or type(rows) is OwnedContainerFacts) and all(
        type(uid) is int
        and (
            type(row) is dict
            or type(row) is OwnedStateSourceRow
            or type(row) is OwnedContainerRow
        )
        and all(type(key) is str for key in row)
        for uid, row in rows.items()
    )


class Routing:
    """Query-owned locator. It supplies no actor or payload authorization."""

    def __init__(self, fight, fields):
        self.fight, self.fields = fight, fields
        self.by_manager = {}
        self.carriers = {}
        self.ordinals = {}
        self.valid = False
        records, order = (
            fields["native_retained_records"],
            fields["native_retained_order"],
        )
        for uid, row in records.items():
            if type(row.get("uid")) is not int or row["uid"] != uid:
                return
            if type(row.get("manager_id")) is not int:
                return
        if (
            any(type(uid) is not int for uid in order)
            or len(order) != len(records)
            or set(order) != set(records)
        ):
            return
        for uid in order:
            self.by_manager.setdefault(records[uid]["manager_id"], []).append(uid)
        live = set(fields["state_wire_payloads"])
        for name in SOURCE_MAPS:
            rows = fields[name]
            self.ordinals[name] = {uid: pos for pos, uid in enumerate(rows)}
            live.update(rows)
        for actor in fields["actors"].values():
            ledger = actor.state_ledger
            for state in ledger.entries:
                if type(state) is not RunningState or type(state.uid) is not int:
                    return
                if state.uid in self.carriers:
                    return
                self.carriers[state.uid] = (actor, state)
                live.add(state.uid)
        from .combat_pending_state import pending_state_uids

        live.difference_update(pending_state_uids(fight))
        if live != set(records):
            return  # Preserve legacy reconcile/error behavior for incomplete inputs.
        self.valid = True

    def rows(self, name, uids):
        current, order = self.fields[name], self.ordinals[name]
        chosen = sorted((uid for uid in uids if uid in order), key=order.__getitem__)
        return ((uid, current[uid]) for uid in chosen)


class _CarrierLookup:
    """Resolve a dependency from current metadata and its actual local ledger."""

    def __init__(self, fight, managers=None):
        self.fight = fight
        self.managers = managers

    def get(self, uid):
        row = self.fight.native_retained_records.get(uid)
        if row is None:
            return None
        target = row.get("target_id")
        if type(target) is not int:
            return None
        actor = self.fight.actors.get(target)
        if actor is None:
            from .combat_retained_area_query import selected_area_manager

            actor = selected_area_manager(self.fight, target, managers=self.managers)
        elif type(actor) is not Actor:
            return None
        if (
            actor is None
            or type(actor.state_ledger) is not StateLedger
            or type(actor.state_ledger.entries) is not tuple
        ):
            return None
        found = None
        for state in actor.state_ledger.entries:
            if type(state) is not RunningState or type(state.uid) is not int:
                return None
            if state.uid == uid:
                if found is not None:
                    return None
                found = (actor, state)
        return found


class _ManagerLookup:
    def __init__(self, owner):
        self.owner = owner

    def get(self, identity, default=()):
        return self.owner.manager_uids(identity)


class IndexedRouting:
    """The current owned collections supply routing, never payload authority."""

    def __init__(self, fight, fields, owner):
        self.fight, self.fields, self.owner = fight, fields, owner
        self.by_manager = _ManagerLookup(owner)
        self.carriers = _CarrierLookup(fight)
        self.ordinals = SOURCE_MAPS  # Parent witnesses check actual source membership.
        self.valid = True

    def rows(self, name, uids):
        current = self.fields[name]
        return ((uid, current[uid]) for uid in self.owner.source_uids(name, uids))


def _indexed_routing(fight, fields):
    from .combat_retained_collections import bound_collections

    owner = bound_collections(fields)
    if owner is None:
        return None
    from .combat_pending_state import pending_state_uids

    if not owner.consistent(pending_state_uids(fight)):
        return None
    return IndexedRouting(fight, fields, owner)


def prepare_routing(fight):
    """Build a primitive locator, or return None for legacy fallback.

    Disconnected managers' payloads are deliberately not parsed. Relevant
    manager/carrier dependencies are read and validated again every time.
    """
    from . import combat_state_managers as manager_source
    from . import combat_retained_effects as view_source
    from . import combat_retained_runtime as runtime_source
    from .combat_summon_initialization import detached_actors

    if (
        type(fight) is not Fight
        or Fight.__getattribute__ is not _SOURCE_FIGHT_GET
        or _SOURCE_FIGHT_GET is not object.__getattribute__
        or Actor.__getattribute__ is not _SOURCE_ACTOR_GET
        or _SOURCE_ACTOR_GET is not object.__getattribute__
        or StateLedger.__getattribute__ is not _SOURCE_LEDGER_GET
        or _SOURCE_LEDGER_GET is not object.__getattribute__
        or "__getattr__" in Actor.__dict__
        or "__getattr__" in StateLedger.__dict__
        or any(name in Actor.__dict__ for name in ("id", "state_ledger"))
        or "_entries" in StateLedger.__dict__
        or StateLedger.__dict__.get("entries") is not _SOURCE_ENTRIES
        or manager_source.state_manager is not _SOURCE_MANAGER
        or view_source.state_manager is not _SOURCE_MANAGER
        or runtime_source.state_manager is not _SOURCE_MANAGER
        or manager_source.state_managers is not _SOURCE_MANAGERS
        or view_source.state_managers is not _SOURCE_MANAGERS
        or runtime_source.state_managers is not _SOURCE_MANAGERS
        or "__getattr__" in Fight.__dict__
        or any(name in Fight.__dict__ for name in _FIELDS)
        or detached_actors(fight)
    ):
        return None
    fields = vars(fight)
    if fields.get("native_retained_tracking") is not True:
        return None
    if any(name not in fields for name in _FIELDS):
        return None
    indexed = _indexed_routing(fight, fields)
    if indexed is not None:
        return indexed
    if (
        type(fields["actors"]) is not dict
        or any(
            type(key) is not int
            or type(actor) is not Actor
            or type(actor.id) is not int
            or actor.id != key
            or type(actor.state_ledger) is not StateLedger
            or type(actor.state_ledger.entries) is not tuple
            for key, actor in fields["actors"].items()
        )
        or type(fields["native_retained_order"]) is not list
        or type(fields["state_wire_payloads"]) is not dict
        or any(type(uid) is not int for uid in fields["state_wire_payloads"])
        or any(
            not _plain_rows(fields[name])
            for name in (
                "native_retained_records",
                "native_owned_state_containers",
                "native_effect_areas",
                "native_retired_area_managers",
                *SOURCE_MAPS,
            )
        )
    ):
        return None
    # Stage 1 does not fabricate area/retired-Qf authority. An actual area
    # ledger still uses the complete legacy constructor until its query proof
    # is implemented. Ordinary areas with null Qf do not force full views.
    if any(
        row.get("state_ledger") is not None
        for name in ("native_effect_areas", "native_retired_area_managers")
        for row in fields[name].values()
    ):
        return None
    routing = Routing(fight, fields)
    if not routing.valid:
        return None
    return routing


_UNSET = object()


class LocalQueries:
    """One pure query/read-pass; discard before a gameplay mutation/callback.

    Routing alone is shared. Every manager and parent payload is revalidated.
    """

    def __init__(self, fight):
        self.fight = fight
        self.routing = _UNSET

    def for_manager(self, identity):
        if self.routing is _UNSET:
            self.routing = prepare_routing(self.fight)
        if self.routing is None:
            return None
        return manager_query(self.fight, identity, _routing=self.routing)


def _scalar(value):
    return (
        value is None or type(value) is int or type(value) is bool or type(value) is str
    )


from .combat_retained_collections import TrackedRow, OwnedMap, RetainedCollections

_SCALAR_SOURCE_FIELDS = (
    "uid",
    "target_id",
    "effect_class",
    "state_uid",
    "payload",
    "caster_id",
    "generic_effect",
    "native_creation_source",
    "native_summon_actor_id",
    "native_manager_source",
    "native_manager_id",
)
_SCALAR_ROW_METHODS = tuple(
    (kind, name, getattr(kind, name))
    for kind in (TrackedRow, OwnedStateSourceRow)
    for name in (
        "__init__",
        "__setattr__",
        "__delattr__",
        "__setitem__",
        "__delitem__",
        "clear",
        "pop",
        "popitem",
        "update",
        "setdefault",
        "__ior__",
        "get",
        "values",
        "__iter__",
        "__getattribute__",
        "_invalidate_scalar",
    )
)


_SCALAR_GATEWAY_METHODS = tuple(
    (kind, name, getattr(kind, name))
    for kind, names in (
        (
            OwnedMap,
            (
                "__setitem__",
                "__delitem__",
                "clear",
                "pop",
                "popitem",
                "update",
                "setdefault",
                "__ior__",
                "__getitem__",
                "get",
                "__iter__",
                "__getattribute__",
                "__contains__",
                "keys",
                "items",
                "values",
                "__len__",
            ),
        ),
        (TrackedRow, ("_changed",)),
        (RetainedCollections, ("_record_changed", "_map_changed")),
        (OwnedStateSourceRow, ("_notify",)),
    )
    for name in names
)


def _row_scalar_proof(row, *, source, native_methods):
    kind = type(row)
    eligible = native_methods and (
        kind is OwnedStateSourceRow if source else kind is TrackedRow
    )
    if not native_methods and (kind is TrackedRow or kind is OwnedStateSourceRow):
        object.__setattr__(row, "_scalar_eligibility", None)
    if eligible:
        attributes = vars(row)
        if any(name in attributes for name in ("get", "values", "__iter__")):
            object.__setattr__(row, "_scalar_eligibility", None)
            return False  # Keep custom readers on the full fallback path.
        proof = attributes.get("_scalar_eligibility")
        if type(proof) is bool:
            return proof
    if source:
        proof = (
            all(type(key) is str for key in row)
            and all(_scalar(row.get(key)) for key in _SCALAR_SOURCE_FIELDS)
            and row.get("native_private_area") is None
        )
    else:
        proof = all(_scalar(value) for value in row.values())
    if eligible:
        object.__setattr__(row, "_scalar_eligibility", proof)
    return proof


def _selected_scalars(fight, routing, ids, manager_id=None):
    # No custom comparison/getter may mutate the locator while a selected
    # view is constructed. Inspect only values these validators will read.
    native_methods = all(
        getattr(kind, name) is method
        for kind, name, method in _SCALAR_ROW_METHODS + _SCALAR_GATEWAY_METHODS
    )
    from .combat_selected_scalar_proof import (
        SelectedScalarProofs,
        record_observed,
        source_observed,
    )

    proof = None
    # Six maps only, never their populations. Custom readers must execute the
    # original per-read path, including their observable callbacks.
    native_maps = (
        native_methods
        and "__getattr__" not in OwnedMap.__dict__
        and all(
            type(routing.fields[name]) is OwnedMap
            and not any(
                reader in vars(routing.fields[name])
                for reader in (
                    "__getitem__",
                    "get",
                    "__iter__",
                    "__getattribute__",
                    "__getattr__",
                    "__contains__",
                    "keys",
                    "items",
                    "values",
                    "__len__",
                )
            )
            for name in ("native_retained_records", "state_wire_payloads", *SOURCE_MAPS)
        )
    )
    if (
        type(routing) is IndexedRouting
        and type(manager_id) is int
        and type(ids) is tuple
    ):
        candidate = vars(routing.owner).get("_selected_scalar_proofs")
        if type(candidate) is SelectedScalarProofs:
            if not native_maps:
                candidate.invalidate(None)
            else:
                proof = candidate
                if proof.matches(manager_id, ids):
                    return True
    certifiable = proof is not None
    dependencies = set(ids)
    for uid in ids:
        owner = routing.fields["native_retained_records"][uid].get("owner_uid")
        if not _scalar(owner):
            return False
        if type(owner) is int:
            dependencies.add(owner)
    for uid in dependencies:
        row = routing.fields["native_retained_records"].get(uid)
        if row is not None and (
            type(routing) is not IndexedRouting
            or not record_observed(routing.owner, uid, row)
        ):
            certifiable = False
        if row is not None and not _row_scalar_proof(
            row, source=False, native_methods=native_methods
        ):
            return False
        wire = routing.fields["state_wire_payloads"].get(uid)
        if wire is not None and type(wire) is not str:
            return False
    for name in SOURCE_MAPS:
        for source_uid, row in routing.rows(name, ids):
            if type(routing) is not IndexedRouting or not source_observed(
                routing.owner, name, source_uid, row
            ):
                certifiable = False
            if type(row) is not dict and type(row) is not OwnedStateSourceRow:
                return False
            if not _row_scalar_proof(row, source=True, native_methods=native_methods):
                return False
    if certifiable:
        proof.install(manager_id, ids, dependencies)
    return True


def manager_query(fight, identity, *, _routing=None):
    routing = prepare_routing(fight) if _routing is None else _routing
    if routing is None or routing.fight is not fight or type(identity) is not int:
        return None
    fields = routing.fields
    actor = fields["actors"].get(identity)
    if actor is None:
        from .combat_retained_area_query import selected_area_manager

        actor = selected_area_manager(fight, identity)
    elif type(actor) is not Actor:
        return None
    if (
        actor is None
        or type(actor.id) is not int
        or actor.id != identity
        or type(actor.state_ledger) is not StateLedger
        or type(actor.state_ledger.entries) is not tuple
    ):
        return None
    ids = routing.by_manager.get(identity, ())
    if not _selected_scalars(fight, routing, ids, identity):
        return None
    from .combat_pending_state import pending_state_uids
    from .combat_selected_manager_recipe import reuse, remember

    pending = pending_state_uids(fight)
    indexed = type(routing) is IndexedRouting
    if indexed:
        reused = reuse(routing, identity, pending)
        if reused is not None:
            return reused
    # Selected values/targets must have native primitive keys and actor PVs.
    # Unknown/custom target lookup behavior retains its complete legacy path.
    for uid in ids:
        record = fields["native_retained_records"][uid]
        target = record.get("target_id")
        if target is not None:
            if type(target) is not int:
                return None
            if target not in fields["actors"]:
                from .combat_retained_area_query import selected_area_target

                if not selected_area_target(fight, target):
                    return None
    from .combat_selected_retained_values import SelectedRetainedValues
    from .combat_structural_event_view import (
        root_carrier_witnesses,
        NativeRetainedEventView,
    )
    from .combat_pending_state import pending_state_uids

    frame = SimpleNamespace(
        counts=Counter(), frozen_rows=SelectedRetainedValues(fight, keep_current=False)
    )
    managers = _RetainedManagerPass(fight, _selected_identities=(identity,))
    managers.consume(fight)
    entries = frame.frozen_rows.read_batch(
        fight, ids, fields["native_retained_records"]
    )
    dependency_index = SimpleNamespace(
        carriers=_CarrierLookup(fight, managers), ordinals=routing.ordinals
    )
    parents = root_carrier_witnesses(
        fight,
        dependency_index,
        managers,
        frame.frozen_rows,
        frame.counts,
        entries,
        set(ids),
        pending_state_uids(fight),
    )
    if parents is None:
        return None
    result = NativeRetainedEventView(
        fight,
        entries,
        manager_id=identity,
        _manager_pass=managers,
        _rows=lambda name: routing.rows(name, ids),
        _parents=parents,
    )
    if indexed:
        remember(routing, identity, pending, managers, result)
    return result


class ReplayQueries:
    """Route reads; share selected views only in an explicit callback-free pass."""

    def __init__(self, retention):
        self.retention = retention
        self.queries = LocalQueries(retention.fight)
        self._cache_manager_views = False
        self._manager_views = {}

    def enable_read_pass_cache(self):
        # The replay scope discards this entire object before callbacks, nested
        # scopes, mutations and exit. Direct/local queries retain fresh reads.
        self._cache_manager_views = True

    def full_view(self):
        # Full legacy reads may synchronize/prune or invoke opaque callbacks.
        # Clear both sides, including failures or reentrant reads during view().
        enabled = self._cache_manager_views
        self._cache_manager_views = False
        self._manager_views.clear()
        self.queries = LocalQueries(self.retention.fight)
        try:
            return self.retention.view()
        finally:
            self._manager_views.clear()
            self.queries = LocalQueries(self.retention.fight)
            self._cache_manager_views = enabled

    def for_manager(self, identity):
        if self.queries.fight is not self.retention.fight:
            self._manager_views.clear()
            self.queries = LocalQueries(self.retention.fight)
        cacheable = self._cache_manager_views and type(identity) is int
        if cacheable and identity in self._manager_views:
            return self._manager_views[identity]
        result = self.queries.for_manager(identity)
        if result is not None:
            if cacheable and type(self.queries.routing) is IndexedRouting:
                self._manager_views[identity] = result
            return result
        return self.full_view()


def replay_queries(retention, *, indexed_only=False):
    from .combat_retained_runtime import (
        NativeRetainedRuntime,
        _SOURCE_VIEW,
        _SOURCE_SYNCHRONIZE,
        _SOURCE_LIVE,
    )

    if (
        type(retention) is not NativeRetainedRuntime
        or NativeRetainedRuntime.__getattribute__ is not object.__getattribute__
        or "__getattr__" in NativeRetainedRuntime.__dict__
        or getattr(retention.view, "__func__", None) is not _SOURCE_VIEW
        or getattr(retention.synchronize, "__func__", None) is not _SOURCE_SYNCHRONIZE
        or getattr(retention._live, "__func__", None) is not _SOURCE_LIVE
    ):
        return None
    queries = ReplayQueries(retention)
    if indexed_only:
        from .combat_retained_collections import OwnedMap

        fight = retention.fight
        if (
            type(fight) is not Fight
            or Fight.__getattribute__ is not object.__getattribute__
            or type(vars(fight).get("native_retained_records")) is not OwnedMap
        ):
            return None  # Do not build a historical Stage-1 locator just to decline it.
        routing = prepare_routing(fight)
        if type(routing) is not IndexedRouting:
            return None
        queries.queries.routing = routing
    return queries
