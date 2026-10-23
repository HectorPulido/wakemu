"""Native fresh self-controller registration is not an owned-child lifetime."""
from copy import deepcopy
import unittest

import test_combat_summon as summon_fixture
import test_combat_summon_owner_death as death_fixture
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_summon_owner_death import settle, verify_transition
from wakfu_server.combat_qi_fight import current_registry


class NativeSelfControllerOwnerDeathTests(unittest.TestCase):
    def fixture(self):
        base = summon_fixture.SummonTests()
        fight, _, _ = base.fixture(native_qi=True)
        authority = RegisteredSummonAuthority(summon_fixture.Ordinary())
        # The real3791 profile and complete native builder produce the actor,
        # snapshot, controller/master/root and registration. No born ID is retagged.
        specification = base.spec([3791, 20, 1, 3, 0])
        actor, registration = NativeSummonBuilder(authority)(
            fight, specification, 7, 901, (1, 0, 0)
        )
        authority.register(
            fight,
            actor,
            registration,
            new_order=list(fight.order),
            new_turn_index=fight.turn_index,
        )
        self.assertEqual(
            (actor.native_controller_id, actor.native_master_id), (actor.id, actor.id)
        )
        self.assertEqual(registration.authority.summon_root_id, actor.id)
        self.assertEqual(actor.native_summon_source["caster_id"], 7)
        return fight, actor

    def test_real_self_controller_survives_caster_death_and_preserves_qi(self):
        fight, child = self.fixture()
        slot, hp = child.native_obstacle_id, child.hp
        fight.apply_effect_damage(-7, 7, fight.actors[7].hp)
        self.assertEqual(child.hp, hp)
        self.assertEqual(child.native_obstacle_id, slot)
        self.assertIsNotNone(current_registry(fight).slots[slot])
        self.assertFalse(
            any(
                event["kind"] == "owner_death_hp_minimum_update"
                for event in fight.events
            )
        )
        before = deepcopy(fight.events)
        self.assertEqual(settle(fight), ())
        self.assertEqual(fight.events, before)

    def test_owned_child_still_dies_and_keeps_durable_relationship_receipt(self):
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        fight, owner, enemy, child, _ = death_fixture.SummonOwnerDeathTests().fixture()
        fight.apply_effect_damage(enemy.id, owner.id, owner.hp)
        self.assertEqual(child.hp, 0)
        self.assertTrue(registered_ordinary_death(fight, child))
        self.assertEqual(settle(fight), ())

    def test_self_controller_requires_original_root_and_relationship_provenance(self):
        for mode in ("root", "master", "source_caster", "registration_controller"):
            with self.subTest(mode=mode):
                fight, child = self.fixture()
                fight._resolution_depth += 1
                try:
                    fight.apply_effect_damage(-7, 7, fight.actors[7].hp)
                finally:
                    fight._resolution_depth -= 1
                row = fight.native_summon_registrations[child.id]
                if mode == "root":
                    row["authority"]["summon_root_id"] = 7
                elif mode == "master":
                    child.native_master_id = 7
                elif mode == "source_caster":
                    child.native_summon_source["caster_id"] = -7
                else:
                    row["controller_id"] = 7
                before = deepcopy(fight.events)
                with self.assertRaises(ValueError):
                    settle(fight)
                self.assertGreater(child.hp, 0)
                self.assertEqual(fight.events, before)

    def test_independent_relationship_cannot_authenticate_owner_death_receipt(self):
        fight, child = self.fixture()
        with self.assertRaisesRegex(ValueError, "Independent summon"):
            verify_transition(fight, {}, {"actor_id": child.id})

    def test_failed_publication_rolls_back_caster_and_independent_qi(self):
        from wakfu_server.combat_native_action_ids import (
            MAX_NATIVE_ACTION_ID,
            native_delivery_boundary,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        fight, child = self.fixture()
        runtime = RuntimeMessages(fight)
        runtime.native_action_id = MAX_NATIVE_ACTION_ID
        before = deepcopy(fight.events)
        hp, slot = child.hp, child.native_obstacle_id

        @native_delivery_boundary
        def lethal(candidate):
            candidate.fight.apply_effect_damage(-7, 7, candidate.fight.actors[7].hp)
            return []

        with self.assertRaises(ValueError):
            lethal(runtime)
        self.assertEqual(fight.actors[7].hp, 60)
        self.assertEqual((child.hp, child.native_obstacle_id), (hp, slot))
        self.assertIsNotNone(current_registry(fight).slots[slot])
        self.assertEqual(fight.events, before)
        self.assertIsNone(runtime.awaiting_ack)
