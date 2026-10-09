"""Native bje/ffx creation resources followed by eHD descriptor transforms.

No world monster level policy is applied. Visual copies require an owned
connected appearance plan and the actual cosmetic-equipment producer.
"""
from .combat_actor_snapshot import (
    native_actor_catalog,
    native_npc_creation_values,
    build_npc_snapshot,
)
from .combat_state import Actor
from .combat_obstacle_ids import assign_obstacle_ids
from .combat_summon import SummonRegistration
from .combat_runtime_adapter import NativeActorAuthority
from .combat_ordinary_authority import native_property_catalog
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
from .combat_stat_effects import apply_current_stat


def native_fresh_summon_authority(actor, reference):
    """Actual detached big/bje before team, controller and QI insertion."""
    return NativeActorAuthority(
        dict(
            bcN=-1,
            is_amO=True,
            is_eGj=True,
            is_Qq=False,
            is_eHH=True,
            bEe=True,
            UNTARGETTABLE_BY_OTHER=False,
            buX=False,
            dTE=True,
            dpu_id=actor.id,
            dpr_id=actor.id,
            baG=False,
            baK=False,
            baF=False,
        ),
        False,
        frozenset(),
        frozenset(),
        False,
        reference,
        None,
        None,
        True,
        is_summon=True,
        summon_root_id=actor.id,
        is_carrying=False,
        is_challenger=False,
        native_real_level=actor.effective_level,
        native_instance_id=None,
        native_controller_id=actor.id,
        native_in_play=False,
        # This producer constructs actual bje, whose dpR is unconditionally true.
        native_ai_control_baseline=True,
        native_controlled_by_ai=actor.native_controlled_by_ai,
        # Fresh bjm.pHM is null until eHD.a after aQc; eGz.dTC is false.
        native_summoned_from_symbiot=False,
        native_actor_type=1,  # Actual bje.dpV -> eGj.aWs.asQ.
        native_sex=0,  # eGj.aWs resets bao before descriptor hydration.
    )


def register_fresh_summon_obstacle(preview, actor):
    """Actual fresh eGj QK registration, shared with registered faW areas."""
    if getattr(preview, "native_qi_slots", None) is not None:
        from .combat_qi_fight import current_registry

        # This runs before inserting the new actor into the authoritative
        # roster. Validate the existing population, then register the QK.
        registry = current_registry(preview)
        slot = registry.register(
            dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=actor.physical_radius,
                indexed=False,
                # Actual eGj.bcO/bcP are true, independent of breed affiliation.
                movement_blocking=True,
            )
        )
        if slot < 0:
            raise ValueError("Native QI summon obstacle byte capacity exhausted")
        actor.native_obstacle_id = slot
        preview.native_qi_slots = registry.serialized_slots()
        preview.native_qi_touched_cells = registry.serialized_cells()
        preview.native_qi_byte_topology = registry.serialized_byte_topology()
        return
    # The older actor-only producer is safe only when the actual registered
    # area population is proven not to contain additional QK obstacles.
    for row in getattr(preview, "native_effect_areas", {}).values():
        non_obstacle_faw = (
            isinstance(row, dict)
            and row.get("native_area_contract") == "faW"
            and isinstance(row.get("native_faw_constructor"), dict)
            and row["native_faw_constructor"].get("obstacle") is False
            and row.get("native_obstacle_source") == "fbm.constructor"
        )
        if (
            not isinstance(row, dict)
            or (
                row.get("native_area_contract")
                not in (SUPPORTED_AREA_CONTRACTS - {"faW"})
                and not non_obstacle_faw
            )
            or row.get("native_obstacle_id") != -1
        ):
            raise ValueError("Missing shared native QI summon/area slot authority")
    assign_obstacle_ids([*preview.actors.values(), actor])


