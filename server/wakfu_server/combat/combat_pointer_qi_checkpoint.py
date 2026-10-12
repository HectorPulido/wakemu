"""Private plain dictionary checkpoint with canonical pointer owner for deepcopy.

Like existing native linked-map subclasses, plain serialization visits only the
mapping. The live owner is not reconstructed from persisted arbitrary JSON.
"""
from copy import deepcopy
from .combat_pointer_qi_actor import ActualActorQI
from .combat_pointer_qi_plain import encode, decode_bound


class NativePointerCheckpoint(dict):
    def __init__(self, qi):
        if not isinstance(qi, ActualActorQI):
            raise ValueError("Actual qualified native QI owner required")
        self._qi = qi
        self._lineage = object()
        dict.__init__(self, encode(qi))

    def validate(self, fight):
        if self._qi.fight is not fight:
            raise ValueError("Native pointer checkpoint belongs to another fight")
        for identity, obj in self._qi.objects.items():
            registered = fight.actors.get(identity)
            if registered is not obj.actor and not (
                registered is None
                and self._qi.pending_constructor_actors.get(identity) is obj.actor
            ):
                raise ValueError("Canonical native QK actor object was replaced")
        for identity, obj in self._qi.area_objects.items():
            active = getattr(fight, "native_effect_areas", {}).get(identity)
            retired = getattr(fight, "native_retired_area_managers", {}).get(identity)
            # QI aliases retain the original actual Qq pointer after Qs removes
            # it from global area collections. Canonical presence is not global
            # registration; reject replacements, not legitimate unregistration.
            if (
                active is not None
                and active is not obj.row
                or retired is not None
                and retired is not obj.row
            ):
                raise ValueError("Canonical native QK area object was replaced")
        decode_bound(self._qi, self)
        return self._qi

    def publish(self):
        payload = encode(self._qi)
        self.clear()
        self.update(payload)

    def __deepcopy__(self, memo):
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        clone._lineage = self._lineage
        dict.__init__(clone, deepcopy(dict(self), memo))
        # The same deepcopy memo binds QK.actor to the copied fight's actors.
        clone._qi = deepcopy(self._qi, memo)
        # Python id keys are process-local pointer indexes, not native UIDs.
        # Rebind from the same memo that copied each exact canonical object.
        clone._qi.movement_blocking = {
            id(memo[id(obj)]): self._qi.movement_blocking[id(obj)]
            for obj in (*self._qi.objects.values(), *self._qi.area_objects.values())
        }
        # Fight may still be under reconstruction; the receiving provider validates
        # after deepcopy completes, before allowing any consumer operation.
        return clone

    def bind_committed_fight(self, fight):
        # Commit may move the candidate's actual objects into the live Fight.
        # Identity equality is required; never manufacture owners from a roster.
        if any(
            fight.actors.get(identity) is not obj.actor
            for identity, obj in self._qi.objects.items()
        ):
            raise ValueError("Commit does not preserve actual canonical actor objects")
        old = self._qi.fight
        self._qi.fight = fight
        try:
            self.validate(fight)
        except BaseException:
            self._qi.fight = old
            raise
        return self._qi

    def commit_topology_from(self, candidate, fight):
        """Publish validated forecast QI topology while retaining live QK objects."""
        self.validate(fight)
        if (
            not isinstance(candidate, type(self))
            or candidate._lineage is not self._lineage
        ):
            raise ValueError("Topology candidate lacks actual forecast lineage")
        candidate.validate(candidate._qi.fight)
        if set(self._qi.objects) != set(candidate._qi.objects) or set(
            self._qi.area_objects
        ) != set(candidate._qi.area_objects):
            raise ValueError("Topology-only commit cannot create canonical QK objects")
        memo = {id(candidate._qi.fight): fight}
        for current, proposed in (
            (self._qi.objects, candidate._qi.objects),
            (self._qi.area_objects, candidate._qi.area_objects),
        ):
            for identity, obj in current.items():
                other = proposed[identity]
                memo[id(other)] = obj
                source = other.actor if other.kind == "actor" else other.row
                target = obj.actor if obj.kind == "actor" else obj.row
                memo[id(source)] = target
        clone = deepcopy(candidate, memo)
        for identity, obj in self._qi.objects.items():
            obj.actor.native_obstacle_id = candidate._qi.objects[
                identity
            ].actor.native_obstacle_id
        self._qi.__dict__.update(clone._qi.__dict__)
        self.publish()
        self.validate(fight)
