"""Publish an owned-area lifecycle boundary only after all callbacks succeed."""
from copy import deepcopy
from functools import wraps


def adopt_fight(destination, candidate):
    from .combat_characteristic_link import characteristic_adoption_bindings

    bindings = characteristic_adoption_bindings(candidate)
    from .combat_pointer_qi_commit import prepare_pointer_commit

    pointer_binding = prepare_pointer_commit(candidate)
    if pointer_binding is not None:
        pointer_binding.stage(destination)
    # Main and serializers retain this Fight reference. Preserve existing actor
    # references too; actual new summon actors are adopted without fabrication.
    actors = {}
    for uid, actor in candidate.actors.items():
        existing = destination.actors.get(uid)
        if existing is not None:
            existing.__dict__.clear()
            existing.__dict__.update(actor.__dict__)
            actor = existing
        actors[uid] = actor
    destination.__dict__.clear()
    destination.__dict__.update(candidate.__dict__)
    destination.actors = actors
    if pointer_binding is not None:
        pointer_binding.publish()
    for stats in bindings:
        stats._fight = destination


def adopt_runtime(destination, candidate):
    fight = destination.fight
    adopt_fight(fight, candidate.fight)
    destination.__dict__.clear()
    destination.__dict__.update(candidate.__dict__)
    destination.fight = fight
    destination.__dict__.pop("_area_atomic_depth", None)


def atomic_area_turn(operation):
    @wraps(operation)
    def apply(runtime, *args, **kwargs):
        if (
            runtime.turn_start_provider is None and runtime.turn_end_provider is None
        ) or getattr(runtime, "_area_atomic_depth", False):
            return operation(runtime, *args, **kwargs)
        candidate = deepcopy(runtime)
        candidate._area_atomic_depth = True
        result = operation(candidate, *args, **kwargs)
        adopt_runtime(runtime, candidate)
        return result

    return apply
