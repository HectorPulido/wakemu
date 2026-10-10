"""Tests for fixed products and locally selected native mining candidates."""
import unittest
from unittest.mock import patch

from wakfu_server import native_catalog
from wakfu_server.mining_products import resolve, supports_action
from wakfu_server.paths import DATA_ROOT


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _DB:
    def __init__(self, policy):
        self.policy = policy
        self.queries = 0

    def execute(self, _query):
        self.queries += 1
        return _Result(None if self.policy is None else {"value": self.policy})


class _Chooser:
    def __init__(self, result):
        self.result = result
        self.seen = None

    def choices(self, candidates, *, weights, k):
        self.seen = (list(candidates), list(weights), k)
        return [self.result]


class MiningProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = native_catalog.load(DATA_ROOT / "plant-resources.json")
        cls.actions = {
            resource["resource_reference"]: [
                (stage["stage_id"], action)
                for stage in resource["stage_definitions"]
                for action in stage["actions"]
                if action["profession_id"] == 73
            ]
            for resource in cls.resources
        }
        cls.actions = {ref: rows for ref, rows in cls.actions.items() if rows}

    def test_all_seven_reference643_actions_support_only_their_stackable_candidates(
        self,
    ):
        stages = self.actions[643]
        self.assertEqual([1, 2, 3, 4, 5, 6, 7], [stage for stage, _ in stages])
        self.assertEqual(7, len(stages))
        for _stage, action in stages:
            self.assertEqual(0, action["item_reference"])
            self.assertTrue(supports_action(action))
            for reference in action["product_references"]:
                self.assertGreater(reference, 0)

    def test_fixed_product_remains_unchanged_without_reading_candidate_policy(self):
        action = next(
            action
            for _stage, action in self.actions[37]
            if action["item_reference"] > 0
        )
        db = _DB(None)
        self.assertTrue(supports_action(action))
        self.assertEqual(action["item_reference"], resolve(db, action))
        self.assertEqual(0, db.queries)

    def test_candidate_choice_uses_local_positive_weights_and_only_native_candidates(
        self,
    ):
        action = self.actions[643][0][1]
        candidates = action["product_references"]
        policy = {
            "version": 1,
            "respawn_seconds": 300,
            "product_selection": {
                "mode": "native_candidates_weighted",
                "weights": {str(candidates[0]): 3},
            },
        }
        chooser = _Chooser(candidates[1])
        db = _DB(policy)
        with patch(
            "wakfu_server.mining_products.secrets.SystemRandom", return_value=chooser
        ):
            self.assertEqual(candidates[1], resolve(db, action))
        self.assertEqual(([candidates[0], candidates[1]], [3, 1], 1), chooser.seen)

    def test_candidate_policy_is_required_and_rejects_bad_modes_weights_and_references(
        self,
    ):
        action = self.actions[643][0][1]
        good = {
            "mode": "native_candidates_weighted",
            "weights": {},
        }
        for policy in (
            None,
            {"version": 1, "respawn_seconds": 300},
            {
                "version": 1,
                "respawn_seconds": 300,
                "product_selection": {"mode": "native", "weights": {}},
            },
            {
                "version": 1,
                "respawn_seconds": 300,
                "product_selection": {"mode": good["mode"], "weights": {"999999": 1}},
            },
            {
                "version": 1,
                "respawn_seconds": 300,
                "product_selection": {
                    "mode": good["mode"],
                    "weights": {str(action["product_references"][0]): 0},
                },
            },
        ):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                resolve(_DB(policy), action)

    def test_candidate_rule_rejects_profession_criteria_terminal_and_unknown_items(
        self,
    ):
        action = dict(self.actions[643][0][1])
        for changes in (
            {"profession_id": 64},
            {"criteria": "native-gate"},
            {"raw_getters": {"cvF": 1}},
            {"product_references": [999999]},
            {"product_references": [action["product_references"][0], 999999]},
            {"product_references": [action["product_references"][0]] * 2},
        ):
            invalid = {**action, **changes}
            with self.subTest(changes=changes):
                self.assertFalse(supports_action(invalid))
                with self.assertRaises(ValueError):
                    resolve(
                        _DB(
                            {
                                "version": 1,
                                "respawn_seconds": 300,
                                "product_selection": {
                                    "mode": "native_candidates_weighted",
                                    "weights": {},
                                },
                            }
                        ),
                        invalid,
                    )
