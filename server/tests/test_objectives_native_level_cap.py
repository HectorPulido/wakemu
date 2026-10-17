"""Native245 player eligibility and immutable historical reward contracts."""
import copy
import unittest
from unittest.mock import patch
from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from wakfu_server.objectives import catalog, content, pvp, reward_policies
from wakfu_server.reward_policy import _normalize_context
from wakfu_server.npc_objective_facts import evaluate


def policy(maximum):
    return {
        "bands": [
            {
                "minimum": 1,
                "maximum": maximum,
                "rewards": [{"kind": "kamas", "amount": 17}],
            }
        ]
    }


class ObjectivesNativeLevelCapTests(unittest.TestCase):
    def test_native245_definition_and_pvp_boundaries_preserve_strict_invalids(self):
        self.assertEqual(MAX_CHARACTER_LEVEL, 245)
        definition = content._definition(
            "native-cap-test",
            "Native cap",
            "Native cap",
            "achievement",
            "fixture_event",
            {},
            1,
            "fixture",
        )
        self.assertEqual(definition["level_range"], {"minimum": 1, "maximum": 245})
        self.assertEqual(
            catalog.validate_definition(definition)["level_range"],
            definition["level_range"],
        )
        absolute = {"type": "absolute", "maximum_difference": 10}
        self.assertTrue(pvp.compatible_levels(absolute, 235, 245))
        self.assertFalse(pvp.compatible_levels(absolute, 234, 245))
        for invalid in (0, True, 246):
            self.assertFalse(pvp.compatible_levels(absolute, invalid, 245))
            malformed = copy.deepcopy(definition)
            malformed["level_range"]["maximum"] = invalid
            with self.assertRaises(ValueError):
                catalog.validate_definition(malformed)
        self.assertTrue(evaluate('GetRealLevel("caster") >= 245', {"level": 245}, {}))
        self.assertFalse(evaluate('GetRealLevel("caster") >= 245', {"level": 244}, {}))
        self.assertFalse(evaluate('GetRealLevel("caster") >= 245', {"level": 246}, {}))

    def test_terminal_reward_band_extends_without_rewriting_old_reward_amounts(self):
        self.assertEqual(content.BANDS[-1], (200, MAX_CHARACTER_LEVEL))
        current = policy(MAX_CHARACTER_LEVEL)
        self.assertEqual(reward_policies.validate_policy(current), current)
        with patch.object(reward_policies, "native_items", return_value={}):
            self.assertEqual(
                reward_policies.expand(None, {"policy": current}, 245),
                [{"kind": "kamas", "amount": 17}],
            )
            self.assertEqual(
                reward_policies.expand(None, {"policy": current}, 200),
                [{"kind": "kamas", "amount": 17}],
            )
        for invalid in (True, 0, 246):
            with self.assertRaises(ValueError):
                reward_policies.expand(None, {"policy": current}, invalid)

    def test_pending_historical200_policy_expands_only_for_original_supported_level(
        self,
    ):
        historical = policy(200)
        before = copy.deepcopy(historical)
        with self.assertRaises(ValueError):
            reward_policies.validate_policy(historical)
        with patch.object(reward_policies, "native_items", return_value={}):
            self.assertEqual(
                reward_policies.expand(None, {"policy": historical}, 200),
                [{"kind": "kamas", "amount": 17}],
            )
            with self.assertRaisesRegex(ValueError, "Frozen reward policy"):
                reward_policies.expand(None, {"policy": historical}, 245)
        self.assertEqual(historical, before)
        with self.assertRaises(ValueError):
            reward_policies.validate_policy(policy(199), allow_historical_200=True)

    def test_winning_player245_and_native_npc_levels_remain_distinct_domains(self):
        context = {
            "winner_team": 0,
            "winners": [
                {
                    "level": 245,
                    "player": True,
                    "eligible": True,
                    "character_id": 7,
                    "wisdom": 0,
                },
                {
                    "level": 300,
                    "player": False,
                    "eligible": False,
                    "character_id": None,
                    "wisdom": 0,
                },
            ],
            "losers": [{"level": 300, "monster_reference": 1}],
            "challenge_percent": 0,
            "star_percent": 0,
        }
        self.assertEqual(
            [row["level"] for row in _normalize_context(context, 7)["winners"]],
            [245, 300],
        )
        for invalid in (True, 0, 246):
            changed = copy.deepcopy(context)
            changed["winners"][0]["level"] = invalid
            with self.assertRaises(ValueError):
                _normalize_context(changed, 7)
        changed = copy.deepcopy(context)
        changed["winners"][0]["wisdom"] = 201
        with self.assertRaises(ValueError):
            _normalize_context(changed, 7)

    def test_existing200_progression_milestones_remain200(self):
        from wakfu_server.objectives import progression

        definitions = {row["key"]: row for row in progression.definitions()}
        old = definitions["progression-v1.characters.level.200.count.2"]
        self.assertEqual(old["objectives"][0]["filters"]["minimum_level"], 200)
        latest = definitions["progression-v1.characters.level.245"]
        self.assertNotIn("current cap is 200", latest["description"])
