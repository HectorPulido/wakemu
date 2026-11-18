"""Original-cause qualification for owned story defeat objectives."""

from copy import deepcopy
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_defeat_qualification as qualification


class OwnedStoryDefeatQualificationTests(unittest.TestCase):
    @staticmethod
    def selected(rule=True):
        selected = {"steps": [{"id": "defeat", "kind": "room_defeat", "reference": 3}]}
        if rule:
            selected["defeat_qualification"] = [
                {
                    "room_order": 3,
                    "original_monster_reference": 2427,
                    "native_effect_reference": 91610,
                    "minimum_actor_turn": 8,
                    "evidence": "native boss lethal effect, eighth turn or later",
                }
            ]
        return selected

    @staticmethod
    def fight(events=None, *, phase="finished", winner=2, player_hp=0, deliveries=None):
        return SimpleNamespace(
            actors={
                10: SimpleNamespace(hp=player_hp, team=1),
                20: SimpleNamespace(hp=1, team=2),
            },
            events=list(events or []),
            phase=phase,
            winner=winner,
            native_death_event_deliveries=deliveries or {},
        )

    @staticmethod
    def events(
        *,
        turn=8,
        source=20,
        native=91610,
        effect_class=28,
        death_after=True,
        cause=True
    ):
        result = [{"kind": "turn_started", "actor_id": 20, "actor_turn": turn}]
        if cause:
            result.append(
                {
                    "kind": "kill_hp_minimum_update",
                    "effect_class": effect_class,
                    "generic_effect": native,
                    "source_id": source,
                    "target_id": 10,
                    "hp_before": 14,
                    "hp": 0,
                }
            )
        if death_after:
            result.append({"kind": "death", "actor_id": 10})
        return result

    def qualifies(self, selected=None, fight=None, original=None):
        return qualification.qualified(
            selected or self.selected(),
            fight or self.fight(),
            10,
            original if original is not None else [{"id": 20, "ref": 2427}],
            3,
        )

    def test_eighth_turn_original_boss_effect_qualifies_and_nearby_cases_do_not(self):
        cases = (
            (
                "valid eighth turn",
                self.events(),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                True,
            ),
            (
                "early turn seven",
                self.events(turn=7),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "wrong killer",
                self.events(source=99),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "wrong native effect",
                self.events(native=91611),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "wrong native effect class",
                self.events(effect_class=27),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "ordinary death without effect",
                self.events(cause=False),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "effect without death",
                self.events(death_after=False),
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            ("victory", self.events(), "finished", 1, [{"id": 20, "ref": 2427}], False),
            (
                "not terminal",
                self.events(),
                "active",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
            (
                "source absent from frozen original monsters",
                self.events(),
                "finished",
                2,
                [{"id": 30, "ref": 2427}],
                False,
            ),
            (
                "death precedes cause",
                [
                    {"kind": "turn_started", "actor_id": 20, "actor_turn": 8},
                    {"kind": "death", "actor_id": 10},
                    {
                        "kind": "kill_hp_minimum_update",
                        "effect_class": 28,
                        "generic_effect": 91610,
                        "source_id": 20,
                        "target_id": 10,
                        "hp_before": 14,
                        "hp": 0,
                    },
                ],
                "finished",
                2,
                [{"id": 20, "ref": 2427}],
                False,
            ),
        )
        for name, events, phase, winner, original, expected in cases:
            with self.subTest(name=name):
                fight = self.fight(events, phase=phase, winner=winner)
                self.assertEqual(
                    self.qualifies(fight=fight, original=original), expected
                )

    def test_missing_optional_guard_preserves_ordinary_defeat_profile(self):
        selected = self.selected(rule=False)
        fight = self.fight([{"kind": "death", "actor_id": 10}])
        self.assertTrue(self.qualifies(selected=selected, fight=fight))

    def test_damage_cause_requires_matching_native_death_receipt_and_adjacent_death(
        self,
    ):
        selected = self.selected()
        selected["defeat_qualification"][0].pop("native_effect_reference")
        selected["defeat_qualification"][0].update(
            cause_kind="native_damage",
            native_effect_references=[333863],
        )
        turn = {"kind": "turn_started", "actor_id": 20, "actor_turn": 8}
        damage = {
            "kind": "damage",
            "source_id": 20,
            "target_id": 10,
            "amount": 14,
            "hp": 0,
        }
        death = {"kind": "death", "actor_id": 10, "sequence": 1013}
        receipt = {
            "policy": "wakemu.owned-ko-and-death-v3",
            "actor_id": 10,
            "source_id": 20,
            "generic_effect": 333863,
            "effect_class": 917,
            "event_id": 1013,
            "channel": 6,
        }
        cases = (
            ("authentic lethal damage", [turn, damage, death], {"1013": receipt}, True),
            ("missing receipt", [turn, damage, death], {}, False),
            (
                "wrong receipt",
                [turn, damage, death],
                {"1013": {**receipt, "generic_effect": 333864}},
                False,
            ),
            (
                "wrong cause source",
                [turn, {**damage, "source_id": 99}, death],
                {"1013": receipt},
                False,
            ),
            (
                "death not immediately after damage",
                [turn, damage, {"kind": "other"}, death],
                {"1013": receipt},
                False,
            ),
        )
        for name, events, deliveries, expected in cases:
            with self.subTest(name=name):
                damage_module = ModuleType("wakfu_server.combat_damage_healing")
                damage_module.DAMAGE_FAMILIES = (1, 2, 3, 4, 5, 917, 1083)
                with patch.dict(
                    sys.modules, {"wakfu_server.combat_damage_healing": damage_module}
                ):
                    self.assertEqual(
                        self.qualifies(
                            selected=selected,
                            fight=self.fight(events, deliveries=deliveries),
                        ),
                        expected,
                    )

    def test_policy_rejects_bad_and_duplicate_declarations(self):
        bad_rows = [
            None,
            {
                "room_order": 3,
                "original_monster_reference": 2427,
                "native_effect_reference": 91610,
                "minimum_actor_turn": 8,
                "evidence": " ",
            },
        ]
        for row in bad_rows:
            with self.subTest(row=row):
                selected = self.selected()
                selected["defeat_qualification"] = [row]
                with self.assertRaises(ValueError):
                    qualification.policy(selected)

        duplicate = self.selected()
        duplicate["defeat_qualification"].append(
            deepcopy(duplicate["defeat_qualification"][0])
        )
        with self.assertRaises(ValueError):
            qualification.policy(duplicate)

        missing_step = self.selected()
        missing_step["steps"] = []
        with self.assertRaises(ValueError):
            qualification.policy(missing_step)


if __name__ == "__main__":
    unittest.main()
