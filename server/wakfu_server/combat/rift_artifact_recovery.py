"""Reconcile producer references against native artifact lifetime and receipts.

Native removal is authoritative: never resurrect a consumed Qq, fabricate a
grant, or discard earned states. A temporarily unavailable recipient postpones
only its assignment, not the player's action or the next wave.
"""
from .combat_state import Fight as _Fight
from .combat_effect_area_events import NativeAreaEventRuntime as _NativeAreaEvents
from .combat_effect_dispatch import EffectDispatcher as _EffectDispatcher
from .combat_effect_dispatch import evaluate_condition as _EFFECT_CONDITION
from .combat_artifact_assignment import (
    artifact_assignment_eligible as _ARTIFACT_ASSIGNMENT_ELIGIBLE,
)
from .combat_condition_cell_batch import (
    NativeConditionContextSource as _NativeConditionContextSource,
)
from .combat_runtime_adapter import NativeServerRuntimeAdapter as _NativeAdapter
from .combat_ordinary_authority import OrdinaryActorAuthority as _OrdinaryAuthority
from .combat_summon import RegisteredSummonAuthority as _SummonAuthority
from .combat_static_catalogs import (
    DefinitionOverlay as _DefinitionOverlay,
    ImmutableCatalog as _ImmutableCatalog,
)
from .combat_published_catalogs import (
    PublishedStaticMapping as _PublishedStaticMapping,
    static_catalog_descriptor as _static_catalog_descriptor,
)

_ORIGINAL_IN_PLAY = _Fight._in_play
_ORIGINAL_AREA_ELIGIBLE = _NativeAreaEvents.artifact_assignment_eligible
_ORIGINAL_AREA_PROBE = _NativeAreaEvents._artifact_criterion_probe
_ORIGINAL_AREA_DEFINITION = _NativeAreaEvents._definition
_ORIGINAL_AREA_ROOT = _NativeAreaEvents._root_invocation
_ORIGINAL_ADAPTER_CONDITION = _NativeAdapter.condition
_ORIGINAL_CONDITION_SOURCE_CALL = _NativeConditionContextSource.__call__
_ORIGINAL_ORDINARY_CONDITION_PROJECTION = _OrdinaryAuthority.condition_projection
_ORIGINAL_SUMMON_CONDITION_PROJECTION = _SummonAuthority.condition_projection
_ORIGINAL_ORDINARY_CALL = _OrdinaryAuthority.__call__
_ORIGINAL_SUMMON_CALL = _SummonAuthority.__call__
_ORIGINAL_EFFECT_GETATTRIBUTE = _EffectDispatcher.__getattribute__
_ORIGINAL_AREA_GETATTRIBUTE = _NativeAreaEvents.__getattribute__
_ORIGINAL_ADAPTER_GETATTRIBUTE = _NativeAdapter.__getattribute__
_ORIGINAL_CONTEXT_GETATTRIBUTE = _NativeConditionContextSource.__getattribute__
_ORIGINAL_IMMUTABLE_METHODS = {
    name: getattr(_ImmutableCatalog, name)
    for name in ("__getitem__", "__iter__", "__len__", "get")
}
_ORIGINAL_IMMUTABLE_GETATTRIBUTE = _ImmutableCatalog.__getattribute__
_ORIGINAL_OVERLAY_METHODS = {
    name: getattr(_DefinitionOverlay, name)
    for name in ("__getitem__", "__contains__", "__iter__", "__len__", "get")
}
_ORIGINAL_OVERLAY_GETATTRIBUTE = _DefinitionOverlay.__getattribute__
_ORIGINAL_STATIC_DESCRIPTOR = _static_catalog_descriptor
_ORIGINAL_PUBLISHED_METHODS = {
    name: getattr(_PublishedStaticMapping, name)
    for name in (
        "__getitem__",
        "__contains__",
        "__iter__",
        "__len__",
        "items",
        "values",
    )
}
_ORIGINAL_PUBLISHED_GETATTRIBUTE = _PublishedStaticMapping.__getattribute__
from .combat_global_pv_read_view import in_play_actors as _ORIGINAL_IN_PLAY_ACTORS


