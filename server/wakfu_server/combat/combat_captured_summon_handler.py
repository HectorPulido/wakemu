"""Owned eZr324 preparation and common constructor, never a synthetic NPC book."""
from dataclasses import replace
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from .combat_summon_handler import NativeSummonHandler
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_runner_callbacks import notify_runner_value
from .combat_stat_handler import StatExecutionContext
from .combat_captured_summon import (
    captured_summon_plan,
    NativeCapturedSummonPipeline,
    mark_captured_origin,
)
from .combat_captured_profiles import (
    native_captured_profiles,
    captured_descriptor,
    initialize_captured_descriptor,
)
from .combat_captured_scaling import scale_captured_characteristics
from .combat_captured_summon_codec import (
    CapturedDescriptor,
    captured_summon_application,
)
from .combat_summon import fresh_summon_insertion


class NativeCapturedSummonHandler(NativeSummonHandler):
    """Fresh selected owned slot only; retained execution remains explicitly guarded."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profiles = native_captured_profiles()
        self.builder.ability_profiles = profiles
        self.builder.initial_states = profiles

    def _roster(self, caster):
        authority = self.authority(self.fight, caster)
        if authority.native_is_ehp is not True:
            raise ValueError("Native324 requires actual eHP caster authority")
        record = getattr(self.fight, "native_captured_rosters", {}).get(str(caster.id))
        roster = (
            OwnedCapturedRoster.from_record(record, expected_owner_id=caster.id)
            if record is not None
            else authority.native_captured_roster
        )
        if not isinstance(roster, OwnedCapturedRoster) or roster.owner_id != caster.id:
            raise ValueError("Native324 requires hydrated actual owned roster")
        return roster

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is None:
            return
        masks = effect.get("target_masks")
        if masks is None or len(masks) != 7:
            raise ValueError("Missing native324 produced event masks")
        # eZr inherits Qe.bbx intrinsic0; only eZl307 overrides it to add2130.
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=runner.uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            _nullable_target=True,
        )

    def _calculate(self, effect, values, invocation, runner):
        caster = self.fight.actors.get(invocation.caster_id)
        if caster is None or invocation.target_id is not None:
            raise ValueError("Native324 requires caster-owned cell application")

        def allocate_actor():
            uid = self.allocate_uid()
            while uid in self.fight.actors:
                uid = self.allocate_uid()
            return uid

        plan = captured_summon_plan(
            effect,
            values,
            self._roster(caster),
            caster_id=caster.id,
            caster_level=caster.effective_level,
            caster_direction=caster.direction,
            caster_team=caster.team,
            allocate_uid=allocate_actor,
        )
        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        return runner, plan

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        if effect["effect_class"] != 324 or invocation.native_running_uid is not None:
            raise ValueError("Missing fresh native324 preparation")
        runner = NativeRunnerAmount(self.allocate_uid(), 324, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        self.prepared_runners[runner.uid] = self._calculate(
            effect, values, invocation, runner
        )
        return invocation

    def __call__(self, effect, values, invocation):
        caster = self.fight.actors.get(invocation.caster_id)
        if (
            effect["effect_class"] != 324
            or caster is None
            or self.fight.phase != "active"
            or invocation.target_id is not None
        ):
            raise ValueError("Native324 requires actual caster-owned cell application")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native324 execution authority")
        prepared = self.prepared_runners.pop(invocation.native_running_uid, None)
        if not ctx.executable:
            return False
        if ctx.retained or (
            invocation.native_running_uid is not None and prepared is None
        ):
            raise ValueError("Retained native324 lifecycle is unaudited")
        if prepared is None:
            if self.event_lifecycle is not None:
                raise ValueError("Missing prepared native324 lifecycle")
            runner = NativeRunnerAmount(self.allocate_uid(), 324, rng=self.rng)
            prepared = self._calculate(effect, values, invocation, runner)
        runner, plan = prepared
        self._phase(effect, invocation, runner, 2)
        after = self.context(effect, invocation)
        if (
            not isinstance(after, StatExecutionContext)
            or after.source_guards_verified is not True
        ):
            raise ValueError("Missing native324 post-event authority")
        if not after.executable or not plan.allowed:
            return False
        descriptor = captured_descriptor(
            plan.descriptor_entry,
            owner_id=plan.owner_id,
            level=plan.specification.level,
            actor_id=plan.actor_id,
        )

        def create(preview, spec, actual_descriptor, **kwargs):
            self.builder.descriptor_initializer = lambda fight, actor, specification, parent: initialize_captured_descriptor(
                actor,
                actual_descriptor,
                definitions=self.builder.characteristics["characteristics"],
            )
            actor, registration = self.builder(
                preview,
                spec,
                kwargs["caster_id"],
                kwargs["actor_id"],
                kwargs["cell"],
                creation_properties=(),
            )
            actor.direction = spec.direction
            order, index = fresh_summon_insertion(
                preview, spec, caster_id=caster.id, actor_id=actor.id
            )
            self.authority.register(
                preview, actor, registration, new_order=order, new_turn_index=index
            )
            return actor

        def commit(preview, roster):
            records = dict(getattr(preview, "native_captured_rosters", {}))
            records[str(caster.id)] = roster.to_record()
            preview.native_captured_rosters = records
            updates = dict(getattr(preview, "native_captured_roster_updates", {}))
            updates[str(caster.id)] = roster.to_record()
            preview.native_captured_roster_updates = updates

        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda *args, **kwargs: descriptor,
            create=create,
            scale_characteristics=lambda actor, main, secondary: scale_captured_characteristics(
                self.fight, actor, main, secondary
            ),
            mark_symbiot=lambda actor, value: mark_captured_origin(
                self.fight, actor, plan
            ),
            commit_roster=commit,
        )
        creation_packet_index = len(self.packets)
        actor = pipeline.execute(
            plan, self._roster(caster), preview=self.fight, cell=invocation.cell
        )
        if actor is None:
            return False
        owner, owner_id = self.container(invocation)
        packet = captured_summon_application(
            self.fight.id,
            self.action_id,
            plan=plan,
            descriptor=CapturedDescriptor(
                descriptor.minimum_hp, descriptor.owner_id, -1, True
            ),
            uid=runner.uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            caster_id=caster.id,
            cell=invocation.cell,
            obstacle_index=actor.native_obstacle_id,
            timing_payload=ctx.timing_payload,
            container_type=owner["container_type"],
            container_id=owner_id,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
            running_value=runner.value,
        )
        deliveries = dict(getattr(self.fight, "native_summon_creation_deliveries", {}))
        if actor.id in deliveries:
            raise ValueError("Duplicate native324 creation delivery")
        deliveries[actor.id] = {"opcode": packet[0], "payload_hex": packet[1].hex()}
        self.fight.native_summon_creation_deliveries = deliveries
        self.packets.insert(creation_packet_index, packet)
        runner.finish_application()
        self._phase(effect, invocation, runner, 3)
        self._phase(effect, invocation, runner, 4)
        notify_runner_value(invocation, runner.value)
        return True
