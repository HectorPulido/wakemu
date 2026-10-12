"""Physical lifecycle witnesses for the AI atomic commit effect gate."""
import unittest
from copy import deepcopy
from types import SimpleNamespace

from wakfu_server.combat_commit_observables import actor_lifecycle_observables


class CommitObservablesTests(unittest.TestCase):
    def test_actual_positive_hp_retirement_is_observable(self):
        from test_combat_forced_retirement import ForcedRetirementTests

        fixture = ForcedRetirementTests()
        fight, _, target, _, retention, _, _ = fixture.fixture()
        hp = target.hp
        before = actor_lifecycle_observables(fight, target)
        fixture.retire(fight, target, retention)
        after = actor_lifecycle_observables(fight, target)
        self.assertEqual(target.hp, hp)
        self.assertNotEqual(before, after)
        self.assertEqual(after["fighter_status"], "OUT_OF_PLAY")
        self.assertEqual(after["qi_slot"], -1)
        self.assertFalse(after["timeline_member"])

    def test_noop_fake_receipt_and_rng_are_not_effect_witnesses(self):
        fight = SimpleNamespace(order=[7])
        actor = SimpleNamespace(id=7)
        before = actor_lifecycle_observables(fight, actor)
        fight.native_forced_retirement_records = {"7": {"source": "fake"}}
        actor.native_forced_retirement_receipt = {"source": "fake"}
        fight.rng_draw_count = 42
        self.assertEqual(before, actor_lifecycle_observables(fight, actor))

    def test_observation_is_read_only_and_copies_physical_slot(self):
        fight = SimpleNamespace(
            order=[7],
            native_qi_slots=[{"identity": ["actor", 7]}],
            native_timeline_member_counters={"7": 2},
            native_global_pv_collections={"fighter_status": {"7": "IN_PLAY"}},
        )
        actor = SimpleNamespace(id=7, native_obstacle_id=0)
        original = deepcopy(vars(fight))
        observed = actor_lifecycle_observables(fight, actor)
        self.assertEqual(vars(fight), original)
        fight.native_qi_slots[0]["identity"][1] = 8
        self.assertEqual(observed["qi_entry"]["identity"], ["actor", 7])