def _native_readonly_effect_mapping(mapping, depth=0):
    """Accept exact frozen catalog containers without scanning definitions."""
    if depth > 16:
        return False
    kind = type(mapping)
    if kind is dict:
        return True
    if kind is _ImmutableCatalog:
        return (
            _ImmutableCatalog.__getattribute__ is _ORIGINAL_IMMUTABLE_GETATTRIBUTE
            and all(
                getattr(_ImmutableCatalog, name) is method
                for name, method in _ORIGINAL_IMMUTABLE_METHODS.items()
            )
            and set(vars(mapping)) == {"_source", "_views"}
            and type(vars(mapping)["_source"]) is dict
            and type(vars(mapping)["_views"]) is dict
        )
    if kind is _DefinitionOverlay:
        return (
            _DefinitionOverlay.__getattribute__ is _ORIGINAL_OVERLAY_GETATTRIBUTE
            and all(
                getattr(_DefinitionOverlay, name) is method
                for name, method in _ORIGINAL_OVERLAY_METHODS.items()
            )
            and set(vars(mapping))
            == {"_base", "_overrides", "_iteration_source", "_size"}
            and _native_readonly_effect_mapping(vars(mapping)["_base"], depth + 1)
            and type(vars(mapping)["_overrides"]) is dict
            and (
                vars(mapping)["_iteration_source"] is None
                or _native_readonly_effect_mapping(
                    vars(mapping)["_iteration_source"], depth + 1
                )
            )
        )
    if kind is _PublishedStaticMapping:
        return (
            _PublishedStaticMapping.__getattribute__ is _ORIGINAL_PUBLISHED_GETATTRIBUTE
            and all(
                getattr(_PublishedStaticMapping, name) is method
                for name, method in _ORIGINAL_PUBLISHED_METHODS.items()
            )
            and _static_catalog_descriptor is _ORIGINAL_STATIC_DESCRIPTOR
            and _static_catalog_descriptor(mapping) is not None
        )
    return False


def reconcile_artifact_group(fight, group):
    """Remove stale choice references without rewriting accepted grant history."""
    areas = fight.native_effect_areas
    remaining = []
    changed = False
    for uid in group["remaining"]:
        row = areas.get(uid)
        if row is None:
            retired = group.setdefault("retired", {})
            retired.setdefault(str(uid), "native_area_absent")
            changed = True
            continue
        if row.get("native_area_contract") != "faM" or row.get("reference") != group[
            "original"
        ].get(str(uid)):
            raise ValueError("Rift artifact live identity changed its original group")
        if uid not in remaining:
            remaining.append(uid)
        else:
            changed = True
    if changed:
        group["remaining"] = remaining
    return changed


def eligible_representative(fight, team, *, area_uid, area_events, _rosters=None):
    """Return a real eligible original fighter, or leave the choice pending."""
    from wakfu_server.combat_global_pv_read_view import in_play_actors

    if _rosters is None:
        actors = sorted(
            (
                actor
                for actor in in_play_actors(fight)
                if actor.team == team
                and actor.id not in getattr(fight, "native_summon_registrations", {})
            ),
            key=lambda actor: actor.id,
        )
    else:
        actors = _iteration_team_roster(_rosters, team)
    for actor in actors:
        if area_events.artifact_assignment_eligible(area_uid, actor.id):
            return actor.id
    return None


