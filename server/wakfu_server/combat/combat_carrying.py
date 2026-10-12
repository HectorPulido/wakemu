"""Owned eGj pGV/pGW relations and their reserved QK indexing lifecycle."""
from dataclasses import dataclass, replace
from contextlib import contextmanager
from contextvars import ContextVar

_population = ContextVar("native_carry_population", default=None)


@contextmanager
def carry_population_scope(preview):
    """Composite summon authority retains the real reciprocal actor population."""
    token = _population.set(preview)
    try:
        yield
    finally:
        _population.reset(token)


@dataclass(frozen=True)
class NativeCarryPair:
    carrier_id: int
    carried_id: int
    position: tuple[int, int, int]
    carried_direction: int
    carrier_direction: int
    source_uid: int
    source_reference: int | None = None


def _pairs(fight):
    pairs = getattr(fight, "native_carry_pairs", {})
    if not isinstance(pairs, dict) or any(
        type(key) is not int
        or not isinstance(pair, NativeCarryPair)
        or key != pair.carrier_id
        for key, pair in pairs.items()
    ):
        raise ValueError("Missing actual native carry relation authority")
    return pairs


def carrying_relations(fight, actor):
    """Fresh null relations or the exact reciprocal producer; no attribute guesses."""
    pairs = _pairs(fight)
    carrier_id = getattr(actor, "native_carrier_id", None)
    carried_id = getattr(actor, "native_carried_actor_id", None)
    carrier_pair = pairs.get(actor.id)
    carried_pairs = [pair for pair in pairs.values() if pair.carried_id == actor.id]
    if len(carried_pairs) > 1 or (carrier_pair is not None and carried_pairs):
        raise ValueError("Native carrying relations cannot be nested")
    pair = carrier_pair or (carried_pairs[0] if carried_pairs else None)
    if pair is None:
        if carrier_id is not None or carried_id is not None:
            raise ValueError("Unregistered native carrying relationships")
        return dict(is_carried=False, is_carrying=False)
    population = fight.actors
    scoped = _population.get()
    if scoped is not None and scoped is not fight:
        if (
            scoped.id != fight.id
            or _pairs(scoped) is not pairs
            or any(
                scoped.actors.get(key) is not value
                for key, value in fight.actors.items()
            )
        ):
            raise ValueError("Mismatched actual native carrying population scope")
        population = scoped.actors
    carrier = population.get(pair.carrier_id)
    carried = population.get(pair.carried_id)
    if (
        carrier is None
        or carried is None
        or carrier is carried
        or getattr(carrier, "native_carried_actor_id", None) != carried.id
        or getattr(carrier, "native_carrier_id", None) is not None
        or getattr(carried, "native_carrier_id", None) != carrier.id
        or getattr(carried, "native_carried_actor_id", None) is not None
        or tuple(carrier.position) != pair.position
        or tuple(carried.position) != pair.position
        or carried.direction != pair.carried_direction
        or carrier.direction != pair.carrier_direction
    ):
        raise ValueError("Stale native reciprocal carrying authority")
    return dict(is_carried=actor is carried, is_carrying=actor is carrier)


def _publish_registry(fight, registry):
    if hasattr(fight, "native_pointer_checkpoint"):
        from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
        from .combat_pointer_qi_registry import PointerRegistryCompatibility

        checkpoint = fight.native_pointer_checkpoint
        if (
            not isinstance(checkpoint, NativePointerCheckpoint)
            or not isinstance(registry, PointerRegistryCompatibility)
            or checkpoint._qi is not registry.qi
            or registry.qi.fight is not fight
        ):
            raise ValueError("Mismatched canonical native QI publisher")
        checkpoint.publish()
        checkpoint.validate(fight)
        return
    fight.native_qi_slots = registry.serialized_slots()
    fight.native_qi_touched_cells = registry.serialized_cells()
    fight.native_qi_byte_topology = registry.serialized_byte_topology()


def _destination(destination):
    if (
        not isinstance(destination, (tuple, list))
        or len(destination) != 3
        or any(type(value) is not int for value in destination)
        or any(not -(1 << 31) <= value < (1 << 31) for value in destination[:2])
        or not -512 <= destination[2] <= 511
    ):
        raise ValueError("Missing actual native eGj coordinate update")
    return tuple(destination)


def _position(actor, destination):
    actor.position = tuple(destination)
    if getattr(actor, "native_physical_position", None) is not None:
        actor.native_physical_position = tuple(destination)


