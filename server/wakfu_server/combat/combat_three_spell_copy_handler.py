"""Fresh eZp839: actual class target, borrowed book and common bje construction."""
from dataclasses import replace
from .combat_summon_handler import NativeSummonHandler
from .combat_summon import SummonSpecification, fresh_summon_insertion
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_runner_callbacks import notify_runner_value
from .combat_value_transfer import apply_context_value
from .combat_character_copy_metadata import (
    native_copy_characteristics,
    native_copy_maximum_caps,
)
from .combat_character_copy_stats import copy_characteristics
from .combat_character_copy_runtime_book import (
    copied_class_book,
    install_copied_action_book,
)
from .combat_character_copy_codec import (
    CopiedCharacterDescriptor,
    connected_copy_appearance,
    character_copy_application,
)
from .combat_parameters import parameter_value
from .combat_character_copy_equipment import copied_equipment_source


from .combat_character_copy_handler import NativeCharacterCopyHandler
from .combat_three_spell_copy_descriptor import plan_class_target_copy
from .combat_three_spell_copy_runtime_book import install_target_copied_action_book


class NativeThreeSpellCopyHandler(NativeCharacterCopyHandler):
    def __init__(self, *args, source_effects, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_effects = source_effects

    def _calculate(self, effect, values, invocation, runner):
        from .combat_native_actor_lookup import native_actor

        target = native_actor(self.fight, invocation.target_id)
        if target is None:
            raise ValueError("Missing actual selected native839 target")
        definitions = (
            self.casting_definitions()
            if callable(self.casting_definitions)
            else self.casting_definitions
        )
        percentage = (
            parameter_value(effect["parameters"], 0, invocation.level)
            if effect["parameters"]
            else 100
        )
        descriptor, book_proof = plan_class_target_copy(
            self.fight,
            target,
            self.authority,
            definitions=definitions,
            effects=self.source_effects,
            percentage=percentage,
        )
        actor_uid = self.allocate_uid()
        while actor_uid in self.fight.actors:
            actor_uid = self.allocate_uid()
        caster = native_actor(self.fight, invocation.caster_id)
        if caster is None:
            raise ValueError("Missing actual native839 creating caster")
        specification = SummonSpecification(
            1549, descriptor.level, True, caster.direction, caster.team, "caster", 1
        )
        # eZp.faB.fTh is false: eZn.c skips PJ(source.dsK()).
        equipment = dict(
            native_plan=dict(roots=[]), native_creation_cell=tuple(caster.position)
        )
        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        return runner, specification, descriptor, book_proof, actor_uid, equipment

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        if effect["effect_class"] != 839 or invocation.native_running_uid is not None:
            raise ValueError("Missing fresh native eZp preparation")
        runner = NativeRunnerAmount(self.allocate_uid(), 839, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        self.prepared_runners[runner.uid] = self._calculate(
            effect, values, invocation, runner
        )
        return invocation

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 839 or self.fight.phase != "active":
            raise ValueError("Missing active fresh native eZp context")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing exact eZp execution authority")
        prepared = self.prepared_runners.pop(invocation.native_running_uid, None)
        if not ctx.executable:
            return False
        if ctx.retained or (
            invocation.native_running_uid is not None and prepared is None
        ):
            raise ValueError("Retained eZp descriptor lifecycle is not attested")
        if prepared is None:
            if self.event_lifecycle is not None:
                raise ValueError("Missing prepared eZp descriptor")
            prepared = self._calculate(
                effect,
                values,
                invocation,
                NativeRunnerAmount(self.allocate_uid(), 839, rng=self.rng),
            )
        runner, spec, descriptor, book_proof, actor_uid, equipment = prepared
        self._phase(effect, invocation, runner, 2)
        after = self.context(effect, invocation)
        if (
            not isinstance(after, StatExecutionContext)
            or after.source_guards_verified is not True
        ):
            raise ValueError("Missing exact eZp post-event authority")
        if not after.executable:
            return False
        from .combat_copied_pa import install_copied_pa_pool

        previous = self.builder.descriptor_initializer

        def initialize(preview, actor, specification, caster):
            install_copied_pa_pool(
                actor,
                descriptor.characteristics,
                metadata=native_copy_characteristics(),
                source_record=dict(
                    producer="eHI.pRU.ffh.a",
                    actor_id=actor.id,
                    source_actor_id=book_proof["source_actor_id"],
                    profile=1549,
                    native_copy_family=839,
                    effect_reference=invocation.reference,
                    copied_raw_characteristics=[
                        list(
                            (
                                row.identifier,
                                row.current,
                                row.minimum,
                                row.maximum,
                                row.percentage,
                            )
                        )
                        for row in descriptor.characteristics
                    ],
                ),
            )
            install_target_copied_action_book(
                actor,
                descriptor.book,
                book_proof,
                effect_reference=invocation.reference,
            )
            actor.native_character_copy_equipment_source = dict(equipment)
            actor.native_character_copy_appearance = dict(
                source_actor_id=book_proof["source_actor_id"],
                model=descriptor.appearance.model,
                appearance_hex=descriptor.appearance.appearance.hex(),
                categories=list(descriptor.appearance.categories),
                native_sex=(
                    ordinary.characters[book_proof["source_actor_id"]][
                        "appearance"
                    ].get("sex", 0)
                    + 128
                )
                % 256
                - 128,
            )

        ordinary = getattr(self.authority, "ordinary", self.authority)
        self.builder.descriptor_initializer = initialize
        creation_packet_index = len(self.packets)
        try:
            actor, registration = self.builder(
                self.fight,
                spec,
                invocation.caster_id,
                actor_uid,
                equipment["native_creation_cell"],
                creation_properties=(),
            )
        finally:
            self.builder.descriptor_initializer = previous
        actor.native_summon_source.update(
            native_character_copy_source="eZp839.faB.eHI.bPl",
            native_symbiot_source="eZp839.new_eHI.pRO_false",
            native_copy_source_actor_id=book_proof["source_actor_id"],
            native_copy_effect_reference=invocation.reference,
            native_copy_runner_uid=runner.uid,
        )
        registration = replace(
            registration,
            authority=replace(
                registration.authority,
                native_sex=actor.native_character_copy_appearance["native_sex"],
                # bje does not override eGj.dsK: the destination getter is zero,
                # independently of the source operand passed to equipment PJ.
                native_selected_cosmetics={7: 0},
            ),
        )
        order, index = (
            (list(self.fight.order), self.fight.turn_index)
            if 114 in registration.fight_properties
            else (
                fresh_summon_insertion(
                    self.fight, spec, caster_id=invocation.caster_id, actor_id=actor.id
                )
            )
        )
        owner, owner_id = self.container(invocation)
        descriptor = replace(descriptor, obstacle_index=actor.native_obstacle_id)
        packet = character_copy_application(
            self.fight.id,
            self.action_id,
            descriptor=descriptor,
            actual_actor_id=actor_uid,
            include_levels=True,
            uid=runner.uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            caster_id=invocation.caster_id,
            cell=equipment["native_creation_cell"],
            timing_payload=ctx.timing_payload,
            container_type=owner["container_type"],
            container_id=owner_id,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
            running_value=runner.value,
        )
        self.authority.register(
            self.fight, actor, registration, new_order=order, new_turn_index=index
        )
        initialize_equipment = getattr(self, "initialize_equipment", None)
        if equipment.get("native_plan", {}).get("roots") and not callable(
            initialize_equipment
        ):
            raise ValueError("Missing native copied cosmetic equipment effect producer")
        if callable(initialize_equipment):
            initialize_equipment(self.fight, actor, equipment)
        deliveries = getattr(self.fight, "native_summon_creation_deliveries", None)
        if deliveries is None:
            deliveries = self.fight.native_summon_creation_deliveries = {}
        if actor.id in deliveries:
            raise ValueError("Duplicate native eZp creation delivery")
        deliveries[actor.id] = dict(opcode=packet[0], payload_hex=packet[1].hex())
        self.packets.insert(creation_packet_index, packet)
        runner.finish_application()
        self._phase(effect, invocation, runner, 3)
        self._phase(effect, invocation, runner, 4)
        notify_runner_value(invocation, runner.value)
        return True
