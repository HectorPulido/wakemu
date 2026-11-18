"""Changed capture qualification only; ordinary creature AI is reused."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server import owned_story_capture_qualification as capture


class OwnedStoryCaptureQualificationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "map_id": 879,
            "steps": [{"kind": "room_victory", "reference": 1}],
            "capture_qualification": [
                {
                    "room_order": 1,
                    "original_monster_reference": 3173,
                    "native_effect_reference": 117956,
                    "evidence": "Original4478 capture native28/117956; map879 training",
                }
            ],
        }
        self.owner = SimpleNamespace(id=10, controlled=True, owner_id=20, hp=1, team=0)
        self.target = SimpleNamespace(id=-100, hp=0, team=1)
        self.events = [
            {
                "kind": "kill_hp_minimum_update",
                "effect_class": 28,
                "generic_effect": 117956,
                "source_id": 10,
                "target_id": -100,
                "hp_before": 50000,
                "hp": 0,
            },
            {"kind": "death", "actor_id": -100},
        ]
        self.fight = SimpleNamespace(
            actors={10: self.owner, -100: self.target},
            phase="finished",
            winner=0,
            events=self.events,
            native_summon_registrations={},
        )
        self.original = [{"id": -100, "ref": 3173}]

    def qualifies(self):
        return capture.qualified(self.policy, self.fight, 10, self.original, 1)

    def test_original_native_capture_and_absent_policy(self):
        self.assertTrue(self.qualifies())
        original = deepcopy(self.policy)
        del original["capture_qualification"]
        self.fight.events = []
        self.assertTrue(capture.qualified(original, self.fight, 10, self.original, 1))

    def test_ordinary_admin_win_or_unrelated_kill_does_not_capture(self):
        for changes in (
            {"generic_effect": 99},
            {"source_id": 11},
            {"target_id": -101},
            {"hp_before": 0},
            {"hp": 1},
            {"effect_class": 100},
        ):
            with self.subTest(changes=changes):
                self.fight.events = [{**self.events[0], **changes}, self.events[1]]
                self.assertFalse(self.qualifies())
        self.fight.events = [{"kind": "death", "actor_id": -100}]
        self.assertFalse(self.qualifies())

    def test_death_must_follow_real_capture_and_original_roster(self):
        self.fight.events = list(reversed(self.events))
        self.assertFalse(self.qualifies())
        self.fight.events = self.events
        self.original = [{"id": -100, "ref": 3225}]
        self.assertFalse(self.qualifies())
        self.original = [{"id": -100, "ref": 3173}]
        self.fight.native_summon_registrations[-100] = {"actor_id": -100}
        self.assertFalse(self.qualifies())

    def test_actual_owner_alive_and_win_required(self):
        for name, value in (("hp", 0), ("controlled", False), ("owner_id", None)):
            original = getattr(self.owner, name)
            setattr(self.owner, name, value)
            self.assertFalse(self.qualifies())
            setattr(self.owner, name, original)
        self.fight.winner = 1
        self.assertFalse(self.qualifies())
        self.fight.winner = 0
        self.fight.phase = "active"
        self.assertFalse(self.qualifies())

    def test_policy_rejects_changed_source_or_nonvictory_stage(self):
        for changes in (
            {"native_effect_reference": 117993},
            {"original_monster_reference": 3225},
            {"room_order": 2},
            {"evidence": ""},
        ):
            with self.subTest(changes=changes):
                selected = deepcopy(self.policy)
                selected["capture_qualification"][0].update(changes)
                with self.assertRaises(ValueError):
                    capture.policy(selected)
        selected = deepcopy(self.policy)
        selected["map_id"] = 527
        with self.assertRaises(ValueError):
            capture.policy(selected)


if __name__ == "__main__":
    unittest.main()
