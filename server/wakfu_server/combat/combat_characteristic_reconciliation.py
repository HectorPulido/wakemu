"""Queue authoritative changed characteristics after relative native effects."""
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


def characteristic_signatures(fight):
    """Copy values, never retain mutable preview dictionaries or PA bindings."""
    result = {}
    for identity, actor in fight.actors.items():
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
    changed = [
        identity
        for identity, signature in characteristic_signatures(fight).items()
        if identity not in excluded and before.get(identity) != signature
    ]
    if not changed:
        return []
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

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
