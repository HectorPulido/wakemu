"""Queue authoritative changed characteristics after relative native effects."""
from itertools import repeat
from operator import is_
from .combat_wire import actor_state


_MAPS = (
    "effect_stats",
    "effect_minima",
    "effect_maxima",
    "effect_percentages",
    "effect_base_minima",
    "effect_base_maxima",
    "effect_resource_raw_currents",
    "effect_characteristic_raw_currents",
)


class _CharacteristicSnapshot(dict):
    """Private operation-local baseline; never attached to the fight graph."""


class _ScalarMapSnapshot:
    __slots__ = ("values",)

    def __init__(self, values):
        self.values = values.copy()


def _map_snapshot(value):
    # These snapshots are short-lived, detached copies, not bounded cache
    # entries. Exact integer identity makes equality/order callback-free even
    # for large integers; bool and all opaque values retain the legacy path.
    if (
        type(value) is dict
        and len(value) <= 4096
        and all(map(is_, map(type, value), repeat(int)))
        and all(map(is_, map(type, value.values()), repeat(int)))
    ):
        return _ScalarMapSnapshot(value)
    return tuple(sorted(value.items())) if isinstance(value, dict) else None


def _capture_characteristics(fight, *, _exclude=()):
    # Keep eager field/actor traversal, including opaque fallbacks, in the
    # legacy order. Only exact scalar maps avoid sorted tuple allocation.
    result = _CharacteristicSnapshot()
    for identity, actor in fight.actors.items():
        if identity in _exclude:
            continue
        if not isinstance(getattr(actor, "effect_stats", None), dict):
            continue
        result[identity] = (
            actor.hp,
            actor.ap,
            actor.mp,
            actor.max_hp,
            actor.max_ap,
            actor.max_mp,
            getattr(actor, "effect_hp_raw_current", None),
            tuple(
                (name, _map_snapshot(value))
                for name in _MAPS
                for value in (getattr(actor, name, None),)
            ),
        )
    return result


def _same_signature(before, after):
    if before is None:
        return False
    # Compare the scalar prefix first, matching tuple equality short-circuit.
    if not before[:7] == after[:7]:
        return False
    for (old_name, old), (new_name, new) in zip(before[7], after[7]):
        if not old_name == new_name:
            return False
        if type(old) is _ScalarMapSnapshot and type(new) is _ScalarMapSnapshot:
            if not old.values == new.values:
                return False
        else:
            # Preserve left-to-right custom equality when either map used the
            # legacy path. Do not dispatch equality through a wrapper object.
            old = (
                tuple(sorted(old.values.items()))
                if type(old) is _ScalarMapSnapshot
                else old
            )
            new = (
                tuple(sorted(new.values.items()))
                if type(new) is _ScalarMapSnapshot
                else new
            )
            if not old == new:
                return False
    return len(before[7]) == len(after[7])


def characteristic_signatures(fight, *, _exclude=()):
    """Copy values, never retain mutable preview dictionaries or PA bindings."""
    result = {}
    for identity, actor in fight.actors.items():
        if identity in _exclude:
            continue
        if not isinstance(getattr(actor, "effect_stats", None), dict):
            continue
        result[identity] = (
            actor.hp,
            actor.ap,
            actor.mp,
            actor.max_hp,
            actor.max_ap,
            actor.max_mp,
            getattr(actor, "effect_hp_raw_current", None),
            tuple(
                (
                    name,
                    tuple(sorted(value.items())) if isinstance(value, dict) else None,
                )
                for name in _MAPS
                for value in (getattr(actor, name, None),)
            ),
        )
    return result


def changed_characteristic_packets(fight, before, serialize, *, exclude=()):
    """Hydrate visible changed actors after callbacks; preserve native values."""
    if serialize is None:
        return []
    excluded = set(exclude)
    private = type(before) is _CharacteristicSnapshot
    # Presentation retirement is stronger than HP0/OFF_PLAY. Only use its
    # existing receipt-backed projection for native storage; custom readers
    # keep the original snapshot/equality/callback order.
    hidden = _early_hidden_characteristics(fight)
    skipped = () if hidden is None else hidden
    current = (
        _capture_characteristics(fight, _exclude=skipped)
        if private
        else characteristic_signatures(fight, _exclude=skipped)
    )
    changed = [
        identity
        for identity, signature in current.items()
        if identity not in excluded
        and (
            not _same_signature(before.get(identity), signature)
            if private
            else before.get(identity) != signature
        )
    ]
    if not changed:
        return []
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    if hidden is None:
        hidden = hidden_snapshot_actor_ids(fight)
    return [
        (
            12873,
            actor_state(
                12873, fight.id, identity, serialize(fight.actors[identity], fight)
            ),
        )
        for identity in changed
        if identity not in hidden
    ]


def _early_hidden_characteristics(fight):
    from .combat_state import Fight, Actor
    from .combat_retained_collections import OwnedMap, bound_collections
    from .combat_characteristic_link import ObservableCharacteristicStats
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    if type(fight) is not Fight or type(fight.actors) is not OwnedMap:
        return None
    if bound_collections(vars(fight)) is None:
        return None
    for name in ("items", "values", "get", "__iter__", "__getitem__"):
        if name in vars(fight.actors) or getattr(OwnedMap, name) is not getattr(
            dict, name
        ):
            return None
    for actor in dict.values(fight.actors):
        if type(actor) is not Actor:
            return None
        for name in _MAPS:
            value = getattr(actor, name, None)
            if value is None:
                continue
            if type(value) not in (dict, ObservableCharacteristicStats):
                return None
            if type(value) is ObservableCharacteristicStats:
                if any(
                    method in vars(value)
                    or getattr(type(value), method) is not getattr(dict, method)
                    for method in ("items", "values", "keys", "__iter__", "__getitem__")
                ):
                    return None
    try:
        hidden = hidden_snapshot_actor_ids(fight)
    except ValueError:
        # Unregistered births/incomplete transitions and malformed receipts
        # retain the original path and its validation/error timing.
        return None
    return hidden