def _native_iteration_rosters(fight, area_events):
    """Prove one mutation-free native eligibility pass can reuse its roster."""
    if type(fight) is not _Fight or "_in_play" in vars(fight):
        return None

    from types import MethodType
    from .combat_native_criterion_failure import evaluate_native_effect_condition
    from .combat_effect_dispatch import evaluate_condition
    from . import combat_artifact_assignment, combat_global_pv_read_view

    if (
        _Fight._in_play is not _ORIGINAL_IN_PLAY
        or _Fight._in_play is not getattr(fight._in_play, "__func__", None)
        or _Fight.__getattribute__ is not object.__getattribute__
        or type(area_events) is not _NativeAreaEvents
        or area_events.fight is not fight
        or _NativeAreaEvents.__getattribute__ is not _ORIGINAL_AREA_GETATTRIBUTE
        or "artifact_assignment_eligible" in vars(area_events)
        or "_artifact_criterion_probe" in vars(area_events)
        or "_definition" in vars(area_events)
        or "_root_invocation" in vars(area_events)
        or _NativeAreaEvents.artifact_assignment_eligible is not _ORIGINAL_AREA_ELIGIBLE
        or _NativeAreaEvents._artifact_criterion_probe is not _ORIGINAL_AREA_PROBE
        or _NativeAreaEvents._definition is not _ORIGINAL_AREA_DEFINITION
        or _NativeAreaEvents._root_invocation is not _ORIGINAL_AREA_ROOT
        or combat_artifact_assignment.artifact_assignment_eligible
        is not _ARTIFACT_ASSIGNMENT_ELIGIBLE
        or not _native_readonly_effect_mapping(area_events.definitions)
    ):
        return None
    try:
        dispatcher = area_events.dispatcher
        context = dispatcher.condition_context
    except Exception:
        return None
    if (
        type(dispatcher) is not _EffectDispatcher
        or _EffectDispatcher.__getattribute__ is not _ORIGINAL_EFFECT_GETATTRIBUTE
        or not _native_readonly_effect_mapping(dispatcher.effects)
        or type(context) is not _NativeConditionContextSource
        or _NativeConditionContextSource.__getattribute__
        is not _ORIGINAL_CONTEXT_GETATTRIBUTE
        or set(vars(context)) != {"callback", "fight", "plan", "effects"}
        or context.fight is not fight
        or context.effects is not dispatcher.effects
        or evaluate_condition is not _EFFECT_CONDITION
        or evaluate_condition is not evaluate_native_effect_condition
        or combat_global_pv_read_view.in_play_actors is not _ORIGINAL_IN_PLAY_ACTORS
        or type(context.callback) is not MethodType
        or context.callback.__func__ is not _ORIGINAL_ADAPTER_CONDITION
        or _NativeAdapter.condition is not _ORIGINAL_ADAPTER_CONDITION
        or _NativeAdapter.__getattribute__ is not _ORIGINAL_ADAPTER_GETATTRIBUTE
        or _NativeConditionContextSource.__call__ is not _ORIGINAL_CONDITION_SOURCE_CALL
    ):
        return None
    adapter = context.callback.__self__
    if type(adapter) is not _NativeAdapter:
        return None
    if "condition" in vars(adapter):
        return None
    authority = adapter.actor_authority
    if type(authority) is _SummonAuthority:
        if set(vars(authority)) != {"ordinary"}:
            return None
        if (
            _SummonAuthority.condition_projection
            is not _ORIGINAL_SUMMON_CONDITION_PROJECTION
        ):
            return None
        if _SummonAuthority.__call__ is not _ORIGINAL_SUMMON_CALL:
            return None
        authority = authority.ordinary
    if (
        type(authority) is not _OrdinaryAuthority
        or "condition_projection" in vars(authority)
        or _OrdinaryAuthority.condition_projection
        is not _ORIGINAL_ORDINARY_CONDITION_PROJECTION
    ):
        return None
    if (
        _OrdinaryAuthority.__call__ is not _ORIGINAL_ORDINARY_CALL
        or _OrdinaryAuthority.__getattribute__ is not object.__getattribute__
        or _SummonAuthority.__getattribute__ is not object.__getattribute__
    ):
        return None
    # Queries above run only the exact native criterion adapter and never
    # assign/remove an artifact. The roster can be reused until assignment.
    registrations = vars(fight).get("native_summon_registrations", {})
    if type(registrations) is not dict:
        return None
    return dict(
        actors=_ORIGINAL_IN_PLAY_ACTORS(fight),
        summons=frozenset(registrations),
        by_team={},
    )


def _iteration_team_roster(cache, team):
    roster = cache["by_team"].get(team)
    if roster is None:
        roster = tuple(
            sorted(
                (
                    actor
                    for actor in cache["actors"]
                    if actor.team == team and actor.id not in cache["summons"]
                ),
                key=lambda actor: actor.id,
            )
        )
        cache["by_team"][team] = roster
    return roster


def finish_pending_pairs(dispatcher, group, *, npc_team, before_wave=None):
    """Retry unfulfilled opponent choices through actual native activation."""
    fight = dispatcher.native_retention.fight
    changed = reconcile_artifact_group(fight, group)
    pending = group.get("pending_pairs", [])
    for request in tuple(pending):
        candidates = []
        rosters = _native_iteration_rosters(fight, dispatcher.native_area_events)
        for uid in group["remaining"]:
            recipient = eligible_representative(
                fight,
                npc_team,
                area_uid=uid,
                area_events=dispatcher.native_area_events,
                _rosters=rosters,
            )
            if recipient is not None:
                candidates.append((uid, recipient))
        if not candidates:
            continue
        rng = dispatcher.rift_artifact_rng
        paired, recipient = candidates[rng.randrange(len(candidates))]
        if not dispatcher.native_area_events.assign_artifact(paired, recipient):
            changed |= reconcile_artifact_group(fight, group)
            continue
        group["remaining"] = [uid for uid in group["remaining"] if uid != paired]
        assignment = dict(request, opponent=paired, recipient=recipient)
        if before_wave is not None:
            assignment["before_wave"] = before_wave
        group["assignments"].append(assignment)
        pending.remove(request)
        changed = True
    if not pending:
        group.pop("pending_pairs", None)
    return changed
