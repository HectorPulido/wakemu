"""Current summon creation and settled-retirement semantic regressions."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

import test_combat_summon as creation_fixture
import test_combat_summon_retirement as retirement_fixture
from wakfu_server.combat_reproduction_state import encode_state
from wakfu_server.combat_summon import RegisteredSummonAuthority, prepare_summon
from wakfu_server.combat_summon_codec import summon_application
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_summon_lifecycle import (
    prepare_registration,
    prepare_retirements,
)
from wakfu_server.combat_summon_retirement import settle_summon_retirements
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.combat_qi_fight import current_registry


def full_observation(fight, packets=()):
    """Preserve the entire graph, including aliases, key types and events."""
    observation = encode_state({"fight": fight, "packets": tuple(packets)})
    if observation["services"]:
        raise AssertionError("Summon observation omitted runtime services")
    return observation


class SummonLifecycleSemanticTests(unittest.TestCase):
    def create(self, *, profile=3251, level=6, encoder_failure=False):
        helper = creation_fixture.SummonTests()
        import test_combat_spell_transaction as native_fixture
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck

        # Reuse the native entry fixture's connected player, actual snapshots
        # and QI terrain. Profile3251 copies bjo visuals and its eSU operand;
        # structural registration metadata cannot authorize that constructor.
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            5,
            20,
            native_qi=True,
            variation_seed=0,
        )
        character["appearance"] = dict(sex=0, clothIndex=0)
        factory, _ = server_runtime(
            character,
            {-7: monster},
            encode_deck([], []),
            action_id=99,
            critical=False,
            rng=Random(0),
        )
        authority = factory.summon_authority
        caster = fight.actors[7]
        occupied = {actor.position for actor in fight.actors.values()}
        cell = next(
            cell
            for cell in sorted(fight.walkable)
            if cell not in occupied
            and cell[2] == caster.position[2]
            and abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
            == 1
        )
        before = full_observation(fight)
        spec = helper.spec([profile, level, 0, 3, 0])

        def encode(preview, specification, registration, cell):
            if encoder_failure:
                raise ValueError("Explicit encoding failure after registration")
            actor = preview.actors[registration.actor_id]
            return (
                summon_application(
                    preview.id,
                    99,
                    uid=902,
                    base_uid=None,
                    effect_reference=123,
                    caster_id=7,
                    cell=cell,
                    specification=specification,
                    actor_id=actor.id,
                    obstacle_index=actor.native_obstacle_id,
                    properties=tuple(sorted(registration.fight_properties)),
                    timing_payload=bytes.fromhex(
                        "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
                    ),
                ),
            )

        if encoder_failure:
            with self.assertRaisesRegex(ValueError, "Explicit encoding failure"):
                prepare_summon(
                    fight,
                    spec,
                    caster_id=7,
                    cell=cell,
                    authority=authority,
                    allocate_actor_uid=lambda preview: 901,
                    build_native_actor=NativeSummonBuilder(authority),
                    encode_application=encode,
                )
            self.assertEqual(full_observation(fight), before)
            return fight, (), ()
        preview, packets = prepare_summon(
            fight,
            spec,
            caster_id=7,
            cell=cell,
            authority=authority,
            allocate_actor_uid=lambda preview: 901,
            build_native_actor=NativeSummonBuilder(authority),
            encode_application=encode,
        )
        self.assertEqual(full_observation(fight), before)
        self.assertIsNot(preview.actors[7], fight.actors[7])
        self.assertEqual(packets[0][0], 12613)
        self.assertTrue(packets[0][1])
        actor = preview.actors[901]
        self.assertEqual(actor.native_controller_id, 7)
        self.assertEqual(actor.native_master_id, 7)
        self.assertEqual(actor.owner_id, fight.actors[7].owner_id)
        self.assertTrue(actor.controlled)
        self.assertEqual(actor.effective_level, level)
        self.assertEqual(actor.native_summon_source["ref"], profile)
        self.assertEqual(preview.native_summon_registrations[901]["actor_id"], 901)
        self.assertGreaterEqual(actor.native_obstacle_id, 0)
        self.assertEqual(
            current_registry(preview).slots[actor.native_obstacle_id]["identity"],
            ["actor", 901],
        )
        self.assertEqual(preview.current.id, 7)
        return preview, packets, ()

    def test_native_creation_preserves_nonempty_book_controller_qi_timeline_and_packets(
        self,
    ):
        right, right_packets, _ = self.create()
        self.assertTrue(actor_action_book(right.actors[901])["actions"])
        self.assertIn(901, right.order)

    def test_native_property114_preserves_timeline_exclusion_and_empty_owned_book(self):
        right, right_packets, _ = self.create(profile=3791, level=20)
        self.assertNotIn(901, right.order)
        self.assertEqual(actor_action_book(right.actors[901])["actions"], [])

    def test_real_creation_then_death_settlement_preserves_owned_lifecycle(self):
        fight, packets, _ = self.create()
        actor = fight.actors[901]
        old_slot = actor.native_obstacle_id
        fight.apply_effect_damage(7, 901, actor.hp)
        self.assertIs(fight.actors[901], actor)
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertIsNone(fight.native_qi_slots[old_slot])
        self.assertNotIn(901, fight.order)
        self.assertIn(901, fight.native_summon_retirements)
        self.assertTrue(
            any(event["kind"] == "summon_out_of_play" for event in fight.events)
        )

    def test_settlement_origins_preserve_captured_release_copied_ownership_and_events(
        self,
    ):
        for origin in ("ordinary", "captured", "copied"):
            with self.subTest(origin=origin):
                (
                    fight,
                    owner,
                    _,
                    actor,
                ) = retirement_fixture.SummonRetirementTests().fight(origin=origin)
                records = deepcopy(fight.native_summon_registrations)
                fight.apply_effect_damage(owner.id, actor.id, actor.hp)
                self.assertEqual(fight.native_summon_registrations, records)
                self.assertIs(fight.actors[901], actor)
                self.assertEqual(
                    fight.native_summon_retirements[901]["captured"],
                    origin == "captured",
                )
                self.assertEqual(
                    fight.native_summon_retirements[901]["copied"], origin == "copied"
                )
                if origin == "captured":
                    self.assertTrue(fight.native_captured_rosters["7"]["available"][0])
                    self.assertEqual(
                        fight.native_captured_roster_updates,
                        fight.native_captured_rosters,
                    )

    def test_failed_encoder_preserves_original_full_graph(self):
        self.create(encoder_failure=True)

    def test_registration_preflight_failure_is_atomic_and_keeps_live_actor_identity(
        self,
    ):
        helper = creation_fixture.SummonTests()
        fight, actor, record = helper.fixture()
        record = replace(record, controller_id=999)
        before = full_observation(fight)
        owner = fight.actors[7]
        with self.assertRaisesRegex(ValueError, "Invalid owned summon"):
            RegisteredSummonAuthority(creation_fixture.Ordinary()).register(
                fight,
                actor,
                record,
                new_order=[7, 901, -7],
                new_turn_index=0,
            )
        self.assertEqual(full_observation(fight), before)
        self.assertIs(fight.actors[7], owner)

    def test_retirement_preparation_does_not_publish_or_retire_hp_zero_without_death(
        self,
    ):
        fight, _, _, actor = retirement_fixture.SummonRetirementTests().fight()
        actor.hp = 0
        before = full_observation(fight)
        self.assertIsNone(prepare_retirements(fight))
        self.assertEqual(full_observation(fight), before)
        self.assertGreaterEqual(actor.native_obstacle_id, 0)

    def test_retirement_prepares_on_private_graph_and_invalid_captured_release_is_atomic(
        self,
    ):
        fight, owner, _, actor = retirement_fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        # The real damage producer records death; keep the outer chain
        # open until explicit preparation so this case can inspect it.
        fight._resolution_depth = 1
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        fight._resolution_depth = 0
        before = full_observation(fight)
        plan = prepare_retirements(fight)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.retired, (901,))
        self.assertEqual(full_observation(fight), before)
        self.assertIs(fight.actors[901], actor)
        fight.native_captured_rosters = {}
        # The publisher also accepts the authentic durable update
        # checkpoint when no live overlay exists. Remove both sources
        # to exercise missing release authority rather than fallback.
        fight.native_captured_roster_updates = {}
        broken = full_observation(fight)
        with self.assertRaises(ValueError):
            settle_summon_retirements(fight)
        self.assertEqual(full_observation(fight), broken)
        self.assertGreaterEqual(actor.native_obstacle_id, 0)

    def test_captured_handler_actual_creation_preserves_native_contract(self):
        import test_captured_summon_handler as captured_fixture

        captured_fixture.CapturedRuntimeHandlerTests().test_original_profile_book_fan_codec_owned_slot_and_plain_checkpoint()
        # The existing actual324 fixture checks native5347 book7356/7/8,
        # descriptor12613, consumed captured slot and durable checkpoint.

    def test_real_target_and_three_spell_copy_handlers_preserve_complete_graph_and_packets(
        self,
    ):
        import test_combat_target_copy_creation as target_fixture
        import test_native_recovery_actual839 as three_fixture
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        for family, fixture_type, reference in (
            (994, target_fixture.TargetCopyCreationTests, 2349),
            (839, three_fixture.Actual839Tests, 1549),
        ):
            with self.subTest(family=family):
                helper = fixture_type()
                try:
                    fight, handler, packets, original_book = helper.fixture()
                    self.assertTrue(
                        handler(
                            dict(
                                effect_class=family,
                                parameters=[],
                                target_masks=(None,) * 7,
                            ),
                            {},
                            EffectInvocation(388786, 1, -7, 7, (1, 1, 0)),
                        )
                    )
                    actor = fight.actors[902]
                    self.assertEqual(actor.native_summon_source["ref"], reference)
                    self.assertEqual(
                        actor.native_controller_id, actor.id if family == 839 else -7
                    )
                    self.assertEqual(actor.native_copy_pa_source["source_actor_id"], 7)
                    actions = actor_action_book(actor)["actions"]
                    self.assertTrue(actions)
                    self.assertTrue(
                        {row["uid"] for row in actions}
                        <= {row[0] for row in original_book}
                    )
                    self.assertEqual([opcode for opcode, _ in packets], [12613])
                finally:
                    helper.doCleanups()

    def certified_departed_summon(self):
        from wakfu_server.combat_pve_departure import retire_pve_actor

        fight, owner, _, actor = retirement_fixture.SummonRetirementTests().fight()
        # Use the actual source-certifying departure producer before its normal
        # withdrawn HP transition. Do not manufacture an absent fdy record.
        retire_pve_actor(fight, actor, root_actor_id=owner.id, owner_id=owner.owner_id)
        actor.pve_withdrawn = True
        from wakfu_server.combat_hp_raw import hp_raw_present, set_hp_raw_current

        if hp_raw_present(actor):
            set_hp_raw_current(actor, 0)
        else:
            actor.hp = 0
            actor.effect_stats[1] = 0
        return fight, actor

    def test_certified_pve_departed_summon_is_not_re_elected_for_ordinary_death(self):
        from wakfu_server.combat_pve_departure import retired_pve_actor_ids
        from wakfu_server.combat_global_pv_collections import global_fighter_registered

        fight, actor = self.certified_departed_summon()
        self.assertIn(actor.id, retired_pve_actor_ids(fight))
        self.assertFalse(global_fighter_registered(fight, actor.id))
        self.assertIn(actor.id, fight.native_summon_registrations)
        self.assertNotIn(actor.id, getattr(fight, "native_summon_retirements", {}))
        before = full_observation(fight)
        self.assertIsNone(prepare_retirements(fight))
        self.assertEqual(settle_summon_retirements(fight), ())
        self.assertEqual(full_observation(fight), before)
        self.assertIs(fight.actors[actor.id], actor)
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertFalse(global_fighter_registered(fight, actor.id))

    def test_missing_or_malformed_departure_cannot_hide_absent_summon_registration(
        self,
    ):
        for corruption in ("missing_certificate", "malformed_certificate"):
            with self.subTest(corruption=corruption):
                fight, actor = self.certified_departed_summon()
                if corruption == "missing_certificate":
                    fight.native_pve_departures = {}
                    expected = "Actual native fdy registration required"
                else:
                    fight.native_pve_departures[actor.id]["source"] = "unattested"
                    expected = "Missing actual owned PvE departure authority"
                before = full_observation(fight)
                with self.assertRaisesRegex(ValueError, expected):
                    prepare_retirements(fight)
                self.assertEqual(full_observation(fight), before)
                self.assertIs(fight.actors[actor.id], actor)
