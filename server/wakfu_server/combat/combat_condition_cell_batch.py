"""Owned ordinary legacy QI bulk input, alive only during pure cell filtering.

No criterion or cell result is memoized here. Registry and range population
are explicit operation-owned working inputs, released before RNG/effects.
Every cell still resolves its actual target, builds its full context and runs
the original evaluator in order against one transaction-owned working input.
"""
import ast
from types import MethodType
from .combat_native_criterion_failure import (
    NativeCriterionRuntimeFailure,
    evaluate_native_effect_condition as _NATIVE_EVALUATOR,
)
from . import combat_conditions as _condition_module


PURE_CALLS = frozenset(
    (
        "IsTargetCellFree",
        "IsOnBorderCell",
        "HasLineOfSight",
        "GetEnnemyCountInRange",
        "GetAlliesCountInRange",
        "GetSpecificEffectAreaCountInRange",
    )
)


def batch_admission(reason):
    """Passive QA interception point; production stores no counters or data."""


def _canonical_evaluator(evaluator):
    return (
        evaluator is _NATIVE_EVALUATOR
        and _condition_module.evaluate_condition
        is _condition_module._CANONICAL_CONDITION_EVALUATOR
    )


def _overridden(instance):
    return any(
        type(name) is not str or callable(getattr(type(instance), name, None))
        for name in vars(instance)
    )


def _inert(value, depth=0):
    """Reject caller-defined iterators/getters in ordinary source records."""
    kind = type(value)
    if depth > 32:
        return False  # Cycles/deep caller graphs do not enter the bulk path.
    if value is None or kind in (bool, int, float, str, bytes):
        return True
    if kind is dict:
        return all(
            _inert(k, depth + 1) and _inert(v, depth + 1) for k, v in dict.items(value)
        )
    if kind in (tuple, list, set, frozenset):
        return all(_inert(v, depth + 1) for v in value)
    from datetime import datetime, date
    from decimal import Decimal
    from .combat_spell_level import NativeSpellBook
    from .combat_qi_snapshot import ImmutableQIMasks

    if kind in (datetime, date, Decimal):
        return True
    if kind is ImmutableQIMasks:
        return all(type(v) is int for v in value)
    if kind is NativeSpellBook:
        return all(_inert(v, depth + 1) for v in vars(value).values())
    return False


def pure_cell_criteria(criteria):
    from .combat_local_criteria import parse_local_criterion

    if type(criteria) is not str or not criteria.strip():
        return False
    try:
        root = parse_local_criterion(criteria.strip())
        calls = [node for node in ast.walk(root) if isinstance(node, ast.Call)]
        if not calls or any(
            not isinstance(node.func, ast.Name)
            or node.func.id not in PURE_CALLS
            or node.keywords
            for node in calls
        ):
            return False
        if any(
            node.id not in PURE_CALLS
            for node in ast.walk(root)
            if isinstance(node, ast.Name)
        ):
            return False
        return True
    except (ValueError, TypeError):
        return False


def _native_effect_mapping(mapping, depth=0):
    from .combat_static_catalogs import ImmutableCatalog, DefinitionOverlay
    from .combat_published_catalogs import PublishedStaticMapping

    if depth > 16:
        return False
    if type(mapping) is dict or type(mapping) is PublishedStaticMapping:
        return True
    if type(mapping) is ImmutableCatalog:
        return type(mapping._source) is dict and not _overridden(mapping)
    if type(mapping) is DefinitionOverlay:
        return (
            not _overridden(mapping)
            and _native_effect_mapping(mapping._base, depth + 1)
            and _native_effect_mapping(mapping._overrides, depth + 1)
        )
    return False


def _inert_effect(effect):
    from .combat_static_catalogs import ImmutableCatalog

    if type(effect) is ImmutableCatalog:
        return (
            type(effect._source) is dict
            and not _overridden(effect)
            and _inert(effect._source)
        )
    return _inert(effect)


