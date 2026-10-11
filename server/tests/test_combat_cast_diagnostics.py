"""Diagnostics preserve actual once-only selection and rejected preflight facts."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_native_spell_casting import definition
from wakfu_server.combat_conditions import UnknownCondition


class CastDiagnosticsTests(unittest.TestCase):
    def record(self):
        flags = dict(
            line_of_sight=True,
            linear=False,
            free_cell=False,
            range_modifiable=True,
            path_option=False,
            diagonal=False,
            linear_path=False,
            allow_self=False,
        )
        rule = dict(
            flags, criteria="HasState(7792)", levels=[[2, 0, 0]], ranges=[[4, 9]]
        )
        return dict(
            flags,
            costs=[[2, 0, 0]],
            levels=[[4, 9, [123]]],
            categories=[],
            forbid_QI_P=False,
            cast_criterion_native_present=False,
            conditional=[rule, dict(rule, criteria="HasState(7757)")],
        )

    def test_rules_evaluated_once_and_recorded(self):
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"4813": self.record()},
        ), patch(
            "wakfu_server.combat_spell_resource_costs.catalog",
            return_value={
                "4813": dict(
                    maximum_level=1,
                    baseline=dict(resources={"2": [2, 2]}),
                    conditional=[
                        dict(criteria=c, resources={"2": [2, 2]})
                        for c in ("HasState(7792)", "HasState(7757)")
                    ],
                )
            },
        ), patch(
            "wakfu_server.combat_native_spell_casting.evaluate_condition",
            side_effect=[False, True],
        ) as evaluate:
            rule = definition(4813, 1, object(), {})
        self.assertEqual(evaluate.call_count, 2)
        self.assertEqual(
            [r["result"] for r in rule["native_casting_selection"]["evaluated_rules"]],
            ["not_matched", "matched"],
        )
        json.dumps(rule)

    def prepare(self, validation_error=None, definition_error=None):
        entry = SimpleNamespace(
            uid=9, reference=3420, level=30, caster_id=6, target_id=6
        )
        actor = SimpleNamespace(
            id=6,
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
            state_ledger=SimpleNamespace(entries=[entry]),
        )
        fight = SimpleNamespace(id=58, actors={6: actor})
        request = dict(actor_id=6, spell_uid=4813, target=(-7, 0, -1))
        rule = dict(
            costs=dict(ap=2, mp=0, wp=0),
            roots=(123,),
            minimum=4,
            maximum=9,
            line_of_sight=True,
            native_casting_selection=dict(evaluated_rules=[]),
        )
        with patch("wakfu_server.combat_cast.decode_cast", return_value=request), patch(
            "wakfu_server.combat_cast.resolve_owned_spell_action",
            return_value=(actor, 4813, 1),
        ), patch(
            "wakfu_server.combat_cast.validate_deck",
            return_value=dict(active=[4813], passive=[]),
        ), patch(
            "wakfu_server.combat_native_spell_casting.definition",
            return_value=rule,
            side_effect=definition_error,
        ), patch(
            "wakfu_server.combat_casting_range.resolve_range", return_value=rule
        ), patch(
            "wakfu_server.combat_cast._validate_target",
            side_effect=validation_error,
            return_value={},
        ):
            return prepare_spell_cast(
                b"",
                dict(breed=9, level=50),
                fight,
                1,
                b"",
                wp=6,
                line_of_sight=None,
                conditional_context=lambda *args: SimpleNamespace(actors={}),
            )

    def test_rejected_los_keeps_full_preflight_and_states(self):
        with self.assertRaisesRegex(ValueError, "twG") as caught:
            self.prepare(validation_error=ValueError("twG"))
        diagnostic = caught.exception.cast_diagnostics
        self.assertTrue(diagnostic["resolved_casting"]["line_of_sight"])
        self.assertEqual(diagnostic["actor_states"][0]["states"][0]["reference"], 3420)
        json.dumps(diagnostic)

    def test_unknown_selection_keeps_partial_diagnostics_without_false_table(self):
        error = UnknownCondition("missing authority")
        error.native_casting_selection = dict(
            selected_values=None,
            evaluated_rules=[
                dict(index=0, criterion="HasState(7792)", result="unknown")
            ],
        )
        with self.assertRaises(UnknownCondition) as caught:
            self.prepare(definition_error=error)
        diagnostic = caught.exception.cast_diagnostics
        self.assertIsNone(diagnostic["selection"]["selected_values"])
        self.assertEqual(diagnostic["conditional_rules"][0]["result"], "unknown")
        json.dumps(diagnostic)