class NativeSummonBuilder:
    def __init__(
        self,
        actor_authority,
        *,
        characteristics=None,
        properties=None,
        initialize_states=None,
        initial_states=None,
        ability_profiles=None,
        descriptor_initializer=None
    ):
        self.actor_authority = actor_authority
        self.characteristics = (
            native_actor_catalog() if characteristics is None else characteristics
        )
        self.properties = (
            native_property_catalog() if properties is None else properties
        )
        self.initialize_states = initialize_states
        self.initial_states = initial_states
        self.ability_profiles = ability_profiles
        self.descriptor_initializer = descriptor_initializer
        if descriptor_initializer is not None and not callable(descriptor_initializer):
            raise ValueError("Native descriptor initializer must be callable")

    def __call__(
        self,
        preview,
        specification,
        caster_id,
        actor_id,
        cell,
        *,
        creation_properties=None
    ):
        caster = preview.actors[caster_id]
        parent = self.actor_authority(preview, caster)
        profile = self.properties["npc"].get(str(specification.reference))
        if profile is None:
            raise ValueError("Missing native summoned breed properties")
        fight_properties = frozenset(profile["fight_properties"])
        # eZl307 passes profile eHN; eZr324 passes null eHN. Descriptor
        # transforms below still read the original profile independently.
        increments = (
            fight_properties
            if creation_properties is None
            else frozenset(creation_properties)
        )
        if any(type(value) is not int or not 0 <= value < 128 for value in increments):
            raise ValueError("Invalid native construction property increments")
        world_properties = frozenset(profile["world_properties"])
        world_provider = getattr(self.actor_authority, "world_properties", None)
        if not callable(world_provider):
            raise ValueError("Missing native summoner world-property authority")
        caster_world = frozenset(world_provider(preview, caster))
        # Actual eHD.a copies eHQ.pSW: category0/property47, after descriptor.
        if 47 in caster_world:
            world_properties = world_properties | {47}
        visual_copy = None
        if 101 in increments:
            if specification.self_controlled:
                raise ValueError("Missing native self-controller bje visual source")
            from .combat_summon_visual_copy import plan_summon_visual_copy

            visual_copy = plan_summon_visual_copy(self.actor_authority, preview, caster)
        # eZl.c has an additional PJ(source.dsK()) call after the common
        # constructor's bPi/ac visual copy; it is not that same callsite.
        equipment_replication = None
        # Default profile eHN is the307 source path. Captured324 and copied1002
        # explicitly supply null/empty creation properties and lack this call.
        if specification.reference == 3251 and creation_properties is None:
            from .combat_character_copy_equipment import copied_equipment_source

            equipment_replication = copied_equipment_source(parent, caster.id)
        values = native_npc_creation_values(
            specification.reference, specification.level, catalog=self.characteristics
        )
        actor = Actor(
            actor_id,
            specification.team,
            cell,
            values[1]["current"],
            values[2]["current"],
            values[3]["current"],
            values[35]["current"],
            specification.level,
            max_hp=values[1]["maximum"],
            direction=specification.direction,
        )
        snapshot = build_npc_snapshot(
            {"id": actor_id, "ref": specification.reference},
            actor,
            wp_current=values[4]["current"],
            wp_maximum=values[4]["maximum"],
            running_effects=(),
            catalog=self.characteristics,
        )
        snapshot.install(actor)
        actor.native_obstacle_id = -1
        actor.native_fight_property_counts = {}
        actor.native_fight_properties = frozenset()
        actor.native_world_properties = frozenset(profile["world_properties"])
        from .combat_native_death_status import initialize_fresh_bje_death_status

        initialize_fresh_bje_death_status(actor)
        # eZl constructs new eHD with JVM-default pRO=false and never lE(true).
        # eZr324 sets lE(true) only after its common creation factory returns.
        actor.native_summoned_from_symbiot = False
        from .combat_summon_spellbook import fresh_action_book

        actor.native_summon_action_book = fresh_action_book(
            specification.reference, specification.level, profiles=self.ability_profiles
        )
        from .combat_summon_initial_states import (
            initial_state_plan,
            native_initial_states,
        )

        initial_profiles = (
            native_initial_states()
            if self.initial_states is None
            else self.initial_states
        )
        initial_row = initial_profiles.get(str(specification.reference))
        if initial_row is None:
            raise ValueError("Missing class summon initial-state source")
        initial_plan = initial_state_plan(
            initial_row["initial_state_triples"],
            specification.level,
        )
        if initial_plan:
            if not callable(self.initialize_states):
                raise ValueError("Missing native fresh summon initialization authority")
            # Native aQc runs with ID/position/ffx available, before eHD.a,
            # profile PB increments, controller/team and QI insertion.
            final_team = actor.team
            actor.team = -1
            try:
                self.initialize_states(preview, actor, initial_plan)
            finally:
                actor.team = final_team
        if self.descriptor_initializer is not None:
            # Native eHD.a follows cle, before DMG_INHERIT/PB/controller/QI.
            # Captured pRL/name/owner descriptor transforms require their
            # actual source provider; no307 defaults are fabricated here.
            self.descriptor_initializer(preview, actor, specification, caster)
        if 47 in caster_world:
            actor.native_world_properties = actor.native_world_properties | {47}
        world_properties = actor.native_world_properties
        if 81 in fight_properties:
            if caster.effect_stats is None or 20 not in caster.effect_stats:
                raise ValueError("Missing native summoner DMG_IN_PERCENT20")
            result = apply_current_stat(
                family="eWQ",
                current=actor.effect_stats[20],
                minimum=actor.effect_minima[20],
                maximum=actor.effect_maxima[20],
                requested=caster.effect_stats[20],
                percent=False,
                executable=True,
                frozen=20 in actor.effect_frozen,
                source_guards_verified=True,
                limit_policy="NORMAL",
            )
            actor.effect_stats[20] = result["current"]
        # eZl.C assigns one per distinct descriptor property; big.a then
        # increments those IDs AFTER initial states and eHD transforms.
        from .combat_property_stack import add_property

        for property_id in increments:
            add_property(actor.native_fight_property_counts, property_id)
        actor.native_fight_properties = frozenset(
            property_id
            for property_id, count in actor.native_fight_property_counts.items()
            if count != 0
        )
        controller_id = actor_id if specification.self_controlled else caster_id
        # Fresh missing UID -> new bje; fdy initializes saH and saJ equally.
        # Physical pGW/pGV start null and are independent of those relations.
        actor.native_controller_id = controller_id
        actor.native_master_id = controller_id
        actor.native_carrier_id = None
        actor.native_carried_actor_id = None
        if not specification.self_controlled:
            actor.owner_id, actor.controlled = caster.owner_id, caster.controlled
        root_id = actor_id if specification.self_controlled else parent.summon_root_id
        if root_id is None:
            raise ValueError("Missing native controller chain root")
        register_fresh_summon_obstacle(preview, actor)
        targeting = dict(
            bcN=actor.native_obstacle_id,
            is_amO=True,
            is_eGj=True,
            is_Qq=False,
            is_eHH=True,
            bEe=42 not in actor.native_fight_properties,
            UNTARGETTABLE_BY_OTHER=21 in actor.native_fight_properties,
            buX=False,
            dTE=True,
            dpu_id=controller_id,
            dpr_id=controller_id,
            baG=False,
            baK=False,
        )
        metadata = NativeActorAuthority(
            targeting,
            False,
            frozenset(),
            frozenset(),
            False,
            specification.reference,
            0,
            {},
            True,
            is_summon=True,
            summon_root_id=root_id,
            is_carrying=False,
            is_challenger=False,
            native_real_level=specification.level,
            native_instance_id=parent.native_instance_id,
            native_controller_id=controller_id,
            native_ai_control_baseline=True,  # Actual new bje.dpR, not ownership.
            native_controlled_by_ai=actor.native_controlled_by_ai,
            native_summoned_from_symbiot=actor.native_summoned_from_symbiot,
            native_actor_type=1,  # Actual constructed bje.dpV, not controller type.
            native_sex=0,  # eHD.aXz is literal zero for fresh/captured descriptors.
        )
        actor.native_summon_source = dict(
            ref=specification.reference,
            level=specification.level,
            direction=specification.direction,
            caster_id=caster_id,
            controller_id=controller_id,
            native_relation_source="big.new_bje.fdt_initial_registration",
            native_symbiot_source="eZl.new_eHD.pRO_false",
        )
        if visual_copy is not None:
            actor.native_pending_summon_visual_copy = visual_copy
        if equipment_replication is not None:
            actor.native_pending_summon_equipment_replication = equipment_replication
        return actor, SummonRegistration(
            actor_id,
            caster_id,
            controller_id,
            metadata,
            increments,
            world_properties,
        )
