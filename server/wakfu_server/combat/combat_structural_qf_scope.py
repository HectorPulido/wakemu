"""Isolated admission-only selected-Qf proof; never persistent fight authority."""
from .combat_owned_container_facts import OwnedContainerFacts
from .combat_owned_container_row import OwnedContainerRow

from .combat_source_parent_index import OwnedStateSourceRow

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from collections import Counter
from copy import copy
from types import MethodType, FunctionType

_FRAMES = ContextVar("structural_qf_frames", default=())
COUNTS = Counter()


def _native_factory(factory, adapter, source):
    from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory
    from .combat_effect_runtime import NativeEffectRuntimeFactory, NativeRuntimeContexts
    from .combat_runtime_adapter import (
        NativeServerRuntimeAdapter,
        native_point_target_projection,
    )
    from .combat_state import Fight, Actor
    from .combat_effect_dispatch import EffectDispatcher
    from .combat_state_ledger import StateLedger
    from .combat_retained_collections import OwnedMap, TrackedRow
    from .combat_area_membership import OwnedAreaRow

    from . import combat_server_spell as paid_source
    from .combat_runtime_adapter import NativeCastAuthority
    from random import Random

    if (
        type(source) is not Fight
        or type(factory) is not NativeEffectRuntimeFactory
        or type(adapter) is not NativeServerRuntimeAdapter
    ):
        return False
    if "native_global_pv_collections" not in source.__dict__:
        return False
    if (
        paid_source.server_runtime is not _SOURCE_SERVER_RUNTIME
        or paid_source.ordinary_cast_authority is not _SOURCE_CAST_FACTORY
        or type(adapter.cast) is not NativeCastAuthority
        or NativeServerRuntimeAdapter.contexts is not _SOURCE_ADAPTER_CONTEXTS
        or NativeEffectRuntimeFactory.__call__ is not _SOURCE_FACTORY_CALL
        or OwnedEquipmentRuntimeFactory.__call__ is not _SOURCE_EQUIPMENT_CALL
        or EffectDispatcher.execute is not _SOURCE_DISPATCH_EXECUTE
        or EffectDispatcher.execute_activation is not _SOURCE_DISPATCH_ACTIVATE
    ):
        return False
    if type(source) is not Fight or type(factory) is not NativeEffectRuntimeFactory:
        return False
    if type(adapter) is not NativeServerRuntimeAdapter:
        return False
    raw = factory
    if (
        type(raw) is not NativeEffectRuntimeFactory
        or type(raw.contexts) is not NativeRuntimeContexts
    ):
        return False
    if type(raw.transaction_rng) is not Random:
        return False
    if native_point_target_projection(adapter.targets) is None:
        return False
    for field, method in (
        ("native_targets", "targets"),
        ("condition", "condition"),
        ("rounding", "random"),
        ("uid_start", "uid"),
        ("healing_events", "healing_events"),
        ("area_affiliation", "area_affiliation"),
    ):
        value = getattr(raw.contexts, field)
        original = _SOURCE_ADAPTER_METHODS[method]
        if NativeServerRuntimeAdapter.__dict__[method] is not original:
            return False
        if type(original) is staticmethod:
            if value is not original.__func__:
                return False
        elif (
            type(value) is not MethodType
            or value.__self__ is not adapter
            or value.__func__ is not original
        ):
            return False
    for field, method in (
        ("resolution", "resolution"),
        ("cell_eligible", "cell_eligible"),
        ("probability", "probability_accepts"),
        ("group_cells", "group_cells"),
        ("damage", "damage"),
        ("healing", "healing"),
        ("stat", "stat"),
        ("state", "state"),
        ("damage_block", "damage_block"),
    ):
        if getattr(raw.contexts, field) is not getattr(adapter.cast, method):
            return False
    if (
        raw.contexts.selected_surface is not None
        or raw.contexts.area_obstacle_register is not _SOURCE_AREA_REGISTER
    ):
        return False
    for name in ("actor_candidates", "state_spell_level", "state_random"):
        value = getattr(raw.contexts, name)
        if name == "state_random" and value is None:
            continue
        if (
            type(value) is not FunctionType
            or value.__code__ not in _SOURCE_CONTEXT_CODES
        ):
            return False
        if value.__closure__ is not None:
            try:
                if any(cell.cell_contents is not adapter for cell in value.__closure__):
                    return False
            except ValueError:
                return False
    if (type(source.actors) is not dict and type(source.actors) is not OwnedMap) or any(
        type(a) is not Actor or type(a.state_ledger) is not StateLedger
        for a in source.actors.values()
    ):
        return False
    # One entry-only native-storage gate. Custom maps/keys retain the legacy API.
    for name in (
        "native_retained_records",
        "owned_stat_effects",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
        "native_owned_state_containers",
        "native_effect_areas",
        "native_retired_area_managers",
    ):
        rows = source.__dict__.get(name, {})
        if (
            type(rows) is not dict
            and type(rows) is not OwnedMap
            and type(rows) is not OwnedContainerFacts
        ):
            return False
        if any(
            (
                type(row) is not dict
                and type(row) is not TrackedRow
                and type(row) is not OwnedAreaRow
                and type(row) is not OwnedStateSourceRow
                and type(row) is not OwnedContainerRow
            )
            or any(type(k) is not str for k in row)
            for row in rows.values()
        ):
            return False
    return True