class NativeConditionContextSource:
    """The same native callback binding as the former factory lambda."""

    def __init__(self, callback, fight, plan, effects):
        self.callback, self.fight, self.plan, self.effects = (
            callback,
            fight,
            plan,
            effects,
        )

    def __call__(self, invocation, *, condition_cell_batch=None):
        effect = self.effects[str(invocation.reference)]
        if condition_cell_batch is None:
            return self.callback(self.fight, self.plan, effect, invocation)
        return self.callback(
            self.fight,
            self.plan,
            effect,
            invocation,
            condition_cell_batch=condition_cell_batch,
        )


def _source_reason(adapter, fight):
    from .combat_runtime_adapter import NativeServerRuntimeAdapter, NativeCastAuthority
    from .combat_ordinary_authority import (
        OrdinaryActorAuthority,
        OrdinaryConditionCellQuery,
        _immutable_property_catalog,
        ordinary_cast_authority,
    )
    from .combat_summon import RegisteredSummonAuthority
    from .combat_npc_spellbook import ordinary_npc_spellbook
    from .combat_state import Fight, Actor
    from .combat_state_ledger import StateLedger, RunningState
    from .combat_characteristic_link import ObservableCharacteristicStats
    from .combat_input_observation import _active, _replaying

    if _active.get() is not None or _replaying.get() is not None:
        return "input_capture_or_replay"
    if type(adapter) is not NativeServerRuntimeAdapter or set(vars(adapter)) != {
        "actor_authority",
        "cast",
        "viewer_id",
    }:
        return "custom_adapter"
    if (
        type(fight) is not Fight
        or _overridden(fight)
        or hasattr(fight, "native_pointer_checkpoint")
    ):
        return "custom_or_pointer_fight"
    cast = adapter.cast
    if type(cast) is not NativeCastAuthority:
        return "custom_cast"
    capability = cast.condition_cell_query
    if (
        type(capability) is not OrdinaryConditionCellQuery
        or not capability.admitted(adapter)
        or capability.created_by is not ordinary_cast_authority
        or type(capability.policies) is not tuple
        or not capability.policies
        or any(
            type(row) is not tuple or len(row) != 2 or type(row[0]) is not str
            for row in capability.policies
        )
        or {name for name, _ in capability.policies}
        != set(vars(cast)) - {"condition_cell_query"}
        or any(getattr(cast, name) is not value for name, value in capability.policies)
    ):
        return "changed_cast_policy"
    authority = adapter.actor_authority
    if type(authority) is RegisteredSummonAuthority:
        if set(vars(authority)) != {"ordinary"}:
            return "custom_summon_wrapper"
        authority = authority.ordinary
    if type(authority) is not OrdinaryActorAuthority or _overridden(authority):
        return "custom_actor_authority"
    if authority.catalog is not _immutable_property_catalog():
        return "custom_property_catalog"
    if (
        authority.npc_spellbook is not None
        and authority.npc_spellbook is not ordinary_npc_spellbook
    ):
        return "custom_npc_spellbook"
    for name in ("characters", "monsters", "decks", "excluded_decks", "deck_caps"):
        if type(getattr(authority, name)) is not dict:
            return "custom_source_container"
    if authority.deck_blobs is not None and type(authority.deck_blobs) is not dict:
        return "custom_deck_container"
    if any(
        type(row) is not dict
        for row in (*authority.characters.values(), *authority.monsters.values())
    ):
        return "custom_actor_source"
    if any(
        not _inert(getattr(authority, name))
        for name in (
            "characters",
            "monsters",
            "decks",
            "excluded_decks",
            "deck_caps",
            "deck_blobs",
        )
    ):
        return "custom_nested_source"
    if (
        type(fight.actors) is not dict
        or type(getattr(fight, "native_effect_areas", {})) is not dict
    ):
        return "custom_population"
    if not _inert(getattr(fight, "native_effect_areas", {})):
        return "custom_area_records"
    if any(
        not _inert(getattr(fight, name, None))
        for name in (
            "native_qi_snapshot",
            "native_qi_slots",
            "native_qi_touched_cells",
            "native_qi_byte_topology",
        )
    ):
        return "custom_qi_input"
    for actor in fight.actors.values():
        if (
            type(actor) is not Actor
            or _overridden(actor)
            or type(actor.state_ledger) is not StateLedger
            or _overridden(actor.state_ledger)
            or type(actor.effect_stats) not in (dict, ObservableCharacteristicStats)
        ):
            return "custom_actor_or_ledger"
        if type(actor.effect_stats) is ObservableCharacteristicStats and (
            _overridden(actor.effect_stats)
            or actor.effect_stats._fight is not fight
            or type(actor.effect_stats._identity) is not int
            or actor.effect_stats._identity != actor.id
        ):
            return "custom_stat_binding"
        entries = actor.state_ledger._entries
        if type(entries) not in (list, tuple) or any(
            type(row) is not RunningState
            or any(
                type(getattr(row, field)) is not int
                for field in ("reference", "level", "caster_id")
            )
            for row in entries
        ):
            return "custom_state_population"
        if (
            not all(_inert(v) for v in dict.values(actor.effect_stats))
            or type(actor.id) is not int
            or type(actor.team) is not int
            or type(actor.physical_radius) is not int
            or any(
                type(getattr(actor, field, None)) is not dict
                or not _inert(getattr(actor, field))
                for field in ("effect_minima", "effect_maxima")
            )
            or type(actor.effect_frozen) not in (tuple, list, set, frozenset)
            or any(type(v) is not int for v in actor.effect_frozen)
            or type(actor.position) not in (tuple, list)
            or any(type(v) is not int for v in actor.position)
            or any(
                not _inert(getattr(actor, field, None))
                for field in (
                    "native_world_properties",
                    "native_fight_properties",
                    "native_cosmetic_state",
                )
            )
        ):
            return "custom_actor_values"
    return None