def carry_registered(fight, carrier, carried, *, source_uid, source_reference=None):
    """Successful base eGj.a(eHH), after eWB's typed property guards."""
    if source_reference is not None and (
        type(source_reference) is not int or source_reference <= 0
    ):
        raise ValueError("Invalid actual native carry definition reference")
    from .combat_qi_fight import current_registry

    if (
        fight.actors.get(carrier.id) is not carrier
        or fight.actors.get(carried.id) is not carried
        or type(source_uid) is not int
        or not 0 < source_uid < 1 << 63
    ):
        raise ValueError("Actual registered carry recipients and source required")
    # Original eGj.b(eHH) checks object identity and returns false before
    # reading the target's reciprocal relation or mutating QI.
    if carrier is carried:
        return False
    for actor in (carrier, carried):
        if any(carrying_relations(fight, actor).values()):
            return False
    if any(
        type(actor.direction) is not int or actor.direction not in range(-1, 10)
        for actor in (carrier, carried)
    ):
        raise ValueError("Missing actual native carry direction")
    height = getattr(carrier, "native_los_height", None)
    if type(height) is not int or not -128 <= height <= 127:
        raise ValueError("Missing actual carrier eGH.bcK height")
    half = int(height / 2)  # Java integer division truncates toward zero.
    if not (
        carried.position[2] <= carrier.position[2] + half
        or carried.position[2] >= carrier.position[2] - half
    ):
        return False
    registry = current_registry(fight)
    registry.toggle(carried.native_obstacle_id, ("actor", carried.id), False)
    registry.move_carried(
        carried.native_obstacle_id, ("actor", carried.id), carrier.position[:2]
    )
    pair = NativeCarryPair(
        carrier.id,
        carried.id,
        _destination(carrier.position),
        carried.direction,
        carrier.direction,
        source_uid,
        source_reference,
    )
    pairs = dict(_pairs(fight))
    pairs[carrier.id] = pair
    carrier.native_carried_actor_id = carried.id
    carried.native_carrier_id = carrier.id
    _position(carried, carrier.position)
    fight.native_carry_pairs = pairs
    _publish_registry(fight, registry)
    return True


def move_carrying_registered(fight, actor, destination, registry):
    """Complete base eGj.a(IIS), including recursive carried coordinate update."""
    destination = _destination(destination)
    relation = carrying_relations(fight, actor)
    if relation["is_carried"]:
        raise ValueError(
            "Independent carried movement requires its native carrier producer"
        )
    registry.move(actor.native_obstacle_id, ("actor", actor.id), destination[:2])
    if relation["is_carrying"]:
        pair = _pairs(fight)[actor.id]
        carried = fight.actors[pair.carried_id]
        registry.move_carried(
            carried.native_obstacle_id, ("actor", carried.id), destination[:2]
        )
        pairs = dict(_pairs(fight))
        pairs[actor.id] = replace(pair, position=tuple(destination))
        _position(carried, destination)
        fight.native_carry_pairs = pairs
    _position(actor, destination)
    _publish_registry(fight, registry)


def release_registered(fight, carrier, destination, *, direction):
    """Base eGj.R: move while carried, dda indexes, then clear carrier pGV."""
    from .combat_qi_fight import current_registry

    destination = _destination(destination)
    if type(direction) is not int or direction not in range(-1, 10):
        raise ValueError("Actual native release direction required")
    relation = carrying_relations(fight, carrier)
    if not relation["is_carrying"]:
        return False
    registry = current_registry(fight)
    pair = _pairs(fight)[carrier.id]
    carried = fight.actors[pair.carried_id]
    registry.move_carried(
        carried.native_obstacle_id, ("actor", carried.id), destination[:2]
    )
    registry.toggle(carried.native_obstacle_id, ("actor", carried.id), True)
    pairs = dict(_pairs(fight))
    del pairs[carrier.id]
    _position(carried, destination)
    carried.direction = direction
    carried.native_carrier_id = None
    carrier.native_carried_actor_id = None
    fight.native_carry_pairs = pairs
    _publish_registry(fight, registry)
    return True


def set_registered_direction(fight, actor, direction):
    """eGj.a(aAS): propagate direction delta through actual pGV."""
    if type(direction) is not int or direction not in range(-1, 10):
        raise ValueError("Actual native direction required")
    relation = carrying_relations(fight, actor)
    pairs = dict(_pairs(fight))
    if relation["is_carrying"]:
        pair = pairs[actor.id]
        carried = fight.actors[pair.carried_id]
        carried_direction = (carried.direction + direction - actor.direction) % 8
        carried.direction = carried_direction
        pairs[actor.id] = replace(
            pair, carrier_direction=direction, carried_direction=carried_direction
        )
    elif relation["is_carried"]:
        pair = pairs[actor.native_carrier_id]
        pairs[pair.carrier_id] = replace(pair, carried_direction=direction)
    actor.direction = direction
    fight.native_carry_pairs = pairs
