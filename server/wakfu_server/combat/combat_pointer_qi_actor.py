"""Private QI pointer bridge over actual Actor/Fight; never publishes legacy slots.

The initial unique population must pass the existing production validator. After
native alias operations, pointer topology is kept independently rather than
forcing it through the legacy unique-identity serialized-slot schema.
"""
from copy import deepcopy
from dataclasses import dataclass
from .combat_pointer_qi_model import PointerQI
from .combat_trove_byte_set import NativeTroveByteSet
from .combat_qi_fight import current_registry
from .combat_carrying import carrying_relations, _destination, _position


class ActorQK:
    def __init__(self, actor):
        self.actor = actor

    identity = property(lambda self: self.actor.id)
    x = property(lambda self: self.actor.position[0])
    y = property(lambda self: self.actor.position[1])
    radius = property(lambda self: self.actor.physical_radius)
    byte = property(
        lambda self: self.actor.native_obstacle_id,
        lambda self, value: setattr(self.actor, "native_obstacle_id", value),
    )
    # Qualified ordinary eGj implements QK.bcO true. Areas are not inferred.
    eligible = True
    kind = "actor"


class AreaQK:
    """Actual registered Qq canonical row, qualified by current_registry first."""

    kind = "effect_area"
    eligible = True
    radius = 0

    def __init__(self, row):
        self.row = row

    identity = property(lambda self: self.row["uid"])
    x = property(lambda self: self.row["cell"][0])
    y = property(lambda self: self.row["cell"][1])
    byte = property(
        lambda self: self.row["native_obstacle_id"],
        lambda self, value: self.row.__setitem__("native_obstacle_id", value),
    )


class ActualActorQI(PointerQI):
    def __init__(self, fight):
        registry = current_registry(fight)
        terrain = registry.terrain
        super().__init__(terrain.width, terrain.height)
        self.origin = terrain.x, terrain.y
        self.fight = fight
        self.objects = {
            identity: ActorQK(actor) for identity, actor in fight.actors.items()
        }
        self.area_objects = {}
        self.pending_constructor_actors = {}
        # Installed eGj.bcP returns true independently of current QI membership.
        # Keep this QK property for canonical registered actors without a slot.
        self.movement_blocking = {id(obj): True for obj in self.objects.values()}
        topology = registry.serialized_byte_topology()
        if topology is None:
            raise ValueError("Missing actual native Trove topology")
        for byte, row in enumerate(registry.slots):
            if row is None:
                continue
            identity = row["identity"][1]
            if row["identity"][0] == "actor":
                obj = self.objects[identity]
            else:
                if identity in fight.actors:
                    raise ValueError("Native area/fighter identity collision")
                area = fight.native_effect_areas[identity]
                obj = self.area_objects.setdefault(identity, AreaQK(area))
            if obj.kind == "actor" and row["movement_blocking"] is not True:
                raise ValueError("Ordinary eGj QK.bcP differs from native true")
            self.movement_blocking[id(obj)] = row["movement_blocking"]
            self.slots[byte] = obj
            if row["indexed"]:
                self.anchors[byte] = tuple(row["position"])
        for key, state in topology.items():
            cell = tuple(map(int, key.split(",")))
            self.cells[cell] = NativeTroveByteSet(deepcopy(state))
            if frozenset(self.cells[cell].order()) != frozenset(
                registry.ordered_U(*cell)
            ):
                raise ValueError("Actual topology mismatch")

    def inside(self, x, y):
        return (
            self.origin[0] <= x < self.origin[0] + self.width
            and self.origin[1] <= y < self.origin[1] + self.height
        )

    def move_actor(self, actor, destination):
        obj = self.objects.get(actor.id)
        if obj is None or obj.actor is not actor:
            raise ValueError("Missing actual retained QK pointer")
        destination = _destination(destination)
        relation = carrying_relations(self.fight, actor)
        # eGj.a(int,int,short): carried actors and absent current slots skip QI.a.
        if not relation["is_carried"] and 0 <= obj.byte < 127:
            self.move(obj, *destination[:2])
        _position(actor, destination)


@dataclass(eq=False)
class RetainedContext:
    qi: ActualActorQI | None


@dataclass(eq=False)
class ActualRetained937:
    uid: int
    target: ActorQK | None
    context: RetainedContext | None
    executed: bool = False

    def valid(self):
        return (
            isinstance(self.target, (ActorQK, AreaQK))
            and isinstance(self.context, RetainedContext)
            and isinstance(self.context.qi, ActualActorQI)
        )

    def apply(self):
        if not self.valid():
            return False
        self.context.qi.remove(self.target)
        self.executed = True
        return True

    def remove_runner(self):
        # Retained context, not actor membership/current actor context, is decisive.
        if self.valid() and self.executed:
            self.context.qi.register(self.target)


def clear_retained_manager(runners, events):
    """Qf.clear snapshot→Qe.aW(false)→bbR→disposal→clear, in supplied order.

    Native HashSet UID snapshot order is deliberately an input, not guessed from
    Python dict insertion. Full multi-runner native HashSet ordering is separate.
    """
    for runner in tuple(runners):
        events.append(("bbR", runner.uid))
        runner.remove_runner()
        events.append(("dispose", runner.uid))
    runners.clear()