def _full_check(retention, fight):
    """Run the existing full guard on registration-map shadows, not the source.

    synchronize may legitimately drop stale registry bookkeeping. Its normal
    operation runs only on private shallow map copies here, preserving the
    exact preview state and actual actor/state objects during pure validation.
    """
    from .combat_retained_runtime import NativeRetainedRuntime
    from .combat_state import Fight

    if type(retention) is not NativeRetainedRuntime or type(fight) is not Fight:
        raise ValueError("Unqualified private Qf full validation")
    from .combat_pending_state import pending_state_uids
    from .combat_summon_initialization import detached_actors

    if pending_state_uids(fight) or detached_actors(fight):
        raise ValueError(
            "Private Qf validation requires a closed native construction boundary"
        )
    shadow = copy(fight)
    shadow.native_retained_records = dict(fight.native_retained_records)
    shadow.native_retained_order = list(fight.native_retained_order)
    shadow.native_owned_state_containers = dict(
        getattr(fight, "native_owned_state_containers", {})
    )
    for name in ("native_effect_areas", "native_retired_area_managers"):
        setattr(
            shadow,
            name,
            {uid: dict(row) for uid, row in getattr(fight, name, {}).items()},
        )
    validator = copy(retention)
    validator.fight = shadow
    from .combat_state_managers import (
        _native_prune_owner,
        _shadow_prune_callbacks_known,
        qualified_prune_shadow,
    )

    source_owner = _native_prune_owner(fight)
    if source_owner is None or not _shadow_prune_callbacks_known(shadow):
        validator.view()
    else:
        # Only the exact source collections survive the shallow Fight copy.
        # Registry maps above are private shadows; the source-user relation
        # may be indexed once from the original, currently bound owner maps.
        with qualified_prune_shadow(shadow, source_owner):
            validator.view()


class Frame:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.retention = dispatcher.native_retention
        self.preview = self.retention.fight
        self.enabled = True
        self.suspended = 0
        self.counts = COUNTS
        from .combat_versioned_handlers import NativeVersionedHandlers

        handlers = dispatcher.handlers
        self.versioned_handlers = type(handlers) is NativeVersionedHandlers
        self.handlers = handlers if self.versioned_handlers else dict(handlers)
        self.handler_version = handlers.version if self.versioned_handlers else None
        from .combat_selected_retained_values import SelectedRetainedValues

        self.frozen_rows = SelectedRetainedValues(self.preview)


def event_frame(retention):
    from .combat_pending_state import pending_state_uids
    from .combat_summon_initialization import detached_actors

    for frame in reversed(_FRAMES.get()):
        if frame.retention is retention:
            if (
                not frame.enabled
                or frame.suspended
                or retention.fight is not frame.preview
                or detached_actors(frame.preview)
            ):
                return None
            # Pending Qe carriers stay excluded by the original manager view;
            # do not turn this transient native state into a global fallback.
            return frame
    return None


@contextmanager
def callback_projection_boundary(retention):
    frame = event_frame(retention)
    if frame is None:
        yield
        return
    frame.suspended += 1
    COUNTS["callback_fallbacks"] += 1
    try:
        yield
    finally:
        frame.suspended -= 1


