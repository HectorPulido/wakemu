import unittest
from types import SimpleNamespace
from wakfu_server.combat_summon import (
    summon_specification,
    summon_additional_payload,
    RegisteredSummonAuthority,
    SummonRegistration,
    fresh_summon_insertion,
    prepare_summon,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_spellbook import fresh_action_book


def metadata(summon=False):
    targeting = {"bcN": 0}
    if summon:
        targeting.update(dpr_id=7, dpu_id=7, buX=False)
    return NativeActorAuthority(
        targeting,
        False,
        frozenset(),
        frozenset(),
        False,
        3251,
        0,
        {},
        True,
        is_summon=summon,
        summon_root_id=7,
        native_instance_id=1134,
        native_real_level=6,
        is_carrying=False if summon else None,
        native_controller_id=7 if summon else None,
    )


class Ordinary:
    def __call__(self, fight, actor):
        if set(fight.actors) != {7, -7}:
            raise ValueError("Ordinary roster changed")
        return metadata()

    def properties(self, fight, actor):
        self(fight, actor)
        return frozenset()

    world_properties = properties


class SummonTests(unittest.TestCase):
    def spec(self, p, **extra):
        args = dict(
            evaluation_level=20,
            container_present=True,
            caster_level=12,
            caster_team=0,
            caster_direction=6,
            native_minimum_level=1,
        )
        args.update(extra)
        return summon_specification({"effect_class": 307}, {"parameters": p}, **args)

    def test_native_descriptor_and_uid_probe_bytes(self):
        s = self.spec([3251, 6, 1, 3, 1, 0, -2])
        self.assertEqual(
            (
                s.reference,
                s.level,
                s.self_controlled,
                s.direction,
                s.team,
                s.timeline_anchor,
                s.timeline_offset,
            ),
            (3251, 6, True, 3, 1, "current", -2),
        )
        self.assertEqual(summon_additional_payload(901).hex(), "6203208507")

    def test_native_none_team_inherits_actual_caster_after_byte_narrowing(self):
        for actual_team in (0, 1):
            for descriptor_team in (-1, 255):
                specification = self.spec(
                    [1380, -2, 0, -1, descriptor_team], caster_team=actual_team
                )
                self.assertEqual(specification.team, actual_team)
                self.assertEqual(specification.direction, 6)
                self.assertEqual(specification.level, 12)
        with self.assertRaisesRegex(ValueError, "direction/team"):
            self.spec([1380, -2, 0, -1, -2])

    def test_complete_descriptor_matches_native_eZm_writer(self):
        from wakfu_server.combat_summon_codec import summon_descriptor_blob

        spec = self.spec([3251, 6, 1, 3, 1, 0, -2])
        actual = summon_descriptor_blob(
            spec, actor_id=901, caster_id=7, obstacle_index=-1, properties=()
        )
        # ProbeNativeSummonDescriptor: actual eZl protected writer -> eZm fj.
        self.assertEqual(
            actual.hex(),
            "010cb30000ffffffff00000000000003850006ff000000000003"
            "ffffffffffffffff000000000000000000000007fffffffe01",
        )

    def test_native_sphere_private_creation_and_wire_keep_original(self):
        from wakfu_server.combat_summon_creation import NativeSummonBuilder
        from wakfu_server.combat_summon_codec import summon_application

        f, _, _ = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        spec = self.spec([3791, 20, 0, 3, 0])
        timing = bytes.fromhex(
            "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
        )

        def encode(preview, specification, registration, cell):
            actor = preview.actors[registration.actor_id]
            return (
                summon_application(
                    preview.id,
                    99,
                    uid=902,
                    base_uid=None,
                    effect_reference=123,
                    caster_id=7,
                    cell=actor.position,
                    specification=spec,
                    actor_id=actor.id,
                    obstacle_index=actor.native_obstacle_id,
                    properties=tuple(sorted(registration.fight_properties)),
                    timing_payload=timing,
                ),
            )

        preview, packets = prepare_summon(
            f,
            spec,
            caster_id=7,
            cell=(1, 0, 0),
            authority=authority,
            allocate_actor_uid=lambda preview: 901,
            build_native_actor=NativeSummonBuilder(authority),
            encode_application=encode,
        )
        summoned = preview.actors[901]
        self.assertEqual(
            (summoned.hp, summoned.ap, summoned.mp, summoned.effect_stats[4]),
            (1, 0, 0, 0),
        )
        self.assertEqual(summoned.effective_level, 20)
        self.assertEqual(summoned.direction, spec.direction)
        self.assertEqual(
            preview.order, [7, -7]
        )  # Native property114, not a missing insertion.
        self.assertEqual(summoned.owner_id, 3)
        self.assertTrue(authority(preview, summoned).is_summon)
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 1)
        self.assertNotIn(901, f.actors)
        self.assertFalse(hasattr(f, "native_summon_registrations"))

    def test_native_descriptor_inherits_world_property47_explicitly(self):
        from wakfu_server.combat_summon_creation import NativeSummonBuilder

        class WorldCaster(Ordinary):
            def world_properties(self, fight, actor):
                self(fight, actor)
                return frozenset({47})

        f, _, _ = self.fixture()
        actor, record = NativeSummonBuilder(WorldCaster())(
            f, self.spec([3791, 20, 0, 3, 0]), 7, 901, (1, 0, 0)
        )
        self.assertIn(47, record.world_properties)
        self.assertEqual(record.controller_id, 7)
        self.assertEqual(
            actor.native_fight_property_counts,
            {property_id: 1 for property_id in record.fight_properties},
        )
        self.assertEqual(actor.native_fight_properties, record.fight_properties)

    def test_zero_descriptor_uses_native_resources_and_own_empty_book(self):
        from wakfu_server.combat_summon_creation import NativeSummonBuilder
        from wakfu_server.combat_summon_spellbook import actor_spellbook

        fight, _, _ = self.fixture()
        caster = fight.actors[7]
        original = (
            caster.effective_level,
            caster.owner_id,
            caster.hp,
            caster.ap,
            caster.mp,
        )
        specification = self.spec([3791, -1], evaluation_level=0)
        actor, registration = NativeSummonBuilder(Ordinary())(
            fight, specification, 7, 901, (1, 0, 0)
        )
        self.assertEqual(actor.effective_level, 0)
        self.assertEqual(
            (actor.hp, actor.ap, actor.mp, actor.effect_stats[4]), (1, 0, 0, 0)
        )
        self.assertEqual(actor.native_summon_action_book["descriptor_level"], 0)
        self.assertEqual(actor_spellbook(actor).levels, {})
        self.assertEqual(
            (actor.owner_id, actor.controlled, registration.controller_id), (3, True, 7)
        )
        self.assertEqual(
            (caster.effective_level, caster.owner_id, caster.hp, caster.ap, caster.mp),
            original,
        )

    def test_zero_inherited_level_differs_from_invalid_explicit_zero_mode(self):
        self.assertEqual(self.spec([3791, -1], evaluation_level=0).level, 0)
        self.assertEqual(self.spec([3791, -2], caster_level=0).level, 0)
        self.assertEqual(self.spec([3791, -1], evaluation_level=245).level, 245)
        with self.assertRaisesRegex(ValueError, "Invalid native summon level mode"):
            self.spec([3791, 0])
        with self.assertRaisesRegex(
            ValueError, "Missing native summon reference/level"
        ):
            self.spec([3791, -1], evaluation_level=32768)

    def test_level_modes_and_default_direction_anchor(self):
        self.assertEqual(self.spec([3251]).level, 20)
        self.assertEqual(self.spec([3251, -2]).level, 12)
        self.assertEqual(self.spec([3251, -3]).level, 1)
        self.assertEqual(self.spec([3251, 6, 0, 999]).direction, 6)
        self.assertEqual(self.spec([3251, 6]).timeline_anchor, "caster")
        with self.assertRaises(ValueError):
            self.spec([3251], container_present=False)
        # Native positive mode is narrowed with i2s before descriptor creation.
        self.assertEqual(self.spec([3251, 65536]).level, 0)

    def fixture(self):
        cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
        a = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 6, owner_id=3, controlled=True)
        b = Actor(-7, 1, (2, 0, 0), 60, 6, 3, 0, 6)
        f = Fight(1, [a, b], cells, {0: {a.position}, 1: {b.position}})
        f.phase = "active"
        f.order = [7, -7]
        f.turn_index = 0
        c = Actor(901, 0, (1, 0, 0), 60, 6, 3, 0, 6, owner_id=3, controlled=True)
        c.effect_stats = {1: 60, 2: 6, 3: 3}
        c.effect_maxima = dict(c.effect_stats)
        c.effect_minima = {1: 0, 2: 0, 3: 0}
        c.effect_frozen = frozenset()
        c.physical_radius = 0
        c.spell_ap_cost_modifiers = {}
        c.spell_range_modifiers = {}
        c.native_controller_id = 7
        c.native_master_id = 7
        c.native_carrier_id = None
        c.native_carried_actor_id = None
        c.native_summon_source = dict(
            ref=3251,
            level=6,
            caster_id=7,
            controller_id=7,
            native_relation_source="big.new_bje.fdt_initial_registration",
            native_symbiot_source="eZl.new_eHD.pRO_false",
        )
        # This fixture models a fresh native descriptor at ref 3251, level 6;
        # the exact class profile is required by registered summon authority.
        c.native_summon_action_book = fresh_action_book(3251, 6)
        c.native_obstacle_id = 2
        summon_metadata = metadata(True)
        summon_metadata.targeting["bcN"] = 2
        r = SummonRegistration(901, 7, 7, summon_metadata, frozenset({3}), frozenset())
        return f, c, r

    def test_registered_roster_does_not_relax_ordinary_authority(self):
        f, c, r = self.fixture()
        ordinary = Ordinary()
        authority = RegisteredSummonAuthority(ordinary)
        authority.register(f, c, r, new_order=[7, 901, -7], new_turn_index=0)
        with self.assertRaises(ValueError):
            ordinary(f, f.actors[7])
        self.assertTrue(authority(f, c).is_summon)
        self.assertIsNone(authority(f, f.actors[7]).summon_count)
        self.assertEqual(authority.properties(f, c), frozenset({3}))
        f.actors[999] = Actor(999, 0, (3, 0, 0), 60, 6, 3, 0, 6)
        with self.assertRaises(ValueError):
            authority(f, f.actors[7])

    def test_native_registration_accepts_controller_cell_before_carry(self):
        # Original creation groups may allow distance0 and carry the new QK
        # afterwards. QI identity ownership, not exclusive cells, is required.
        fight, actor, registration = self.fixture()
        actor.position = fight.actors[7].position
        authority = RegisteredSummonAuthority(Ordinary())
        authority.register(
            fight, actor, registration, new_order=[7, 901, -7], new_turn_index=0
        )
        self.assertIs(fight.actors[901], actor)
        self.assertEqual(actor.position, fight.actors[7].position)
        self.assertEqual(actor.native_controller_id, 7)
        self.assertEqual(actor.native_obstacle_id, 2)
        self.assertTrue(authority(fight, actor).is_summon)

    def test_native_creation_criterion_owns_other_occupied_cell_rejection(self):
        from wakfu_server.combat_conditions import (
            ConditionCell,
            ConditionContext,
            evaluate_condition,
        )

        criterion = "IsTargetCellFree() or GetDistanceBetweenCasterAndTarget() == 0"
        occupied = ConditionCell(True, False, (True,))
        for distance, expected in ((0, True), (1, False)):
            context = ConditionContext({}, occupied, caster_target_distance=distance)
            self.assertEqual(evaluate_condition(criterion, context), expected)
        free = ConditionContext(
            {}, ConditionCell(True, False), caster_target_distance=1
        )
        self.assertTrue(evaluate_condition(criterion, free))

    def test_ordinary_callbacks_keep_actual_reciprocal_carry_population(self):
        from dataclasses import replace
        from wakfu_server.combat_carrying import NativeCarryPair, carrying_relations

        class CarryOrdinary(Ordinary):
            def __call__(self, view, actor):
                super().__call__(view, actor)
                carrying_relations(view, actor)
                return metadata()

            def property_counts(self, view, actor):
                self(view, actor)
                return {3: 1}

            world_property_counts = property_counts

            def item_quantity(self, view, actor, references):
                self(view, actor)
                if getattr(self, "raise_item", False):
                    raise RuntimeError("inventory callback failed")
                return 4

        fight, actor, registration = self.fixture()
        actor.position = fight.actors[7].position
        actor.native_summon_source["ref"] = 3794  # Actual class-owned barrel.
        actor.native_summon_action_book = fresh_action_book(3794, 6)
        registration = replace(
            registration, authority=replace(registration.authority, breed_id=3794)
        )
        authority = RegisteredSummonAuthority(CarryOrdinary())
        authority.register(
            fight, actor, registration, new_order=[7, 901, -7], new_turn_index=0
        )
        controller = fight.actors[7]
        controller.native_carrier_id = None
        controller.native_carried_actor_id = actor.id
        actor.native_carrier_id = controller.id
        fight.native_carry_pairs = {
            controller.id: NativeCarryPair(
                controller.id,
                actor.id,
                controller.position,
                actor.direction,
                controller.direction,
                1000,
            )
        }
        self.assertEqual(authority.properties(fight, controller), frozenset())
        self.assertEqual(authority.world_properties(fight, controller), frozenset())
        self.assertEqual(authority.property_counts(fight, controller), {3: 1})
        self.assertEqual(authority.world_property_counts(fight, controller), {3: 1})
        self.assertEqual(authority.item_quantity(fight, controller, (32870,)), 4)
        # Callback scopes end even though the filtered roster cannot resolve
        # the carried summon independently.
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            carrying_relations(authority._ordinary_view(fight), controller)
        authority.ordinary.raise_item = True
        with self.assertRaisesRegex(RuntimeError, "inventory callback failed"):
            authority.item_quantity(fight, controller, (32870,))
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            carrying_relations(authority._ordinary_view(fight), controller)
        actor.native_carrier_id = None
        for callback in (
            authority.properties,
            authority.world_properties,
            authority.property_counts,
            authority.world_property_counts,
        ):
            with self.assertRaisesRegex(ValueError, "reciprocal"):
                callback(fight, controller)

    def test_owned_inventory_query_crosses_registered_roster_wrapper(self):
        f, c, r = self.fixture()

        class InventoryOrdinary(Ordinary):
            def item_quantity(self, preview, actor, references):
                self(preview, actor)
                return 4 if actor.id == 7 and references == (32870,) else 0

        authority = RegisteredSummonAuthority(InventoryOrdinary())
        authority.register(f, c, r, new_order=[7, 901, -7], new_turn_index=0)
        self.assertEqual(authority.item_quantity(f, f.actors[7], (32870,)), 4)
        self.assertEqual(authority.item_quantity(f, f.actors[-7], (32870,)), 0)
        with self.assertRaisesRegex(ValueError, "summoned inventory authority"):
            authority.item_quantity(f, c, (32870,))

    def test_summon_after_extra_turn_survives_native_round_reset(self):
        f, c, r = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        f.native_base_turn_order = [7, -7]
        f.order = [7, 7, -7]
        f.turn_index = 1
        authority.register(f, c, r, new_order=[7, 7, 901, -7], new_turn_index=1)
        self.assertEqual(f.order, [7, 7, 901, -7])
        self.assertEqual(f.native_base_turn_order, [7, 901, -7])
        self.assertIn(901, f.actors)
        f._advance()
        f._advance()
        f._advance()
        self.assertEqual(f.order, [7, 901, -7])
        self.assertEqual(f.current.id, 7)

    def test_failed_insertion_does_not_mutate_roster(self):
        f, c, r = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        with self.assertRaises(ValueError):
            authority.register(f, c, r, new_order=[901, 7, -7], new_turn_index=0)
        self.assertEqual(set(f.actors), {7, -7})
        self.assertFalse(hasattr(f, "native_summon_registrations"))

    def test_fresh_timeline_insertion_native_anchor_and_overflow(self):
        f, c, r = self.fixture()
        f.order = [7, -7, 8]
        f.turn_index = 1
        for mode, offset, expected in (
            (0, 1, 2),
            (1, -1, 3),
            (2, 1, 1),
            (0, 2147483647, 0),
        ):
            spec = self.spec([3251, 6, 0, 3, 0, mode, offset])
            order, current = fresh_summon_insertion(f, spec, caster_id=7, actor_id=901)
            self.assertEqual(order.index(901), expected)
            self.assertEqual(order[current], -7)
        with self.assertRaises(ValueError):
            fresh_summon_insertion(f, spec, caster_id=7, actor_id=7)

    def test_dead_retirement_preserves_identity_and_rejects_live_unsummon(self):
        f, c, r = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        authority.register(f, c, r, new_order=[7, 901, -7], new_turn_index=0)
        with self.assertRaises(ValueError):
            authority.retire(f, 901, new_order=[7, -7], new_turn_index=0)
        c.hp = 0
        authority.retire(f, 901, new_order=[7, -7], new_turn_index=0)
        self.assertIs(f.actors[901], c)
        self.assertTrue(f.native_summon_registrations[901]["retired"])
        self.assertTrue(authority(f, c).is_summon)

    def test_private_prepare_preserves_original_on_success_and_encoder_error(self):
        f, c, r = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        spec = self.spec([3251, 6, 0, 3, 0])
        args = dict(
            caster_id=7,
            cell=c.position,
            authority=authority,
            allocate_actor_uid=lambda preview: 901,
            build_native_actor=lambda *args: (c, r),
        )
        preview, packets = prepare_summon(
            f,
            spec,
            **args,
            encode_application=lambda *args: ((13497, b"explicit encoder fixture"),)
        )
        self.assertEqual(preview.order, [7, 901, -7])
        self.assertEqual(set(f.actors), {7, -7})

        self.assertEqual(packets[0][0], 13497)
        with self.assertRaises(ValueError):
            prepare_summon(f, spec, **args, encode_application=lambda *args: ())
        self.assertEqual(set(f.actors), {7, -7})

    def test_registered_caster_controlled_summon_uses_owned_turn_permissions(self):
        f, c, r = self.fixture()
        authority = RegisteredSummonAuthority(Ordinary())
        spec = self.spec([3251, 6, 0, 3, 0])
        order, index = fresh_summon_insertion(f, spec, caster_id=7, actor_id=901)
        authority.register(f, c, r, new_order=order, new_turn_index=index)
        f.end_turn(3, 7, 0)
        self.assertEqual(f.current.id, 901)
        with self.assertRaises(ValueError):
            f.spend(99, 901, ap=1)
        f.spend(3, 901, ap=1)
        self.assertEqual(c.ap, 5)
        f.end_turn(3, 901, c.turn_count)
        self.assertEqual(f.current.id, -7)
