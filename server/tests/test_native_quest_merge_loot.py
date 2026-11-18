"""Exact native merge consumers preserve real complex-drop odds and inputs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server import native_quest_complex_loot as policy

ROOT = Path(__file__).resolve().parents[2]


class NativeQuestMergeLootTests(unittest.TestCase):
    def setUp(self):
        self.contract = next(
            row
            for row in policy.contracts()
            if row["id"] == "wild-native-2779-item-17851-v1"
        )
        self.context = next(
            row
            for row in json.loads(
                (
                    ROOT
                    / "server/wakfu_server/items/native_simple_item_use_contexts.json"
                ).read_text()
            )["actions"]
            if row["action_id"] == 5160
        )
        self.row = dict(
            complex_criteria=True,
            conditions=[],
            is_loot_table=False,
            native_csE=-1,
            native_csF=0,
            probability=0.2,
            quantity_max=1,
            quantity_min=1,
            reference_id=17851,
            roll_count=-1,
        )

    def test_original_three_part_native_merge_source_is_preserved(self):
        source = policy.validate_merge_consumer(self.contract, {5160: self.context})
        self.assertIs(source, self.context)
        self.assertEqual(source["action_parameters"], ["3", "17821"])
        self.assertEqual(self.contract["native_row_sha256"], policy.digest(self.row))

    def test_changed_quantity_output_map_and_source_fail_closed(self):
        for parameters, criterion in (
            (["2", "17821"], self.context["action_criterion"]),
            (["3", "17822"], self.context["action_criterion"]),
            (["3", "17821"], "GetItemQuantity(17851) >= 3 and GetInstanceId() == 711"),
        ):
            with self.subTest(parameters=parameters, criterion=criterion):
                source = dict(
                    self.context,
                    action_parameters=parameters,
                    action_criterion=criterion,
                )
                contract = deepcopy(self.contract)
                contract["consumer"]["native_source_sha256"] = policy.digest(source)
                with self.assertRaises(ValueError):
                    policy.validate_merge_consumer(contract, {5160: source})
        with self.assertRaises(ValueError):
            policy.validate_merge_consumer(
                self.contract, {5160: dict(self.context, item_ref=99)}
            )

    def test_native_twenty_percent_drop_stays_a_real_roll_and_quantity_one(self):
        from wakfu_server import combat_drops

        permission = dict(
            schema=policy.SCHEMA,
            fight_id=10,
            character_id=20,
            instance_id=30,
            route_key="source-qualified-owned-farm",
            policy_version=2,
            rows=[
                dict(
                    contract=self.contract["id"],
                    contract_sha256=policy.digest(self.contract),
                    monster_reference=2779,
                    item_reference=17851,
                    native_row_sha256=policy.digest(self.row),
                )
            ],
        )
        arguments = dict(
            monsters=[dict(actor_id=-1, reference=2779)],
            character_id=20,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={"quest_complex_loot": permission},
            catalog={"monsters": {2779: [self.row]}},
        )
        success = combat_drops.plan_player_drops(**arguments, rng=lambda upper: 0)
        failure = combat_drops.plan_player_drops(
            **arguments, rng=lambda upper: upper - 1
        )
        self.assertEqual(len(success), 1)
        self.assertEqual((success[0].success, success[0].quantity), (True, 1))
        self.assertEqual(len(failure), 1)
        self.assertFalse(failure[0].success)
        self.assertEqual(
            combat_drops.plan_player_drops(
                **dict(arguments, fight_context={}), rng=lambda upper: 0
            ),
            (),
        )

    def test_existing_frigost_and_key_contracts_remain_unchanged(self):
        others = [row for row in policy.contracts() if row["id"] != self.contract["id"]]
        self.assertEqual(len(others), 8)
        self.assertEqual(
            others[0]["native_row_sha256"],
            "67a6786da3a6bb3e4edc5e5ffe69ea034d8dfc6ec5f9517111c8c02c31ceb8c2",
        )
        self.assertEqual(
            {row["consumer"].get("kind") for row in others[1:]},
            {"native_dialogue_payment"},
        )
        self.assertEqual({row["consumer"]["quantity"] for row in others[1:]}, {10})

    def test_only_running_unfinished_merge_quest_is_eligible(self):
        for running, completed, objectives, expected in (
            ([1677], [], [], True),
            ([], [], [], False),
            ([], [1677], [3106], False),
            ([1677], [], [3106], False),
        ):
            with self.subTest(
                running=running, completed=completed, objectives=objectives
            ):
                self.assertEqual(
                    policy.contract_eligible(
                        self.contract,
                        dict(
                            running=running, completed=completed, objectives=objectives
                        ),
                    ),
                    expected,
                )
        self.assertTrue(policy.contract_eligible(policy.contracts()[0], None))


if __name__ == "__main__":
    unittest.main()
