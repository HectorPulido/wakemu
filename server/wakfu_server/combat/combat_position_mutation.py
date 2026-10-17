"""Shared position mutation boundary for native combat movement.

This boundary owns coordinates, reciprocal carried coordinates and native QI
publication. Area callbacks, effect phases and packet delivery remain callers'
responsibility. Historical comparisons run against an isolated source archive.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class _RegisteredPositionUpdate:
    fight: object
    actor: object
    destination: tuple
    registry: object

    def apply(self):
        from .combat_carrying import carrying_relations, _pairs, _position
        from .combat_carrying import _publish_registry

        fight, actor = self.fight, self.actor
        relation = carrying_relations(fight, actor)
        if relation["is_carried"]:
            raise ValueError(
                "Independent carried movement requires its native carrier producer"
            )
        self.registry.move(
            actor.native_obstacle_id, ("actor", actor.id), self.destination[:2]
        )
        if relation["is_carrying"]:
            pair = _pairs(fight)[actor.id]
            carried = fight.actors[pair.carried_id]
            self.registry.move_carried(
                carried.native_obstacle_id,
                ("actor", carried.id),
                self.destination[:2],
            )
            pairs = dict(_pairs(fight))
            pairs[actor.id] = replace(pair, position=self.destination)
            _position(carried, self.destination)
            fight.native_carry_pairs = pairs
        _position(actor, self.destination)
        # Pointer checkpoints must see the actual relocated actor objects here;
        # serialized QI uses this same point to publish its ordered topology.
        _publish_registry(fight, self.registry)


def move_actor_position(fight, actor, destination):
    """Apply one coordinate update without invoking area or delivery callbacks."""
    from .combat_carrying import _destination

    if getattr(fight, "native_qi_slots", None) is not None:
        from .combat_qi_fight import current_registry

        # Preserve the historical authority-check order, including stale QI
        # failures before destination validation and all OFF_PLAY checks.
        registry = current_registry(fight)
        registered_destination = _destination(tuple(destination))
        _RegisteredPositionUpdate(
            fight, actor, registered_destination, registry
        ).apply()
    # Compatibility tail: repeated conversions preserve the original alias
    # topology for list destinations and consumption of one-shot iterables.
    # No-QI fixtures retain their original permissive coordinate behavior.
    actor.position = tuple(destination)
    if getattr(actor, "native_physical_position", None) is not None:
        actor.native_physical_position = tuple(destination)