def read_condition_cell_batch(adapter, fight, plan, effect, invocation, batch):
    from .combat_effect_dispatch import EffectInvocation

    if (
        type(invocation) is not EffectInvocation
        or type(batch) is not LegacyConditionCellBatch
        or not batch.active
        or batch.adapter is not adapter
        or batch.fight is not fight
        or batch.plan is not plan
        or invocation.reference != batch.reference
    ):
        return None
    return batch.read(invocation)


class LegacyConditionCellBatch:
    def __init__(self, factory, effect, reference):
        self.factory, self.adapter, self.fight, self.plan = (
            factory,
            factory.adapter,
            factory.fight,
            factory.plan,
        )
        self.reference = reference
        self.active, self.registry = False, None
        self.range_population = None
        self.range_population_anchor = None
        self.condition_program = None
        self.condition_program_criteria = None

    def __enter__(self):
        if self.factory.changed():
            batch_admission("changed_before_filter")
            return self
        self.active = True
        batch_admission("admitted")
        return self

    def __exit__(self, *errors):
        self.active, self.registry = False, None
        self.range_population = None
        self.range_population_anchor = None
        program, self.condition_program = self.condition_program, None
        self.condition_program_criteria = None
        if program is not None:
            program.close()

    def condition(self, invocation):
        if not self.active:
            return self.factory.context(invocation)
        return self.factory.context(invocation, condition_cell_batch=self)

    def evaluate(self, criteria, context, evaluator):
        if not self.active:
            return evaluator(criteria, context)
        if not _canonical_evaluator(evaluator):
            self.__exit__()
            batch_admission("custom_evaluator_during_filter")
            return evaluator(criteria, context)
        from .combat_conditions import prepare_operation_condition_program

        try:
            if (
                self.condition_program is not None
                and self.condition_program_criteria != criteria
            ):
                return evaluator(criteria, context)
            if self.condition_program is None:
                program = prepare_operation_condition_program(criteria, context)
                if program is None:
                    return evaluator(criteria, context)
                self.condition_program = program
                self.condition_program_criteria = criteria
            return self.condition_program.evaluate(context)
        except NativeCriterionRuntimeFailure:
            # Preserve eZR.I's WHOLE-criterion rejection, including OR/not.
            return False

    def read(self, invocation):
        from .combat_casting_context import resolve_criterion_cell_invocation
        from .combat_qi_fight import current_registry
        from .combat_qi_registry import NativeQIRegistry
        from .combat_effect_dispatch import EffectInvocation

        if type(invocation) is not EffectInvocation:
            return None

        # Invoked at the original adapter operand, after its retained-reader
        # preparation. Never read QI eagerly at dispatcher/filter entry.
        if self.registry is None and invocation.cell is not None:
            registry = current_registry(self.fight)
            if type(registry) is not NativeQIRegistry:
                self.active = False
                batch_admission("nonlegacy_registry")
                return None
            self.registry = registry
        return resolve_criterion_cell_invocation(
            self.adapter,
            self.fight,
            invocation,
            return_obstacle=True,
            _registry=self.registry,
        )


