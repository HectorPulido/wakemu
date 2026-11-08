"""Operation-local reuse for certified ordinary external event producers."""
from .combat_retained_collections import OwnedMap
from contextlib import nullcontext
from types import MethodType
from . import combat_global_pv_collections as _collections


def external_read_pass(fight, replay, authority, retention):
    from .combat_event_replay import NativeEventReplay, NativeCloneAuthority
    from .combat_ordinary_events import (
        OrdinaryHealingEvents,
        OrdinaryDamageEvents,
        OrdinaryResourceLossEvents,
        OrdinaryArmorEvents,
        OrdinaryDisplacementEvents,
        _phase_read_pass,
        _fallback_phase_read_pass,
    )

    # Opaque forwarders must never inherit an enclosing ordinary read scope.
    fallback = lambda: _fallback_phase_read_pass(None)
    if (
        type(replay) is not NativeEventReplay
        or type(authority) is not NativeCloneAuthority
    ):
        return fallback()
    executable = authority.executable
    condition = authority.condition_context
    if type(executable) is not MethodType or type(condition) is not MethodType:
        return fallback()
    owner = executable.__self__
    if not (
        type(owner)
        in (
            OrdinaryHealingEvents,
            OrdinaryDamageEvents,
            OrdinaryResourceLossEvents,
            OrdinaryArmorEvents,
            OrdinaryDisplacementEvents,
        )
        and executable.__func__ is OrdinaryHealingEvents.executable
        and condition.__self__ is owner
        and condition.__func__ is OrdinaryHealingEvents.conditions
        and owner.preview is fight
        and owner.replay is replay
        and owner.retention is retention
        and owner.authority is authority
        and _collections.global_pv_iterator is _collections._SOURCE_GLOBAL_PV_ITERATOR
        and _collections.native_global_event_iterator
        is _collections._SOURCE_NATIVE_GLOBAL_EVENT_ITERATOR
        and _collections._collections is _collections._SOURCE_COLLECTIONS
        and _collections.NativeTroveLongMap is _collections._SOURCE_TROVE_TYPE
        and all(
            _collections.NativeTroveLongMap.__dict__.get(name) is method
            for name, method in _collections._SOURCE_TROVE_METHODS.items()
        )
    ):
        return fallback()
    if not _plain_iteration(fight):
        return fallback()
    return _phase_read_pass(owner, None)


def external_recipient_read(fight, identity, replay):
    from .combat_event_replay import NativeEventReplay
    from .combat_ordinary_events import _pure_area_recipient_read

    if type(replay) is not NativeEventReplay or replay._read_pass is None:
        return nullcontext()
    if identity in fight.actors or _pure_area_recipient_read(fight, identity):
        return nullcontext()
    # Geometry refresh and opaque area providers may reenter; suspend before
    # lookup and clear after it, including nullable Qf and exceptional exits.
    return replay._callback_read_boundary()


def _plain_topology(topology):
    if type(topology) is not dict or any(type(key) is not str for key in topology):
        return False
    return all(
        type(topology.get(key)) is list
        and all(type(value) is int for value in topology[key])
        for key in ("keys", "states")
    ) and all(
        type(topology.get(key)) is int for key in ("size", "free", "compact_removes")
    )


def _plain_state(state):
    if type(state) is not dict or any(type(key) is not str for key in state):
        return False
    status = state.get("fighter_status")
    retired = state.get("retired_fighters")
    return (
        type(state.get("source")) is str
        and type(state.get("mode")) is str
        and type(status) is dict
        and all(
            type(key) is str and type(value) is str for key, value in status.items()
        )
        and type(retired) is list
        and all(type(value) is int for value in retired)
        and all(
            _plain_topology(state.get(key)) for key in ("fighters", "areas", "extras")
        )
    )


def _plain_iteration(fight, captured=()):
    from .combat_state import Fight

    if type(fight) is not Fight:
        return False
    storage = object.__getattribute__(fight, "__dict__")
    actors = storage.get("actors")
    areas = storage.get("native_effect_areas", {})
    native_areas = False
    retired = storage.get("native_retired_area_managers")
    if type(areas) is OwnedMap or type(retired) is OwnedMap:
        if type(areas) is not OwnedMap or type(retired) is not OwnedMap:
            return False
        if (
            Fight.__getattribute__ is not object.__getattribute__
            or "__getattr__" in Fight.__dict__
            or any(
                name in Fight.__dict__
                for name in (
                    "actors",
                    "native_effect_areas",
                    "native_retired_area_managers",
                )
            )
        ):
            return False
        from .combat_retained_collections import (
            bound_collections,
            bound_area_collections,
        )

        readers = ("get", "__getitem__", "__contains__", "__iter__", "__getattribute__")
        if any(getattr(OwnedMap, name) is not getattr(dict, name) for name in readers):
            return False
        retired = storage.get("native_retired_area_managers")
        if (
            type(actors) is not OwnedMap
            or type(retired) is not OwnedMap
            or any(
                name in vars(rows)
                for rows in (actors, areas, retired)
                for name in readers
            )
        ):
            return False
        owner = bound_collections(storage)
        native_areas = owner is not None and bound_area_collections(storage, owner)
    return (
        (type(actors) is dict or type(actors) is OwnedMap)
        and all(type(key) is int for key in actors)
        and (type(areas) is dict or native_areas)
        and all(type(key) is int for key in areas)
        and _plain_state(storage.get("native_global_pv_collections"))
        and (
            not captured
            or (
                _plain_state(captured[0])
                and all(_plain_topology(topology) for topology in captured[1:])
            )
        )
        and _collections.global_pv_iterator is _collections._SOURCE_GLOBAL_PV_ITERATOR
        and _collections.native_global_event_iterator
        is _collections._SOURCE_NATIVE_GLOBAL_EVENT_ITERATOR
        and _collections._collections is _collections._SOURCE_COLLECTIONS
        and _collections.NativeTroveLongMap is _collections._SOURCE_TROVE_TYPE
        and all(
            _collections.NativeTroveLongMap.__dict__.get(name) is method
            for name, method in _collections._SOURCE_TROVE_METHODS.items()
        )
    )


def external_global_iterator(fight, caster_id):
    from .combat_ordinary_events import _fallback_phase_read_pass

    if not _plain_iteration(fight):
        with _fallback_phase_read_pass(None):
            yield from _collections.global_pv_iterator(fight, caster_id=caster_id)
        return
    state = object.__getattribute__(fight, "__dict__")["native_global_pv_collections"]
    captured = (state, *(state[key] for key in ("fighters", "areas", "extras")))
    iterator = _collections.global_pv_iterator(fight, caster_id=caster_id)
    while True:
        # Earlier reactions can replace a container or mutate the original
        # objects still held by native eligibility. Revoke before next().
        scope = (
            nullcontext()
            if _plain_iteration(fight, captured)
            else _fallback_phase_read_pass(None)
        )
        with scope:
            try:
                identity = next(iterator)
            except StopIteration:
                return
            yield identity
