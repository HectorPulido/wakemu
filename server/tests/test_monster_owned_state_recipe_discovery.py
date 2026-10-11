"""Preparation discovery proposes actual owned native state casts only."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import (
    discover_owned_state_recipes,
    simple_required_caster_states,
    recovery_owned_state_recipes,
)


class OwnedStateRecipeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.abilities = [{"spell_id": 1583, "spell_level": 1}]
        self.effect = dict(
            effect_class=304,
            variant=0,
            criteria="",
            parameters=[336.0, 0.0, 1.0, 0.0, -1.0, 0.0],
            native_target_selector={"mask": 1},
        )
        self.document = {
            "spells": {"1583": {"levels": [[0, 0, [17602]]]}},
            "effects": {"17602": self.effect},
        }

    def test_discovers_same_turn_and_next_turn_real_owned_casts(self):
        recipes = discover_owned_state_recipes(self.abilities, [336], self.document)
        self.assertEqual([r["actions"][0]["next_turn"] for r in recipes], [False, True])
        self.assertTrue(all(r["actions"][0]["spell_id"] == 1583 for r in recipes))
        self.assertTrue(all(r["discovered_required_states"] == [336] for r in recipes))

    def test_never_proposes_unowned_or_unrelated_state_producer(self):
        self.assertEqual(discover_owned_state_recipes([], [336], self.document), [])
        self.assertEqual(
            discover_owned_state_recipes(self.abilities, [337], self.document), []
        )

    def test_rejects_nonconstant_conditional_or_other_target_roots(self):
        for key, value in [
            ("parameters", [336.0, 1.0]),
            ("criteria", "HasState(1,caster)"),
            ("native_target_selector", {"mask": 2}),
            ("effect_class", 321),
        ]:
            with self.subTest(key=key):
                original = self.effect[key]
                self.effect[key] = value
                self.assertEqual(
                    discover_owned_state_recipes(self.abilities, [336], self.document),
                    [],
                )
                self.effect[key] = original

    def test_budget_is_finite(self):
        self.assertEqual(
            len(
                discover_owned_state_recipes(
                    self.abilities, [336], self.document, limit=1
                )
            ),
            1,
        )

    def test_discovers_nested_unconditional_native_groups_and_terminates_cycles(self):
        self.document["spells"]["1583"]["levels"] = [[0, 0, [10]]]
        self.document["effects"]["10"] = dict(
            effect_class=330, criteria="", children=[11]
        )
        self.document["effects"]["11"] = dict(
            effect_class=349, criteria="", children=[10, 17602]
        )
        self.assertEqual(
            len(discover_owned_state_recipes(self.abilities, [336], self.document)), 2
        )
        self.document["effects"]["11"]["criteria"] = "HasState(99, 'caster')"
        self.assertEqual(
            discover_owned_state_recipes(self.abilities, [336], self.document), []
        )


class ConservativeCasterStateCriterionTests(unittest.TestCase):
    def test_exact_positive_native_expression(self):
        self.assertEqual(
            simple_required_caster_states('HasState(336, "caster")'), [336]
        )
        self.assertEqual(
            simple_required_caster_states(" HasState( 336, 'caster') "), [336]
        )

    def test_negation_composition_other_actor_and_unknown_are_not_inferred(self):
        for raw in [
            None,
            "",
            '!HasState(336, "caster")',
            'Not(HasState(336, "caster"))',
            'HasState(336, "target")',
            'HasState(336, "caster")|True',
            'HasState(-1, "caster")',
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(simple_required_caster_states(raw), [])
                self.assertEqual(recovery_owned_state_recipes(872, 75, 1582, raw), [])

    def test_positive_native_and_extracts_only_necessary_caster_states(self):
        self.assertEqual(
            simple_required_caster_states('HasState(546, "caster")\r\nand IsEnnemy()'),
            [546],
        )
        self.assertEqual(
            simple_required_caster_states(
                'HasState(336, "caster") and HasState(337, "caster")'
            ),
            [336, 337],
        )
        self.assertEqual(
            simple_required_caster_states('SomeUnknown(HasState(336, "caster"))'), []
        )
        self.assertEqual(
            simple_required_caster_states('HasState(336, "caster") == False'), []
        )

    def test_target_spell_cannot_be_its_own_preparation(self):
        from unittest.mock import patch
        import types

        modules = {
            "wakfu_server.monsters": types.SimpleNamespace(
                native_abilities=lambda *args: [{"spell_id": 1583, "spell_level": 1}]
            ),
            "wakfu_server.combat_npc_attack": types.SimpleNamespace(
                npc_spell_catalog=lambda: {}
            ),
        }
        with patch.dict(sys.modules, modules), patch(
            "monster_pending_scenarios.discover_owned_state_recipes", return_value=[]
        ) as discover:
            recovery_owned_state_recipes(872, 75, 1583, 'HasState(336, "caster")')
        self.assertEqual(discover.call_args.args[0], [])
        self.assertEqual(discover.call_args.kwargs["limit"], 4)


if __name__ == "__main__":
    unittest.main()
