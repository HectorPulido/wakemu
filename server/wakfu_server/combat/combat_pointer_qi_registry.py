"""Private consumer interface preserving explicit QL history and canonical QKs."""
from copy import deepcopy
from .combat_qi_snapshot import NativeQISnapshot


class PointerRegistryCompatibility:
    def __init__(self, qi):
        self.qi = qi
        self.terrain = NativeQISnapshot(qi.fight.native_qi_snapshot)

    @property
    def slots(self):
        return [
            None
            if obj is None
            else dict(
                identity=[obj.kind, obj.identity],
                position=[obj.x, obj.y],
                radius=obj.radius,
                indexed=any(byte in value.order() for value in self.qi.cells.values()),
                movement_blocking=self.qi.movement_blocking[id(obj)],
            )
            for byte, obj in enumerate(self.qi.slots)
        ]

    def snapshot(self):
        result = NativeQISnapshot(self.qi.fight.native_qi_snapshot)
        result.occupancy = {
            cell: frozenset(value.order()) for cell, value in self.qi.cells.items()
        }
        return result

    def ordered_U(self, x, y):
        return self.qi.ordered_members(x, y) if self.terrain.aK(x, y) else ()

    def actual_slot_object(self, byte):
        return self.qi.slot_object(byte)

    def _canonical(self, slot, identity):
        if type(slot) is not int or not -1 <= slot <= 126:
            raise ValueError("Invalid native canonical QK byte")
        obj = self.qi.slot_object(slot)
        if slot == -1 and isinstance(identity, (list, tuple)) and len(identity) == 2:
            kind, uid = identity
            objects = (
                self.qi.objects
                if kind == "actor"
                else self.qi.area_objects
                if kind == "effect_area"
                else {}
            )
            obj = objects.get(uid)
            if obj is not None and obj.byte != -1:
                raise ValueError("Native absent byte differs from actual canonical QK")
        if obj is None or tuple(identity) != (obj.kind, obj.identity):
            raise ValueError("Native canonical QK identity mismatch")
        return obj

    def _owned(self, slot, identity):
        self._canonical(slot, identity)
        return self.slots[slot]

    def native_V(self, x, y):
        order = self.ordered_U(x, y)
        return None if not order else self.qi.slot_object(order[0])

    def native_g(self, x, y):
        snapshot = self.snapshot()
        index = snapshot._int32(
            snapshot._int32(snapshot._int32(y - snapshot.y) * snapshot.width)
            + snapshot._int32(x - snapshot.x)
        )
        if not 0 <= index < len(snapshot.masks) or snapshot.masks[index] & 768:
            return True
        override = getattr(self.qi.fight, "native_qi_movement_override", None)
        ignored = getattr(self.qi.fight, "native_qi_ignored_slots", None)
        if (
            type(override) is not bool
            or not isinstance(ignored, (list, tuple))
            or any(type(byte) is not int or not -128 <= byte <= 127 for byte in ignored)
        ):
            raise ValueError("Missing actual native movement override/exclusions")
        if override:
            return False
        rows = self.slots
        return any(
            byte not in ignored
            and rows[byte] is not None
            and rows[byte]["movement_blocking"]
            for byte in self.ordered_U(x, y)
        )

    def remove(self, slot, identity):
        self.qi.remove(self._canonical(slot, identity))

    def move(self, slot, identity, position):
        obj = self._canonical(slot, identity)
        self.qi.move(obj, *position)

    def move_carried(self, slot, identity, position):
        obj = self._canonical(slot, identity)
        # eGj.a(IIS) changes canonical pGF while buX bypasses QI.a entirely.
        obj.actor.position = (*position, obj.actor.position[2])

    def toggle(self, slot, identity, enabled):
        if type(enabled) is not bool:
            raise ValueError("Missing actual QK indexing flag")
        obj = self._canonical(slot, identity)
        if not self.qi.inside(obj.x, obj.y):
            return
        if enabled:
            self.qi._index(obj, obj.x, obj.y)
        else:
            self.qi._unindex(obj)

    def serialized_slots(self):
        raise ValueError(
            "Pointer aliases require versioned canonical checkpoint publication"
        )

    def serialized_cells(self):
        return [list(cell) for cell in sorted(self.qi.cells)]

    def serialized_byte_topology(self):
        return {
            f"{x},{y}": deepcopy(value.state) for (x, y), value in self.qi.cells.items()
        }

    def validate_exclusion_target(self, target):
        """QI.b consumes actual target.bcN byte, including legitimate -1."""
        obj = self.qi.objects.get(getattr(target, "id", None))
        if (
            obj is None
            or obj.actor is not target
            or self.qi.fight.actors.get(target.id) is not target
        ):
            raise ValueError("Missing actual canonical Sn target QK")
        byte = obj.byte
        if type(byte) is not int or not -1 <= byte <= 126:
            raise ValueError("Invalid actual Sn target QK byte")
        if byte >= 0 and self.qi.slot_object(byte) is not obj:
            raise ValueError("Missing actual Sn target current QK slot")
        return byte

    def register_constructor_actor(self, actor):
        """QI.f over actual fresh eGj, before native fdt roster insertion.

        Only source-qualified actor constructor callers use this API; descriptor
        dictionaries cannot manufacture canonical object pointers.
        """
        from .combat_pointer_qi_actor import ActorQK

        identity = getattr(actor, "id", None)
        if (
            type(identity) is not int
            or identity == 0
            or identity in self.qi.objects
            or identity in self.qi.area_objects
        ):
            raise ValueError("Duplicate or missing fresh canonical actor identity")
        registered = self.qi.fight.actors.get(identity)
        if registered is not None and registered is not actor:
            raise ValueError("Fresh actor conflicts with actual roster object")
        position = getattr(actor, "native_physical_position", None)
        if (
            position is None
            or tuple(position) != tuple(actor.position)
            or type(actor.physical_radius) is not int
            or not -128 <= actor.physical_radius <= 127
            or actor.native_obstacle_id != -1
        ):
            raise ValueError("Missing actual fresh eGj QK constructor facts")
        if not any(obj is None for obj in self.qi.slots):
            return -1  # Preserve existing producer's explicit capacity refusal.
        obj = ActorQK(actor)
        self.qi.objects[identity] = obj
        self.qi.pending_constructor_actors[identity] = actor
        self.qi.movement_blocking[id(obj)] = True  # Native eGj.bcP literal true.
        self.qi.register(obj)
        return obj.byte

    def register_constructor_area(self, row, constructor):
        """Receive the actual Qq after the caller validates its native constructor."""
        from .combat_pointer_qi_actor import AreaQK

        identity = row.get("uid")
        if (
            type(identity) is not int
            or identity in self.qi.objects
            or identity in self.qi.area_objects
        ):
            raise ValueError("Duplicate or missing fresh canonical area identity")
        if self.qi.fight.native_effect_areas.get(identity) is not row:
            raise ValueError("Missing actual pending Qs area object")
        if (
            row.get("native_obstacle_id") != -1
            or constructor.get("obstacle") is not True
            or type(constructor.get("movement_blocking")) is not bool
        ):
            raise ValueError("Missing actual pending Qq constructor facts")
        if not any(obj is None for obj in self.qi.slots):
            return -1
        obj = AreaQK(row)
        self.qi.area_objects[identity] = obj
        self.qi.movement_blocking[id(obj)] = constructor["movement_blocking"]
        self.qi.register(obj)
        return obj.byte
