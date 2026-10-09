import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_casting_context import (
    use_gate_effect,
    NativeOwnedCastingContext,
    enemy_cell_affiliations,
)
from wakfu_server.combat_casting_eligibility import native_pv_cell_distance
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_registry import NativeQIRegistry


class NativeUseGateConditionsTests(unittest.TestCase):
    def test_empty_signature_and_strict_callback_type(self):
        self.assertTrue(
            evaluate_condition(
                "UseGateEffect()",
                ConditionContext({}, use_gate_effect_query=lambda: True),
            )
        )
        self.assertFalse(
            evaluate_condition(
                "UseGateEffect()",
                ConditionContext({}, use_gate_effect_query=lambda: False),
            )
        )
        for text in ("UseGateEffect(1)", "UseGateEffect() == 0"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(
                    text, ConditionContext({}, use_gate_effect_query=lambda: True)
                )
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "UseGateEffect()", ConditionContext({}, use_gate_effect_query=lambda: 0)
            )

    def test_unavailable_context_is_not_native_false(self):
        with self.assertRaisesRegex(UnknownCondition, "authority"):
            evaluate_condition("UseGateEffect()", ConditionContext({}))

    def test_actual_non_runner_and_state_container_are_false(self):
        invocation = EffectInvocation(1, 20, 7, None, (0, 0, 0))
        self.assertFalse(use_gate_effect(None, None, {}, None, invocation))
        state = EffectInvocation(1, 20, 7, None, (0, 0, 0), state_uid=9)
        self.assertFalse(use_gate_effect(None, None, {}, {}, state))

    def test_pv_distance_includes_signed_radius_and_wrapping(self):
        self.assertEqual(native_pv_cell_distance((0, 0, 0), 1, (1, 1, 99)), 0)
        self.assertEqual(native_pv_cell_distance((0, 0, 0), -1, (0, 0, 0)), 2)
        self.assertEqual(native_pv_cell_distance((0, 0, 0), 0, (-(1 << 31), 0, 0)), 0)

    def context(self):
        source = SimpleNamespace(
            id=7,
            team=0,
            position=(0, 0, 0),
            physical_radius=0,
            native_obstacle_id=0,
            hp=100,
        )
        target = SimpleNamespace(
            id=8,
            team=1,
            position=(1, 0, 0),
            physical_radius=0,
            native_obstacle_id=1,
            hp=100,
        )
        fight = SimpleNamespace(
            actors={7: source, 8: target},
            native_effect_areas={},
            phase="active",
            current=source,
            native_qi_movement_override=False,
            native_qi_ignored_slots=[],
        )
        arena = dict(x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0])
        slots = [None] * 127
        for slot, actor in enumerate((source, target)):
            slots[slot] = dict(
                identity=["actor", actor.id],
                position=list(actor.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        registry = NativeQIRegistry(arena, slots)
        registry.capture_fresh_cell_topology((0, 1))
        fight.native_qi_snapshot = arena
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        adapter = SimpleNamespace(
            _actor=lambda preview, actor: SimpleNamespace(targeting={"is_eGj": True})
        )
        invocation = SimpleNamespace(caster_id=7, target_id=None, cell=(1, 0, 0))
        rule = dict(roots=(), minimum=1, maximum=4, cast_criterion_native_present=True)
        context = NativeOwnedCastingContext(
            adapter, fight, {}, invocation, ConditionContext({}), rule
        )
        context._registry = registry
        return context, fight

    def test_target_fighter_comes_from_qi_slots_not_requested_recipient(self):
        context, _ = self.context()
        context.resolve_target_fighter()
        self.assertEqual(context.target.id, 8)
        self.assertTrue(context.qi_g())

    def test_free_cell_respects_actual_override_and_exclusions(self):
        context, fight = self.context()
        fight.native_qi_ignored_slots = [1]
        self.assertFalse(context.qi_g())
        fight.native_qi_ignored_slots = []
        fight.native_qi_movement_override = True
        self.assertFalse(context.qi_g())

    def test_admissible_pvs_use_captured_native_order_and_ignore_z(self):
        context, fight = self.context()
        initialize_global_pv_collections(fight, (7, 8))
        fight.actors[8].position = (1, 0, 9)
        self.assertEqual(context.criterion_objects(), (("actor", 8),))

    def test_fkx_null_is_distinct_from_effect_area(self):
        context, _ = self.context()
        roots = {
            "1": dict(native_casting_collision_area=None, native_selector_present=True)
        }
        with patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": roots},
        ):
            self.assertFalse(context.root_has_shape(1))
            self.assertTrue(context.root_has_selector(1))
            with self.assertRaises(UnknownCondition):
                context.root_has_shape(2)

    def test_casting_group_selector_uses_native_root_without_executable_tree(self):
        context, _ = self.context()
        context.resolve_target_fighter()
        context.target.team = context.source.team
        context.adapter._actor = lambda preview, actor: SimpleNamespace(
            targeting={
                "is_eGj": True,
                "is_amO": True,
                "bEe": True,
                "is_Qq": False,
                "UNTARGETTABLE_BY_OTHER": False,
            }
        )
        self.assertEqual(
            context.root_record(327650)["native_target_selector"],
            {"class": "fcE", "mask": 5},
        )
        # This group root exists in the original casting container, independently
        # from the effect dispatcher closure used to execute its descendants.
        self.assertTrue(context.root_selector_accepts(327650))

    def test_casting_only_table_does_not_require_ap_modifiers(self):
        from wakfu_server.combat_native_spell_casting import definition

        record = dict(
            costs=[[3, 0, 0]],
            levels=[[1, 4, []]],
            conditional=[],
            categories=[3],
            forbid_QI_P=False,
            cast_criterion_native_present=False,
            cast_criterion_raw=None,
        )
        for field in (
            "line_of_sight",
            "linear",
            "free_cell",
            "range_modifiable",
            "path_option",
            "diagonal",
            "linear_path",
            "allow_self",
        ):
            record[field] = False
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"1": record},
        ):
            rule = definition(1, 1, ConditionContext({}), None, calculate_costs=False)
            self.assertIsNone(rule["costs"])
            self.assertEqual((rule["minimum"], rule["maximum"]), (1, 4))
            with self.assertRaises(UnknownCondition):
                definition(1, 1, ConditionContext({}), None)

    def test_normal_cast_consumes_native_decision_and_keeps_usage_separate(self):
        from wakfu_server.combat_cast import _validate_target

        request = dict(actor_id=7, spell_uid=1, target=(1, 1, 0))
        actor = SimpleNamespace(ap=4, mp=3)
        costs = dict(ap=3, mp=0, wp=0)
        context = ConditionContext(
            {},
            native_casting_query=lambda rule, spell, level: dict(
                result="twD", aligned=True, target_id=8
            ),
        )
        # An exact native decision can accept a diagonal without a walkable-set
        # approximation. Usage remains an independent validated authority.
        with patch(
            "wakfu_server.combat_spell_usage.validate_usage", return_value={}
        ) as usage:
            plan = _validate_target(
                request,
                actor,
                SimpleNamespace(walkable=set()),
                1,
                costs,
                {},
                (12,),
                20,
                None,
                1,
                context,
            )
            self.assertEqual(plan["target_id"], 8)
            usage.assert_called_once()

    def test_normal_cast_rejects_missing_producer_and_failed_alignment(self):
        from wakfu_server.combat_cast import _validate_target

        args = (
            dict(target=(1, 1, 0)),
            SimpleNamespace(ap=4, mp=3),
            SimpleNamespace(),
            1,
            dict(ap=3, mp=0, wp=0),
            {},
            (),
            20,
            None,
            1,
        )
        with self.assertRaisesRegex(ValueError, "producer"):
            _validate_target(*args, ConditionContext({}))
        context = ConditionContext(
            {},
            native_casting_query=lambda *args: dict(
                result="twD", aligned=False, target_id=None
            ),
        )
        with self.assertRaisesRegex(ValueError, "alignment/path"):
            _validate_target(*args, context)

    def test_enemy_cell_uses_fighter_footprint_then_first_qk(self):
        context, fight = self.context()
        initialize_global_pv_collections(fight, (7, 8))
        self.assertEqual(
            enemy_cell_affiliations(context.adapter, fight, 7, (1, 0, 0)), (1,)
        )
        self.assertEqual(
            enemy_cell_affiliations(context.adapter, fight, 7, (2, 0, 0)), ()
        )
        # The full-XYZ footprint test fails, then QI.V's XY actor still proves enemy.
        self.assertEqual(
            enemy_cell_affiliations(context.adapter, fight, 7, (1, 0, 9)), (1,)
        )

    def test_actual_null_and_other_enemy_targets_are_distinct(self):
        source = ConditionActor(fight_affiliation=0)
        self.assertTrue(
            evaluate_condition(
                "IsEnemy()", ConditionContext({}, enemy_target_kind="null")
            )
        )
        self.assertFalse(
            evaluate_condition(
                "IsEnemy()",
                ConditionContext({"caster": source}, enemy_target_kind="other"),
            )
        )
        self.assertTrue(
            evaluate_condition(
                "IsEnemy()",
                ConditionContext(
                    {"caster": source},
                    enemy_target_kind="cell",
                    enemy_cell_affiliations_query=lambda: (1,),
                ),
            )
        )

    def test_proven_null_cast_cell_alias_has_no_fight_property(self):
        self.assertFalse(
            evaluate_condition(
                'HasFightProperty("target", 21)',
                ConditionContext({}, null_actor_aliases=frozenset({"target"})),
            )
        )
        context = ConditionContext(
            {},
            target_cell_is_explicit=True,
            native_cell_target_fighter_resolved=True,
            null_actor_aliases=frozenset({"target"}),
        )
        self.assertTrue(
            evaluate_condition('GetCharacterDirection("target") == -1', context)
        )


if __name__ == "__main__":
    unittest.main()
