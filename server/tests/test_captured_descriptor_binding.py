from copy import copy, deepcopy
from types import SimpleNamespace
import unittest
import test_combat_summon_retirement as fixture
from wakfu_server.combat_captured_descriptor_binding import (
    bind_descriptor_actor,
    clear_descriptor_actor,
    descriptor_actor_id,
)
from wakfu_server.combat_summon_retirement import retired_summon_ids


class CapturedDescriptorBindingTests(unittest.TestCase):
    def test_candidate_clear_preserves_source_and_other_slots(self):
        source = SimpleNamespace(
            native_captured_descriptor_actor_ids={"7": {"0": 901, "2": 902}}
        )
        candidate = copy(source)
        clear_descriptor_actor(candidate, 7, 0)
        self.assertEqual(
            source.native_captured_descriptor_actor_ids, {"7": {"0": 901, "2": 902}}
        )
        self.assertEqual(
            candidate.native_captured_descriptor_actor_ids, {"7": {"0": None, "2": 902}}
        )
        self.assertEqual(descriptor_actor_id(candidate, 7, 1), (False, None))

    def test_exact_retirement_clears_uid_and_preserves_descriptor(self):
        fight, owner, _, actor = fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        before = deepcopy(fight.native_captured_rosters[str(owner.id)]["slots"])
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        self.assertEqual(descriptor_actor_id(fight, owner.id, 0), (True, None))
        self.assertTrue(fight.native_captured_rosters[str(owner.id)]["available"][0])
        self.assertEqual(fight.native_captured_rosters[str(owner.id)]["slots"], before)
        self.assertEqual(retired_summon_ids(fight), frozenset((actor.id,)))

    def test_released_descriptor_missing_does_not_strand_retirement(self):
        fight, owner, _, actor = fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        clear_descriptor_actor(fight, owner.id, 0)
        for field in ("native_captured_rosters", "native_captured_roster_updates"):
            getattr(fight, field)[str(owner.id)]["slots"][0] = None
        before = deepcopy(fight.native_captured_rosters)
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        self.assertEqual(fight.native_captured_rosters, before)
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertNotIn(actor.id, fight.order)
        self.assertEqual(retired_summon_ids(fight), frozenset((actor.id,)))

    def test_same_species_new_uid_survives_old_retirement(self):
        fight, owner, _, actor = fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        clear_descriptor_actor(fight, owner.id, 0)
        # Same profile is a new descriptor; native pY matches actor UID only.
        bind_descriptor_actor(fight, owner.id, 0, 902)
        before = deepcopy(fight.native_captured_rosters)
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        self.assertEqual(fight.native_captured_rosters, before)
        self.assertEqual(descriptor_actor_id(fight, owner.id, 0), (True, 902))
        self.assertEqual(actor.native_obstacle_id, -1)
        self.assertEqual(retired_summon_ids(fight), frozenset((actor.id,)))

    def test_constructor_reaction_keeps_current_roster_changes_and_prepared_identity(
        self,
    ):
        from dataclasses import replace
        import test_captured_summon as plans
        from wakfu_server.characters.captured_roster import CapturedCreature
        from wakfu_server.combat_captured_summon import NativeCapturedSummonPipeline

        prepared = plans.CapturedSummonTests()
        original = prepared.roster()
        world = SimpleNamespace(roster=original)
        seen = []

        def create(preview, specification, descriptor, **kwargs):
            self.assertEqual(descriptor_actor_id(preview, 42, 0), (True, 99))
            # The constructor/initial-state callback changes another descriptor
            # and the selection. The native final Z(slot,false) preserves both.
            slots = list(preview.roster.slots)
            slots[2] = CapturedCreature(2, 72, "new during constructor")
            flags = list(preview.roster.available)
            flags[2] = True
            preview.roster = replace(
                preview.roster,
                slots=tuple(slots),
                available=tuple(flags),
                selected_slot=2,
            )
            return SimpleNamespace(id=99)

        pipeline = NativeCapturedSummonPipeline(
            profile_descriptor=lambda entry, **kwargs: seen.append(entry.profile_id)
            or object(),
            create=create,
            scale_characteristics=lambda *args: None,
            mark_symbiot=lambda *args: None,
            commit_roster=lambda preview, roster: setattr(preview, "roster", roster),
            bind_descriptor=bind_descriptor_actor,
            current_roster=lambda preview: preview.roster,
        )
        actor = pipeline.execute(
            prepared.plan(), original, preview=world, cell=(1, 2, 0)
        )
        self.assertEqual(actor.id, 99)
        self.assertEqual(seen, [71])
        self.assertEqual(world.roster.selected_slot, 2)
        self.assertEqual(
            world.roster.slots[2], CapturedCreature(2, 72, "new during constructor")
        )
        self.assertTrue(world.roster.available[2])
        self.assertFalse(world.roster.available[0])

    def test_retired_actor_cannot_retain_its_exact_descriptor_uid(self):
        fight, owner, _, actor = fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        with self.assertRaisesRegex(ValueError, "still owns a descriptor UID"):
            retired_summon_ids(fight)

    def test_malformed_other_slots_or_owners_fail_before_any_publication(self):
        for ledger in (
            {"7": {"bad": 101}},
            {"7": {"2": True}},
            {"7": {"2": 1 << 63}},
            {"8": {"-1": 101}},
            {"08": {"0": 101}},
            {8: {"0": 101}},
        ):
            with self.subTest(ledger=ledger):
                fight = SimpleNamespace(native_captured_descriptor_actor_ids=ledger)
                before = deepcopy(vars(fight))
                with self.assertRaises(ValueError):
                    clear_descriptor_actor(fight, 7, 6)
                self.assertEqual(vars(fight), before)
                self.assertIs(fight.native_captured_descriptor_actor_ids, ledger)

    def test_retired_actor_cannot_retain_its_uid_in_another_descriptor_slot(self):
        fight, owner, _, actor = fixture.SummonRetirementTests().fight(
            origin="captured"
        )
        bind_descriptor_actor(fight, owner.id, 0, actor.id)
        fight.apply_effect_damage(owner.id, actor.id, actor.hp)
        self.assertEqual(descriptor_actor_id(fight, owner.id, 0), (True, None))
        bind_descriptor_actor(fight, owner.id, 2, actor.id)
        self.assertEqual(
            fight.native_captured_descriptor_actor_ids[str(owner.id)],
            {"0": None, "2": actor.id},
        )
        before = deepcopy(fight.native_captured_descriptor_actor_ids)
        with self.assertRaisesRegex(ValueError, "still owns a descriptor UID"):
            retired_summon_ids(fight)
        self.assertEqual(fight.native_captured_descriptor_actor_ids, before)
