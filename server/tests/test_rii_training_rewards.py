"""Native Rii lesson fights must not receive ordinary monster rewards."""

import ast
from source_view import WorldSourcePath as Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.rii_training_rewards import is_owned_training

LESSONS = (
    "rii_orientation_contract",
    "rii_element_lesson_contract",
    "rii_distance_lesson_contract",
    "rii_los_lesson_contract",
    "rii_area_lesson_contract",
    "rii_movement_lesson_contract",
    "rii_states_lesson_contract",
)


class Policy:
    def __init__(self, xp=0, kamas=0):
        self.xp = xp
        self.kamas = kamas

    def __eq__(self, other):
        return (self.xp, self.kamas) == (other.xp, other.kamas)


def _fight(attribute, *, model=14, owner=7, native=True, targets=None):
    targets = targets or (
        [-8, -9, -10, -11] if attribute.endswith("area_lesson_contract") else [-8]
    )
    actors = {
        owner: SimpleNamespace(id=owner, controlled=True, team=1),
        **{
            target: SimpleNamespace(id=target, controlled=False, team=0)
            for target in targets
        },
    }
    contract = (
        {"owner": owner, "targets": targets}
        if len(targets) > 1
        else {
            "owner": owner,
            "target": targets[0],
        }
    )
    if attribute != "rii_orientation_contract" and native:
        contract["native_lesson"] = True
    return SimpleNamespace(
        id=1,
        native_fight_model=model,
        actors=actors,
        **{attribute: contract},
    )


class RiiTrainingRewardsTests(unittest.TestCase):
    def test_all_seven_official_lesson_contracts_are_reward_free(self):
        for attribute in LESSONS:
            with self.subTest(lesson=attribute):
                self.assertTrue(is_owned_training(_fight(attribute), 7))

    def test_reward_bypass_is_limited_to_the_owned_native_lesson(self):
        fight = _fight("rii_distance_lesson_contract")
        self.assertFalse(is_owned_training(fight, 8))
        self.assertFalse(
            is_owned_training(_fight("rii_distance_lesson_contract", model=2), 7)
        )
        self.assertFalse(
            is_owned_training(_fight("rii_distance_lesson_contract", native=False), 7)
        )
        self.assertFalse(
            is_owned_training(
                SimpleNamespace(native_fight_model=14, actors=fight.actors), 7
            )
        )

    def test_invalid_lesson_target_roster_fails_closed(self):
        fight = _fight("rii_area_lesson_contract", targets=[-8, -9, -10, -11])
        fight.rii_area_lesson_contract["targets"] = [-8, -9, -10, -12]
        with self.assertRaisesRegex(ValueError, "target roster"):
            is_owned_training(fight, 7)

    def test_reward_and_loot_guards_cover_shared_and_individual_paths(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        names = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {
                "shared_policy",
                "shared_loot",
                "resolve_fight_reward",
                "resolve_fight_loot",
            }
        }
        self.assertEqual(
            set(names),
            {
                "shared_policy",
                "shared_loot",
                "resolve_fight_reward",
                "resolve_fight_loot",
            },
        )

        for attribute in LESSONS:
            for name in names:
                with self.subTest(lesson=attribute, path=name):
                    fight = _fight(attribute)
                    reward_context = SimpleNamespace(
                        build_context=Mock(
                            side_effect=AssertionError("ordinary XP path used")
                        ),
                        settlement_contexts=Mock(
                            side_effect=AssertionError("ordinary XP path used")
                        ),
                        build_drop_context=Mock(
                            side_effect=AssertionError("ordinary loot path used")
                        ),
                    )
                    namespace = {
                        "fight": fight,
                        "character": {"id": 7, "account_id": 9},
                        "TEST_MONSTERS": [],
                        "combat_reward_context": reward_context,
                        "reward_policy": SimpleNamespace(
                            resolve=Mock(
                                side_effect=AssertionError("ordinary XP path used")
                            )
                        ),
                        "STORE": object(),
                        "account_id": 9,
                        "generation": "test-generation",
                        "is_developer_test_fight": lambda *_: False,
                    }
                    exec(
                        compile(
                            ast.Module(body=[names[name]], type_ignores=[]),
                            str(source),
                            "exec",
                        ),
                        namespace,
                    )
                    fake_rewards = SimpleNamespace(Policy=Policy)
                    with patch.dict(
                        sys.modules,
                        {"wakfu_server.combat_rewards": fake_rewards},
                    ):
                        if name == "resolve_fight_reward":
                            result = namespace[name](object())
                            self.assertEqual(Policy(), result)
                        elif name == "shared_policy":
                            result = namespace[name](
                                object(), {"character_id": 7}, namespace["character"]
                            )
                            self.assertEqual(Policy(), result)
                        elif name == "resolve_fight_loot":
                            self.assertEqual(
                                {"loots": [], "packets": []},
                                namespace[name](object(), Policy()),
                            )
                        else:
                            self.assertEqual(
                                {"loots": [], "packets": []},
                                namespace[name](
                                    object(), {"character_id": 7}, Policy()
                                ),
                            )

    def test_owned_guardian_skips_rewards_and_loot_in_all_four_resolvers(self):
        from wakfu_server.achievements.rii_guardian_contract import SCHEMA

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        names = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {
                "shared_policy",
                "shared_loot",
                "resolve_fight_reward",
                "resolve_fight_loot",
            }
        }
        fight = SimpleNamespace(
            id=1,
            native_fight_model=71,
            rii_guardian_contract={"schema": SCHEMA, "owner": 7, "target": -8},
            actors={
                7: SimpleNamespace(controlled=True, team=1),
                -8: SimpleNamespace(controlled=False, team=0),
            },
        )
        character = {"id": 7, "account_id": 9}
        for name in names:
            with self.subTest(path=name):
                namespace = {
                    "fight": fight,
                    "character": character,
                    "TEST_MONSTERS": [],
                    "is_developer_test_fight": lambda *_: False,
                    "STORE": object(),
                    "account_id": 9,
                    "generation": "test-generation",
                    "frozen_contexts": {},
                }
                exec(
                    compile(
                        ast.Module(body=[names[name]], type_ignores=[]),
                        str(source),
                        "exec",
                    ),
                    namespace,
                )
                fake_rewards = SimpleNamespace(Policy=Policy)
                with patch.dict(
                    sys.modules, {"wakfu_server.combat_rewards": fake_rewards}
                ):
                    if name == "resolve_fight_reward":
                        result = namespace[name](object())
                        self.assertEqual(Policy(), result)
                    elif name == "shared_policy":
                        result = namespace[name](
                            object(), {"character_id": 7}, character
                        )
                        self.assertEqual(Policy(), result)
                    elif name == "resolve_fight_loot":
                        self.assertEqual(
                            {"loots": [], "packets": []},
                            namespace[name](object(), Policy()),
                        )
                    else:
                        self.assertEqual(
                            {"loots": [], "packets": []},
                            namespace[name](object(), {"character_id": 7}, Policy()),
                        )


if __name__ == "__main__":
    unittest.main()
