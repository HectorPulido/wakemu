"""Fresh eZw1002: owned class source, eHI descriptor and common bje constructor."""
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


class NativeCharacterCopyHandler(NativeSummonHandler):
    def __init__(self, *args, casting_definitions, **kwargs):
        super().__init__(*args, **kwargs)
        self.casting_definitions = casting_definitions

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
                _nullable_target=True,
            )

    def _calculate(self, effect, values, invocation, runner):
        caster = self.fight.actors.get(invocation.caster_id)
        if caster is None:
            raise ValueError("Missing actual eZw source caster")
        actor_uid = self.allocate_uid()
        while actor_uid in self.fight.actors:
            actor_uid = self.allocate_uid()
        ordinary = getattr(self.authority, "ordinary", self.authority)
        source = ordinary.characters.get(caster.id)
        if not isinstance(source, dict) or not isinstance(source.get("name"), str):
            raise ValueError("Missing actual eZw class source name")
        authority = self.authority(self.fight, caster)
        equipment = copied_equipment_source(authority, caster.id)
        level = authority.native_real_level
        appearance = connected_copy_appearance(self.authority, self.fight, caster)
        definitions = (
            self.casting_definitions()
            if callable(self.casting_definitions)
            else self.casting_definitions
        )
        book, book_proof = copied_class_book(
            self.fight,
            caster,
            self.authority,
            allocate_uid=self.allocate_uid,
            definitions=definitions,
        )
        metadata = native_copy_characteristics()
        curves = metadata["breeds"].get(str(authority.breed_id))
        if curves is None:
            raise ValueError("Missing exact copied class level curves")
        percentage = (
            parameter_value(effect["parameters"], 0, invocation.level)
            if effect["parameters"]
            else 100
        )
        characteristics = copy_characteristics(
            caster.effect_stats,
            caster.effect_maxima,
            fresh_definitions=metadata["fresh_characteristics"],
            breed_curves=curves,
            level=level,
            percentage=percentage,
            maximum_caps=native_copy_maximum_caps(metadata, level),
            native_order=tuple(metadata["native_characteristic_order"]),
        )
        # eZn.C never calls eHD.lZ: vJ keeps pRM=-1. Its iR field carries
        # the independently reserved creature UID used by the constructor.
        descriptor = CopiedCharacterDescriptor(
            authority.breed_id,
            source["name"],
            caster.hp,
            -1,
            level,
            -1,
            -1,
            -1,
            False,
            percentage,
            appearance,
            book,
            characteristics,
        )
        specification = SummonSpecification(
            2382, level, False, caster.direction, caster.team, "caster", 1
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
        if effect["effect_class"] != 1002 or invocation.native_running_uid is not None:
            raise ValueError("Missing fresh native eZw preparation")
        runner = NativeRunnerAmount(self.allocate_uid(), 1002, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        self.prepared_runners[runner.uid] = self._calculate(
            effect, values, invocation, runner
        )
        return invocation

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 1002 or self.fight.phase != "active":
            raise ValueError("Missing active fresh native eZw context")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing exact eZw execution authority")
        prepared = self.prepared_runners.pop(invocation.native_running_uid, None)
        if not ctx.executable:
            return False
        if ctx.retained or (
            invocation.native_running_uid is not None and prepared is None
        ):
            raise ValueError("Retained eZw descriptor lifecycle is not attested")
        if prepared is None:
            if self.event_lifecycle is not None:
                raise ValueError("Missing prepared eZw descriptor")
            prepared = self._calculate(
                effect,
                values,
                invocation,
                NativeRunnerAmount(self.allocate_uid(), 1002, rng=self.rng),
            )
        runner, spec, descriptor, book_proof, actor_uid, equipment = prepared
        self._phase(effect, invocation, runner, 2)
        after = self.context(effect, invocation)
        if (
            not isinstance(after, StatExecutionContext)
            or after.source_guards_verified is not True
        ):
            raise ValueError("Missing exact eZw post-event authority")
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
                    source_actor_id=caster.id,
                    profile=2382,
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
            install_copied_action_book(
                actor,
                descriptor.book,
                book_proof,
                effect_reference=invocation.reference,
            )
            actor.native_character_copy_equipment_source = dict(equipment)
            actor.native_character_copy_appearance = dict(
                source_actor_id=caster.id,
                model=descriptor.appearance.model,
                appearance_hex=descriptor.appearance.appearance.hex(),
                categories=list(descriptor.appearance.categories),
                native_sex=(
                    ordinary.characters[caster.id]["appearance"].get("sex", 0) + 128
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
                invocation.cell,
                creation_properties=(),
            )
        finally:
            self.builder.descriptor_initializer = previous
        actor.native_summon_source.update(
            native_character_copy_source="eZw1002.faB.eHI.bPl",
            native_symbiot_source="eZw1002.new_eHI.pRO_false",
            native_copy_source_actor_id=invocation.caster_id,
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
            include_levels=False,
            uid=runner.uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            caster_id=invocation.caster_id,
            cell=invocation.cell,
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
            raise ValueError("Duplicate native eZw creation delivery")
        deliveries[actor.id] = dict(opcode=packet[0], payload_hex=packet[1].hex())
        self.packets.insert(creation_packet_index, packet)
        runner.finish_application()
        self._phase(effect, invocation, runner, 3)
        self._phase(effect, invocation, runner, 4)
        notify_runner_value(invocation, runner.value)
        return True