def qualify_replay(dispatcher, retention, authority):
    frame = event_frame(retention)
    if frame is None:
        return
    handlers = dispatcher.handlers
    if frame.versioned_handlers:
        from .combat_versioned_handlers import NativeVersionedHandlers

        handlers_changed = (
            type(handlers) is not NativeVersionedHandlers
            or handlers is not frame.handlers
            or any(
                getattr(NativeVersionedHandlers, name) is not method
                for name, method in _VERSIONED_HANDLER_MUTATORS
            )
            or handlers.mutation_in_progress
            or handlers.version != frame.handler_version
        )
    else:
        handlers_changed = any(
            handlers.get(key) is not value for key, value in frame.handlers.items()
        ) or len(handlers) != len(frame.handlers)
    if (
        frame.dispatcher is not dispatcher
        or authority is not getattr(dispatcher, "native_clone_authority", None)
        or handlers_changed
    ):
        frame.enabled = False
        COUNTS["opaque_replay_revocations"] += 1


@contextmanager
def admission_scope(dispatcher):
    from .combat_effect_dispatch import EffectDispatcher
    from .combat_retained_runtime import NativeRetainedRuntime
    from .combat_pending_state import pending_state_uids
    from .combat_summon_initialization import detached_actors
    from .combat_runtime_adapter import NativeServerRuntimeAdapter

    if type(dispatcher) is not EffectDispatcher:
        yield
        return
    origin = getattr(dispatcher, "_structural_index_factory", None)
    retention = getattr(dispatcher, "native_retention", None)
    if type(retention) is not NativeRetainedRuntime or origin is None:
        COUNTS["entry_factory_fallbacks"] += 1
        yield
        return
    target = origin.contexts.native_targets
    adapter = target.__self__ if type(target) is MethodType else None
    fight = retention.fight
    if (
        type(adapter) is not NativeServerRuntimeAdapter
        or not _native_factory(origin, adapter, fight)
        or pending_state_uids(fight)
        or detached_actors(fight)
    ):
        COUNTS["entry_factory_fallbacks"] += 1
        yield
        return
    _full_check(retention, fight)
    COUNTS["entries"] += 1
    frame = Frame(dispatcher)
    token = _FRAMES.set((*_FRAMES.get(), frame))
    try:
        yield
        frame.enabled = False
        _full_check(retention, fight)
        COUNTS["ends"] += 1
    finally:
        frame.enabled = False
        _FRAMES.reset(token)


# Method identities are static source authorities, not gameplay/query results.
from .combat_runtime_adapter import NativeServerRuntimeAdapter as _Adapter
from .combat_effect_runtime import NativeEffectRuntimeFactory as _Factory
from .combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory as _Equipment

_SOURCE_ADAPTER_CONTEXTS = _Adapter.contexts
_SOURCE_FACTORY_CALL = _Factory.__call__
_SOURCE_EQUIPMENT_CALL = _Equipment.__call__
_SOURCE_ADAPTER_METHODS = {
    name: _Adapter.__dict__[name]
    for name in (
        "targets",
        "condition",
        "random",
        "uid",
        "healing_events",
        "area_affiliation",
    )
}
from . import combat_server_spell as _PaidSource

_SOURCE_SERVER_RUNTIME = _PaidSource.server_runtime
_SOURCE_CAST_FACTORY = _PaidSource.ordinary_cast_authority
from .combat_qi_fight import register_effect_area_obstacle as _SOURCE_AREA_REGISTER
from types import CodeType as _CodeType

_SOURCE_CONTEXT_CODES = frozenset(
    code
    for code in _SOURCE_ADAPTER_CONTEXTS.__code__.co_consts
    if type(code) is _CodeType
)
from .combat_effect_dispatch import EffectDispatcher as _Dispatcher

_SOURCE_DISPATCH_EXECUTE = _Dispatcher.execute
_SOURCE_DISPATCH_ACTIVATE = _Dispatcher.execute_activation
from .combat_versioned_handlers import (
    NativeVersionedHandlers as _NativeVersionedHandlers,
)

_VERSIONED_HANDLER_MUTATORS = tuple(
    (name, _NativeVersionedHandlers.__dict__[name])
    for name in (
        "__setitem__",
        "__delitem__",
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "update",
        "__ior__",
        "__setattr__",
        "__delattr__",
        "_begin_mutation",
        "_finish_mutation",
        "mutation_in_progress",
        "version",
    )
)
