"""Native support intent is bounded and never grants execution authority."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge.jondo_capabilities import empty_aim_cells, project_support


class NativeSupportTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=1, team=0, effective_level=5, direction=1, position=(0, 0, 0)
        )
        cells = {(x, y, 0): x * 3 + y for x in range(5) for y in range(3)}
        edges = [
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        ]
        fight = SimpleNamespace(actors={1: actor}, edges=edges)
        actors = [
            dict(id=1, team=0, cell=cells[(0, 0, 0)], hp=100),
            dict(id=2, team=1, cell=cells[(4, 2, 0)], hp=100),
        ]
        native = SimpleNamespace(
            characteristics={"LEADERSHIP": 3},
            summon_count=2,
            summon_counts_by_breed={123: 1},
            summon_counts_complete=True,
        )
        context = SimpleNamespace(actors={"caster": native})
        return fight, actor, cells, actors, context

    def test_actual_larva_summon_has_typed_native_recipe_and_empty_aims(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        table, index = native_casting_table(4625, 5)
        before = deepcopy(vars(fight)), deepcopy(vars(actor)), deepcopy(actors)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            5,
            fight=fight,
            actor=actor,
            rule=dict(maximum=5),
            context=context,
            indices=cells,
            actors=actors,
        )
        self.assertIn("summon", result["intents"])
        self.assertIn("emptyCell", result["aimKinds"])
        self.assertTrue(result["summons"])
        self.assertGreater(result["summons"][0]["reference"], 0)
        self.assertLessEqual(len(result["candidateCells"]), 12)
        self.assertEqual(result["facts"]["leadership"], 3)
        self.assertEqual(result["facts"]["summonCount"], 2)
        self.assertEqual(result["facts"]["summonCountsByBreed"], {"123": 1})
        self.assertEqual((vars(fight), vars(actor), actors), before)

    def test_zero_range_native_wave_keeps_self_aim(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        actor.effective_level = 50
        table, index = native_casting_table(2859, 50)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            50,
            fight=fight,
            actor=actor,
            rule=dict(maximum=0),
            context=context,
            indices=cells,
            actors=actors,
        )
        self.assertIn("summon", result["intents"])
        self.assertEqual(result["aimKinds"], ["self"])
        self.assertEqual(result["candidateCells"], [])

    def test_actual_stat_mechanics_retain_native_stat_sign_and_uncertainty(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        table, index = native_casting_table(4001, 52)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            52,
            fight=fight,
            actor=actor,
            rule=dict(maximum=8),
            context=context,
            indices=cells,
            actors=actors,
        )
        facts = {(row["statName"], row["kind"]) for row in result["effects"]}
        self.assertIn(("DMG_IN_PERCENT", "stat_gain"), facts)
        self.assertIn(("RES_WATER_PERCENT", "stat_loss"), facts)
        self.assertTrue(
            all("benefit" in row and "probability" in row for row in result["effects"])
        )

    def test_missing_typed_summon_authority_stays_unknown(self):
        fight, actor, cells, actors, _ = self.fixture()
        with patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value={"effects": {}},
        ):
            result = project_support(
                SimpleNamespace(effects={}),
                [],
                1,
                fight=fight,
                actor=actor,
                indices=cells,
                actors=actors,
            )
        self.assertIsNone(result["facts"]["leadership"])
        self.assertIsNone(result["facts"]["summonCount"])
        self.assertFalse(result["facts"]["summonCountsComplete"])
        self.assertNotIn("capacityAvailable", result["facts"])

    def test_empty_aims_use_observed_footprints_and_soft_corridor_preference(self):
        fight, actor, cells, actors, _ = self.fixture()
        ally = dict(
            id=3,
            team=0,
            cell=cells[(1, 1, 0)],
            hp=100,
            extraCells=[cells[(1, 0, 0)], cells[(1, 2, 0)]],
        )
        actors.append(ally)
        # A native directed corridor leaves this ally only one available exit.
        fight.edges = [(a, b) for a, b in fight.edges if a != (1, 1, 0)]
        fight.edges.append(((1, 1, 0), (2, 1, 0)))
        result = empty_aim_cells(fight, actor, cells, actors)
        self.assertLessEqual(len(result), 12)
        self.assertFalse(set(result).intersection({ally["cell"], *ally["extraCells"]}))
        if cells[(2, 1, 0)] in result:
            self.assertNotEqual(result[0], cells[(2, 1, 0)])

    def test_state_benefit_is_not_assumed_from_application(self):
        from wakfu_ai.bridge.jondo_capabilities import _benefit

        self.assertEqual(_benefit(["state", "unknown"]), "unknown")
        self.assertEqual(_benefit(["buff", "damage"]), "unknown")
        self.assertEqual(_benefit(["buff"]), "beneficial")
        self.assertEqual(_benefit(["damage"]), "harmful")

    def test_parent_criteria_and_probability_are_not_guaranteed_stat_benefit(self):
        fight, actor, cells, actors, context = self.fixture()
        base = dict(
            variant=0,
            minimum_level=0,
            maximum_level=100,
            parameters=[10, 0],
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            native_target_selector={"class": "fcE", "mask": 128},
            area_class="anD",
            area_native="point",
            children=(),
            criteria="",
        )
        parent = dict(
            base,
            effect_class=330,
            children=[2],
            criteria='NativeTargetCondition("target")',
        )
        child = dict(base, effect_class=120, probability_base=50)
        compiled = SimpleNamespace(effects={"1": parent, "2": child})
        registry = {
            "effects": {
                "120": dict(
                    fixed_stat_id=20,
                    fixed_stat_name="DMG_IN_PERCENT",
                    operation="gain_current",
                )
            }
        }
        with patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value=registry,
        ):
            result = project_support(
                compiled,
                [1],
                5,
                fight=fight,
                actor=actor,
                indices=cells,
                actors=actors,
                context=context,
            )
        row = result["effects"][0]
        self.assertEqual(row["probability"], 50)
        self.assertTrue(row["conditional"])
        self.assertEqual(row["confidence"], "conditional")
        self.assertEqual(row["targets"], ["ally"])
        self.assertEqual(row["fixedCells"], [[0, 0]])
        self.assertEqual(result["aimKinds"], ["ally"])

    def test_actual_native_state_apply_and_decurse_do_not_assume_positive_states(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        actors[1]["states"] = [dict(reference=2490, level=0)]
        table, index = native_casting_table(4121, 60)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            60,
            fight=fight,
            actor=actor,
            rule=dict(maximum=8),
            context=context,
            indices=cells,
            actors=actors,
        )
        self.assertEqual(
            {row["kind"] for row in result["effects"]}, {"add_state", "remove_state"}
        )
        removed = next(
            row for row in result["effects"] if row["kind"] == "remove_state"
        )
        self.assertEqual(removed["stateId"], 2490)
        self.assertEqual(removed["presentOn"], [2])
        self.assertEqual(removed["benefit"], "unknown")

    def test_native_value_transfer_does_not_claim_child_base_as_actual_amount(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        table, index = native_casting_table(4001, 52)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            52,
            fight=fight,
            actor=actor,
            context=context,
            indices=cells,
            actors=actors,
        )
        gain = next(row for row in result["effects"] if row["kind"] == "stat_gain")
        self.assertFalse(gain["amountKnown"])
        self.assertEqual(gain["valueBasis"], "native_runner_callback")
        self.assertTrue(gain["conditional"])
        loss = next(row for row in result["effects"] if row["kind"] == "stat_loss")
        self.assertTrue(loss["amountKnown"])

    def state_increase_fixture(
        self,
        *,
        current=1,
        requested=1,
        maximum=10,
        additive=True,
        protected=False,
        instance_protected=None
    ):
        from wakfu_ai.bridge.jondo_capabilities import state_increases

        entry = SimpleNamespace(
            reference=123, level=current, protected=instance_protected
        )
        target = SimpleNamespace(state_ledger=SimpleNamespace(entries=[entry]))
        fight = SimpleNamespace(actors={20: target})
        catalog = {
            "states": {
                "123": dict(
                    maximum_level=maximum,
                    additive=additive,
                    replace=True,
                    refresh=False,
                    protected=protected,
                )
            }
        }
        return state_increases(fight, [dict(id=20)], catalog, 123, requested)

    def test_existing_zero_level_state_does_not_prove_a_new_benefit(self):
        self.assertEqual(
            self.state_increase_fixture(current=0, requested=0, additive=False),
            dict(increaseOn=[], increaseTo={}),
        )

    def test_native_additive_level_one_can_increase_to_two(self):
        self.assertEqual(
            self.state_increase_fixture(), dict(increaseOn=[20], increaseTo={"20": 2})
        )

    def test_native_protected_nonadditive_state_cannot_be_replaced(self):
        self.assertEqual(
            self.state_increase_fixture(additive=False, protected=True, requested=2),
            dict(increaseOn=[], increaseTo={}),
        )

    def test_native_state_cap_does_not_prove_increased_benefit(self):
        self.assertEqual(
            self.state_increase_fixture(current=10, maximum=10),
            dict(increaseOn=[], increaseTo={}),
        )

    def test_actual_instance_protection_overrides_default_state_definition(self):
        self.assertEqual(
            self.state_increase_fixture(
                additive=False, requested=2, instance_protected=True
            ),
            dict(increaseOn=[], increaseTo={}),
        )

    def test_native_self_selector_without_area_requires_a_legal_cast_anchor(self):
        fight, actor, cells, actors, context = self.fixture()
        effect = dict(
            effect_class=120,
            variant=0,
            minimum_level=0,
            maximum_level=100,
            parameters=[10, 0],
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            native_target_selector={"class": "fcE", "mask": 2},
            area_class="anA",
            area_native="empty",
            children=(),
            criteria="",
            target_masks=[[], [], [], [], [], [], [123]],
        )
        registry = {
            "effects": {
                "120": dict(
                    fixed_stat_id=20,
                    fixed_stat_name="DMG_IN_PERCENT",
                    operation="gain_current",
                )
            }
        }
        with patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value=registry,
        ):
            result = project_support(
                SimpleNamespace(effects={"1": effect}),
                [1],
                5,
                fight=fight,
                actor=actor,
                context=context,
                indices=cells,
                actors=actors,
                rule=dict(minimum=1, maximum=3),
            )
        self.assertTrue(result["castAnchorRequired"])
        self.assertIn("emptyCell", result["aimKinds"])
        self.assertFalse(result["effects"][0]["inArea"])
        self.assertEqual(result["effects"][0]["fixedCells"], [])
        self.assertFalse(result["effects"][0]["triggered"])

    def test_native_removal_only_mask_does_not_defer_fresh_state_effect(self):
        fight, actor, cells, actors, context = self.fixture()
        effect = dict(
            effect_class=120,
            variant=0,
            minimum_level=0,
            maximum_level=100,
            parameters=[10, 0],
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            native_target_selector={"class": "fcE", "mask": 3},
            area_class="anD",
            area_native="point",
            children=(),
            criteria="",
            target_masks=[[], [], [123], [], [], [], []],
        )
        registry = {
            "effects": {
                "120": dict(
                    fixed_stat_id=20,
                    fixed_stat_name="DMG_IN_PERCENT",
                    operation="gain_current",
                )
            }
        }
        with patch(
            "wakfu_server.combat_static_catalogs.characteristic_registry",
            return_value=registry,
        ):
            result = project_support(
                SimpleNamespace(effects={"1": effect}),
                [1],
                5,
                fight=fight,
                actor=actor,
                context=context,
                indices=cells,
                actors=actors,
            )
        self.assertFalse(result["effects"][0]["triggered"])

    def test_request_local_empty_aim_reuse_is_fresh_for_next_snapshot(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_ai.bridge import jondo_capabilities as module

        fight, actor, cells, actors, context = self.fixture()
        table, index = native_casting_table(4625, 5)
        cache = {}
        with patch.object(
            module, "empty_aim_cells", wraps=module.empty_aim_cells
        ) as work:
            arguments = dict(
                fight=fight,
                actor=actor,
                rule=dict(minimum=2, maximum=5),
                context=context,
                indices=cells,
                actors=actors,
            )
            first = project_support(
                npc_runtime_catalog(),
                table["levels"][index][2],
                5,
                request_cache=cache,
                **arguments
            )
            second = project_support(
                npc_runtime_catalog(),
                table["levels"][index][2],
                5,
                request_cache=cache,
                **arguments
            )
            self.assertEqual(work.call_count, 1)
            self.assertEqual(first["candidateCells"], second["candidateCells"])
            first["candidateCells"].clear()
            self.assertTrue(second["candidateCells"])
            project_support(
                npc_runtime_catalog(),
                table["levels"][index][2],
                5,
                request_cache={},
                **arguments
            )
            self.assertEqual(work.call_count, 2)

    def test_state_increase_cache_does_not_alias_results_or_survive_a_new_snapshot(
        self,
    ):
        from wakfu_ai.bridge.jondo_capabilities import state_increases

        entry = SimpleNamespace(reference=123, level=1, protected=None)
        target = SimpleNamespace(state_ledger=SimpleNamespace(entries=[entry]))
        fight = SimpleNamespace(actors={20: target})
        catalog = {
            "states": {
                "123": dict(
                    maximum_level=10,
                    additive=True,
                    replace=True,
                    refresh=False,
                    protected=False,
                )
            }
        }
        cache = {}
        first = state_increases(
            fight, [dict(id=20)], catalog, 123, 1, request_cache=cache
        )
        first["increaseOn"].clear()
        first["increaseTo"].clear()
        self.assertEqual(
            state_increases(fight, [dict(id=20)], catalog, 123, 1, request_cache=cache),
            dict(increaseOn=[20], increaseTo={"20": 2}),
        )
        entry.level = 10
        self.assertEqual(
            state_increases(fight, [dict(id=20)], catalog, 123, 1, request_cache={}),
            dict(increaseOn=[], increaseTo={}),
        )

    def test_native_state_callbacks_are_not_extra_owned_cast_effects(self):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        fight, actor, cells, actors, context = self.fixture()
        table, index = native_casting_table(638, 83)
        result = project_support(
            npc_runtime_catalog(),
            table["levels"][index][2],
            83,
            fight=fight,
            actor=actor,
            context=context,
            indices=cells,
            actors=actors,
        )
        self.assertTrue(any(row["kind"] == "add_state" for row in result["effects"]))
        self.assertFalse(
            any(row["kind"] == "remove_state" for row in result["effects"])
        )
        self.assertFalse(any(row["fromState"] for row in result["effects"]))


if __name__ == "__main__":
    unittest.main()
