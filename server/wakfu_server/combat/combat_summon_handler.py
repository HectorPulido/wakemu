"""Immediate eZl307 creation on the transaction-owned preview.

Actor/controller registration is separate from effect retention. eZl.bbF does
not unsummon; retained/subscribed creation stays guarded until its lifecycle
is represented by the central effect manager.
"""
from dataclasses import replace
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_runner_callbacks import notify_runner_value

from .combat_summon import (
    summon_specification,
    fresh_summon_insertion,
    RegisteredSummonAuthority,
)
from .combat_summon_creation import NativeSummonBuilder
from .combat_summon_property_descriptor import descriptor_property_keys
from .combat_summon_codec import summon_application, summon_payload
from .combat_stat_handler import StatExecutionContext
from .combat_actor_snapshot import native_actor_catalog


def _unused_rng():
    raise ValueError("Native Qe summon runner must not request rounding")


class NativeSummonHandler:
    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        actor_authority,
        container_level,
        container,
        rng=None
    ):
        if not isinstance(actor_authority, RegisteredSummonAuthority):
            raise ValueError("Summoning requires the registered-roster authority")
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.authority, self.container_level = (
            context,
            actor_authority,
            container_level,
        )
        self.container = container
        self.builder = NativeSummonBuilder(actor_authority)
        self.rng = rng if rng is not None else _unused_rng
        self.event_lifecycle = None
        self.prepared_runners = {}
        self.retained_application = None
        self.initialize_registered_gameplay = None

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is None:
            return
        masks = effect.get("target_masks")
        if masks is None or len(masks) != 7:
            raise ValueError("Missing native eZl produced event masks")
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=runner.uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, 2130, *(masks[6] or ())})),
            _nullable_target=True,
        )

    def _calculate(self, effect, values, invocation, runner):
        # eZl.C reserves the creature identity before constructing its descriptor.
        actor_uid = self.allocate_uid()
        while actor_uid in self.fight.actors:
            actor_uid = self.allocate_uid()
        caster = self.fight.actors.get(invocation.caster_id)
        if caster is None or invocation.target_id is not None:
            raise ValueError("Native eZl requires a caster-owned cell application")
        self.authority(self.fight, caster)
        direction = getattr(caster, "direction", None)
        if type(direction) is not int or not 0 <= direction < 8:
            raise ValueError("Missing native summoner orientation")
        parameters = values["parameters"]
        if not parameters:
            raise ValueError("Missing native summoned breed")
        reference = ((parameters[0] + 32768) % 65536) - 32768
        profile = native_actor_catalog()["npc_profiles"].get(str(reference))
        if profile is None:
            raise ValueError("Missing native summoned breed characteristics")
        present, _ = self.container_level(invocation)
        from wakfu_server.monsters import reference as native_reference

        spec = summon_specification(
            effect,
            values,
            evaluation_level=invocation.level,
            container_present=present,
            caster_level=caster.effective_level,
            caster_team=caster.team,
            caster_direction=direction,
            native_minimum_level=native_reference(reference)["min_level"],
        )
        runner.set_calculated(
            apply_context_value(
                parameters[0],
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        return runner, spec, actor_uid

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        if effect["effect_class"] != 307 or invocation.native_running_uid is not None:
            raise ValueError("Missing fresh native eZl preparation")
        runner = NativeRunnerAmount(self.allocate_uid(), 307, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        self.prepared_runners[runner.uid] = self._calculate(
            effect, values, invocation, runner
        )
        return invocation

    def cancel_prepared(self, invocation):
        # The dispatcher also closes preparation when criteria/probability
        # reject application before __call__. Reserved identities stay spent.
        self.prepared_runners.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        caster = self.fight.actors.get(invocation.caster_id)
        if (
            effect["effect_class"] != 307
            or caster is None
            or self.fight.phase != "active"
            or invocation.target_id is not None
        ):
            raise ValueError("Native eZl requires a caster-owned cell application")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native summon execution/timing authority")
        prepared = self.prepared_runners.pop(invocation.native_running_uid, None)
        if not ctx.executable:
            return False
        if (ctx.retained and not callable(self.retained_application)) or (
            invocation.native_running_uid is not None and prepared is None
        ):
            raise ValueError("Native retained/subscribed summon lifecycle is unaudited")
        if ctx.retained:
            masks = effect.get("target_masks")
            if (
                not isinstance(masks, (list, tuple))
                or len(masks) != 7
                or any(masks[index] for index in (0, 1, 3, 4, 5))
            ):
                raise ValueError("Native subscribed summon lifecycle is unaudited")
        if prepared is None:
            if self.event_lifecycle is not None:
                raise ValueError("Missing prepared fresh native eZl lifecycle")
            runner = NativeRunnerAmount(self.allocate_uid(), 307, rng=self.rng)
            prepared = self._calculate(effect, values, invocation, runner)
        runner, spec, actor_uid = prepared
        effect_uid = runner.uid
        reference = spec.reference
        self._phase(effect, invocation, runner, 2)
        # Qe.bbJ rechecks execution after synchronous L2 listeners.
        after = self.context(effect, invocation)
        if (
            not isinstance(after, StatExecutionContext)
            or after.source_guards_verified is not True
        ):
            raise ValueError("Missing native summon post-event execution authority")
        if not after.executable:
            return False
        creation_packet_index = len(self.packets)
        actor, registration = self.builder(
            self.fight, spec, caster.id, actor_uid, invocation.cell
        )
        actor.direction = spec.direction
        if 114 in registration.fight_properties:
            order, index = list(self.fight.order), self.fight.turn_index
        else:
            order, index = fresh_summon_insertion(
                self.fight, spec, caster_id=caster.id, actor_id=actor_uid
            )
        owner, owner_id = self.container(invocation)
        # eZl.C constructs one eHN map entry per distinct descriptor property.
        # Reuse the exact builder increments, never the raw aMb.csb array.
        properties = descriptor_property_keys(registration.fight_properties)
        payload_arguments = dict(
            uid=effect_uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            caster_id=caster.id,
            cell=invocation.cell,
            specification=spec,
            running_value=runner.value,
            actor_id=actor_uid,
            obstacle_index=actor.native_obstacle_id,
            properties=properties,
            timing_payload=ctx.timing_payload,
            container_type=owner["container_type"],
            container_id=owner_id,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        packet = summon_application(self.fight.id, self.action_id, **payload_arguments)
        self.authority.register(
            self.fight, actor, registration, new_order=order, new_turn_index=index
        )
        from .combat_summon_visual_copy import install_summon_visual_copy

        from .combat_ai_control import set_native_ai_control

        # eZl.c calls lx(true) after the common factory and before reference3251
        # PJ. Later ordered parent effects may change that current flag again.
        install_summon_visual_copy(
            self.fight,
            actor,
            caster,
            self.authority,
            equipment_apply=getattr(self, "initialize_equipment", None),
            after_common_factory=lambda: set_native_ai_control(actor, True),
        )
        # The descriptor packet introduces this PV on the client. Ready captures
        # existing actors before innates, so newly created actors must retain
        # their actual creation delivery instead of receiving an empty baseline.
        deliveries = getattr(self.fight, "native_summon_creation_deliveries", None)
        if deliveries is None:
            deliveries = self.fight.native_summon_creation_deliveries = {}
        if actor_uid in deliveries:
            raise ValueError("Duplicate native summon creation delivery")
        deliveries[actor_uid] = {"opcode": packet[0], "payload_hex": packet[1].hex()}
        # Introduce the actual entity before constructor state/equipment
        # deliveries refer to its manager on the client.
        self.packets.insert(creation_packet_index, packet)
        if ctx.retained:
            self.retained_application(
                effect,
                invocation,
                uid=effect_uid,
                actor_id=actor_uid,
                payload=summon_payload(**payload_arguments),
                context=ctx,
            )
        runner.finish_application()
        self._phase(effect, invocation, runner, 3)
        self._phase(effect, invocation, runner, 4)
        notify_runner_value(invocation, runner.value)
        if self.initialize_registered_gameplay is not None:
            self.initialize_registered_gameplay(
                self.fight, actor, registration, effect, invocation
            )
        return True
