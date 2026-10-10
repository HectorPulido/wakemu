"""Native eWB/eZE application over verified reciprocal carrying geometry."""
from dataclasses import replace
from .combat_carrying import (
    carrying_relations,
    carry_registered,
    release_registered,
    set_registered_direction,
)
from .combat_carry_delivery import native_carry_gate
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount


class NativeCarryHandler:
    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        authority,
        rng,
        delivery,
        selected_height
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.authority, self.rng = authority, rng
        self.delivery, self.selected_height = delivery, selected_height
        self.event_lifecycle, self.area_events = None, None
        self.prepared, self.runners = {}, {}

    @staticmethod
    def require_execution_context(invocation):
        from .combat_effect_removal import _identity_fields

        if invocation.native_context_hex is None:
            raise ValueError("Missing actual native carrying execution-context origin")
        fields = _identity_fields(
            bytes.fromhex(invocation.native_context_hex),
            integer_fields=(1, 2, 4, 5, 6, 7, 8, 9),
        )
        if (
            set(fields) != {1, 2, 4, 5, 6, 7, 8, 9}
            or any(fields[k] not in (0, 1) for k in (1, 2, 5, 7, 8))
            or fields[9] not in (0, 1, 2)
        ):
            raise ValueError("Missing complete actual native carrying eVt context")

    def _context(self, effect, invocation):
        family = effect["effect_class"]
        if (
            self.fight.phase != "active"
            or family not in (333, 334)
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Missing actual carrying runner/caster")
        caster = self.fight.actors[invocation.caster_id]
        if self.authority(self.fight, caster).targeting.get("is_eGj") is not True:
            raise ValueError("Carrying requires actual eHG fighter authority")
        if family == 334:
            target = self.fight.actors.get(invocation.target_id)
            if (
                target is None
                or self.authority(self.fight, target).targeting.get("is_eGj")
                is not True
            ):
                raise ValueError("Carrying requires actual eHH recipient authority")
        areas = getattr(self.fight, "native_effect_areas", None)
        if not isinstance(areas, dict):
            raise ValueError("Missing complete native Qs area population")
        if areas and self.area_events is None:
            raise ValueError("Carrying requires actual Qs movement callback")
        if family == 334:
            # fbX.aE removes unattached faY presentation zones of this target.
            # Their creation/removal authority is not part of this producer.
            if any(row.get("native_area_contract") == "faY" for row in areas.values()):
                raise ValueError("Carrying requires actual faY cleanup authority")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native carrying runner guards")
        if context.retained:
            raise ValueError(
                "Retained carry runner removal requires its actual owner contract"
            )
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native carrying events")
        return tuple(
            sorted(
                {
                    0,
                    *((2224,) if effect["effect_class"] == 334 else ()),
                    *(masks[6] or ()),
                }
            )
        )

    def _phase(self, effect, invocation, uid, channel):
        if self.event_lifecycle is not None:
            runner = self.runners[uid]
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=runner.value,
                channel=channel,
                _event_ids=self._events(effect),
                runner_modifier=runner,
                _nullable_target=effect["effect_class"] == 333,
                _execution_status=-1,
            )

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            self.runners[uid] = NativeRunnerAmount(
                uid, effect["effect_class"], rng=self.rng
            )
            self._phase(effect, invocation, uid, 1)
            # Both C implementations leave inherited bfB untouched. eZE only
            # calculates its private qcl, not a forced-context running amount.
            count = effect.get("parameter_count")
            if type(count) is not int or count < 0:
                raise ValueError("Missing actual carrying parameter count")
            qcl = (
                effect["effect_class"] == 333
                and count > 0
                and parameter_value(effect["parameters"], 0, invocation.level) == 1
            )
            self.prepared[uid] = qcl
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def _carry_gate(self, effect, caster, target):
        if any(
            type(actor.team) is not int or not -128 <= actor.team <= 127
            for actor in (caster, target)
        ):
            raise ValueError("Missing actual native eHg.bcM affiliation byte")
        source = self.authority.properties(self.fight, caster)
        recipient = self.authority.properties(self.fight, target)
        return native_carry_gate(
            target_is_ehh=True,
            caster_is_ehg=True,
            both_are_ehg_affiliations=True,
            target_cannot_be_carried=70 in recipient,
            target_stabilized=11 in recipient,
            bypass_stabilization=36 in effect["native_effect_flags"],
            caster_enemy_stabilized=110 in source,
            target_enemy_stabilized=110 in recipient,
            caster_ally_stabilized=111 in source,
            target_ally_stabilized=111 in recipient,
            same_affiliation=caster.team == target.team,
        )

    def _blocked(self, registry, cell):
        qi = registry.snapshot()
        # QI.g tests W/index range (not aK), terrain768, biP, U and biN.
        index = qi._int32(
            qi._int32(qi._int32(cell[1] - qi.y) * qi.width) + qi._int32(cell[0] - qi.x)
        )
        if not 0 <= index < len(qi.masks) or qi.masks[index] & 768:
            return True
        if not qi.aK(*cell[:2]):
            raise ValueError(
                "Native QI.g aliased out-of-bounds occupancy requires its exact producer"
            )
        override = getattr(self.fight, "native_qi_movement_override", None)
        ignored = getattr(self.fight, "native_qi_ignored_slots", None)
        if type(override) is not bool or not isinstance(ignored, (tuple, list)):
            raise ValueError("Missing actual QI movement flags")
        if any(type(slot) is not int or not 0 <= slot <= 126 for slot in ignored):
            raise ValueError("Missing actual ignored QK byte set")
        if override:
            return False
        return any(
            slot not in ignored
            and registry.slots[slot] is not None
            and registry.slots[slot]["movement_blocking"]
            for slot in (qi.U(*cell[:2]) or ())
        )

    def _landing(self, effect, invocation, caster, carried, qcl):
        from .combat_qi_fight import current_registry
        from .combat_group_cells import ordered_offsets

        registry = current_registry(self.fight)
        destination = invocation.cell
        # Ordinary eGj is a movement-blocking QK. Other eHH subclasses need
        # their own source-proven bcP authority and are rejected above.
        if qcl or not self._blocked(registry, destination):
            return destination
        for dx, dy in ordered_offsets(
            effect,
            origin=destination,
            reference=caster.position,
            direction=caster.direction,
        ):
            x, y = destination[0] + dx, destination[1] + dy
            if not registry.terrain.aK(x, y):
                continue
            z = self.selected_height(self.fight, x, y)
            if type(z) is not int or not -32768 <= z <= 32767:
                raise ValueError("Unknown actual QI.X selected height")
            candidate = (x, y, z)
            if z != -32768 and not self._blocked(registry, candidate):
                return candidate
        return None

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        context = self._context(effect, invocation)
        uid = invocation.native_running_uid
        if uid not in self.prepared:
            raise ValueError("Missing prepared native carrying runner")
        if not context.executable:
            return False
        self._phase(effect, invocation, uid, 2)
        if not self._context(effect, invocation).executable:
            return False
        caster = self.fight.actors[invocation.caster_id]
        qcl = self.prepared[uid]
        if effect["effect_class"] == 334:
            carried = self.fight.actors[invocation.target_id]
            if not self._carry_gate(effect, caster, carried):
                return False
            destination = caster.position
        else:
            if not carrying_relations(self.fight, caster)["is_carrying"]:
                return False
            carried = self.fight.actors[caster.native_carried_actor_id]
            destination = self._landing(effect, invocation, caster, carried, qcl)
            if destination is None:
                return False
        # Prebuild exact native delivery before publishing any geometry.
        packet = self.delivery(
            effect,
            invocation,
            uid=uid,
            value=self.runners[uid].value,
            qcl=qcl,
            timing_payload=context.timing_payload,
        )
        before = carried.position
        if effect["effect_class"] == 334:
            success = carry_registered(
                self.fight,
                caster,
                carried,
                source_uid=uid,
                source_reference=invocation.reference,
            )
        else:
            from .combat_orientation_effect import _toward

            properties = self.authority.properties(self.fight, caster)
            if tuple(caster.position) != tuple(destination) and 51 not in properties:
                direction = _toward(caster.position, destination)
                set_registered_direction(self.fight, caster, direction)
            success = release_registered(
                self.fight, caster, destination, direction=carried.direction
            )
        if not success:
            return False
        self.packets.append(packet)
        if self.area_events is not None:
            self.area_events.movement(
                carried.id, from_cell=before, to_cell=carried.position
            )
        self.runners[uid].finish_application()
        self._phase(effect, invocation, uid, 3)
        self._phase(effect, invocation, uid, 4)
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, self.runners[uid].value)
        return True