class NativeCellBatchFactory:
    def __init__(self, adapter, fight, plan, dispatcher):
        self.adapter, self.fight, self.plan, self.dispatcher = (
            adapter,
            fight,
            plan,
            dispatcher,
        )
        self.context = dispatcher.condition_context
        self.context_binding = (
            self.context.callback,
            self.context.fight,
            self.context.plan,
            self.context.effects,
        )
        self.callbacks = tuple(
            (name, getattr(dispatcher, name))
            for name in (
                "condition_context",
                "group_cells",
                "actor_position",
                "group_random",
            )
        )

    def changed(self):
        source = self.dispatcher.condition_context
        return (
            type(source) is not NativeConditionContextSource
            or set(vars(source)) != {"callback", "fight", "plan", "effects"}
            or any(
                current is not prior
                for current, prior in zip(
                    (source.callback, source.fight, source.plan, source.effects),
                    self.context_binding,
                )
            )
            or not _native_effect_mapping(source.effects)
            or _source_reason(self.adapter, self.fight) is not None
            or any(
                getattr(self.dispatcher, name) is not value
                for name, value in self.callbacks
            )
        )

    def __call__(self, effect, invocation, *, activation, evaluator=_NATIVE_EVALUATOR):
        from .combat_effect_dispatch import EffectInvocation

        if type(invocation) is not EffectInvocation:
            batch_admission("custom_invocation")
            return None
        if not _canonical_evaluator(evaluator):
            batch_admission("custom_evaluator")
            return None
        if activation is not None:
            batch_admission("direct_activation")
            return None
        reason = _source_reason(self.adapter, self.fight)
        if reason is not None:
            batch_admission(reason)
            return None
        if self.changed():
            batch_admission("changed_dispatch_callbacks")
            return None
        if not _inert_effect(effect) or not pure_cell_criteria(effect.get("criteria")):
            batch_admission("unsupported_criteria")
            return None
        return LegacyConditionCellBatch(self, effect, invocation.reference)


def native_cell_batch_factory(provider, fight, plan, dispatcher):
    from .combat_runtime_adapter import NativeServerRuntimeAdapter
    from .combat_effect_runtime import NativeRuntimeContexts
    from .combat_effect_dispatch import EffectDispatcher

    if (
        type(provider) is not NativeRuntimeContexts
        or type(dispatcher) is not EffectDispatcher
    ):
        batch_admission("custom_runtime_provider")
        return None
    callback = provider.condition
    if type(callback) is not MethodType:
        batch_admission("unproved_factory_callbacks")
        return None
    adapter = getattr(callback, "__self__", None)
    if (
        type(adapter) is not NativeServerRuntimeAdapter
        or getattr(callback, "__func__", None)
        is not NativeServerRuntimeAdapter.condition
        or type(dispatcher.condition_context) is not NativeConditionContextSource
        or dispatcher.condition_context.callback is not callback
        or dispatcher.condition_context.fight is not fight
        or dispatcher.condition_context.plan is not plan
        or dispatcher.condition_context.effects is not dispatcher.effects
        or set(vars(dispatcher.condition_context))
        != {"callback", "fight", "plan", "effects"}
        or provider.group_cells is not adapter.cast.group_cells
        or provider.cell_eligible is not adapter.cast.cell_eligible
    ):
        batch_admission("unproved_factory_callbacks")
        return None
    if not _native_effect_mapping(dispatcher.effects):
        batch_admission("custom_effect_mapping")
        return None
    return NativeCellBatchFactory(adapter, fight, plan, dispatcher)
