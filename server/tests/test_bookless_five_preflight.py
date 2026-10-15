"""Catalog-free preflight for the five bookless native scenario contracts.

These assertions validate native criterion/timeline primitives and queue
integrity; they are not encounter execution or spell activation evidence.
"""

import json
import ast
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace as NS

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)


REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / ".runtime" / "monster-all-boss-tests-20261014"
sys.path.insert(0, str(RUNTIME))
from prepare_bookless_five_runner import prepare  # noqa: E402


def isolated_native_state_timeline():
    """Compile only the exact source function to avoid catalog-heavy imports."""
    source_path = (
        REPO / "server" / "wakfu_server" / "combat" / "combat_native_timing_context.py"
    )
    module = ast.parse(source_path.read_text())
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "native_state_timeline"
    )

    def state_timeline(
        round_number, current_actor_id, current_actor_index, clock_actor_index, phase
    ):
        return NS(
            round_number=round_number,
            current_actor_id=current_actor_id,
            current_actor_index=current_actor_index,
            clock_actor_index=clock_actor_index,
            phase=phase,
        )

    namespace = {"StateTimeline": state_timeline}
    isolated = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(isolated, str(source_path), "exec"), namespace)
    return namespace["native_state_timeline"]


class BooklessFivePreflightTests(unittest.TestCase):
    def test_queue_preparation_preserves_all_22_unrun_contracts(self):
        result = prepare()
        self.assertEqual(result["scenario_count"], 22)
        self.assertEqual(result["readiness"], "PREPARED_NOT_EXECUTED")
        self.assertEqual(result["execution_claims"], 0)
        self.assertFalse(result["book_grant"])
        self.assertFalse(result["resource_gift"])
        self.assertFalse(result["owned_806_denominator_changed"])
        self.assertEqual(
            result["scenario_counts_by_reference"],
            {"4875": 4, "4876": 4, "5114": 6, "5801": 4, "5802": 4},
        )

    def test_registered_property_114_actor_has_no_timeline_slot(self):
        first = NS(id=7, hp=5000, turn_count=1)
        second = NS(id=-7, hp=100, turn_count=1)
        passive = NS(id=4875, hp=5000, turn_count=1)
        fight = NS(
            phase="active",
            current=first,
            actors={7: first, -7: second, 4875: passive},
            order=[7, -7],
            turn_index=0,
            native_summon_registrations={
                4875: {"actor_id": 4875, "fight_properties": (3, 11, 51, 114)}
            },
            _resolution_depth=0,
            native_base_turn_order=None,
            native_timeline_round=1,
        )

        timeline = isolated_native_state_timeline()(fight, 4875)
        self.assertIn(4875, fight.actors)
        self.assertNotIn(4875, fight.order)
        self.assertEqual(timeline.clock_actor_index, -1)
        self.assertEqual(fight.order, [7, -7])

    def test_luna_6177_wp_zero_and_maximum_branches_use_native_conditions(self):
        queue = json.loads((RUNTIME / "bookless-five-scenarios.json").read_text())
        luna = next(row for row in queue["diagnoses"] if row["reference"] == 5114)
        effects = luna["effect_rows"]
        wp_zero = effects["293117"]["criteria"]
        wp_maximum = effects["293123"]["criteria"]

        def context(wp, maximum, states):
            return ConditionContext(
                {
                    "caster": ConditionActor(
                        characteristics={"WP": wp},
                        characteristic_maxima={"WP": maximum},
                        state_ids=frozenset(states),
                    )
                }
            )

        # The native alias database is intentionally not loaded in this
        # manifest-level test; preserve the audited WP canonical name here.
        with patch(
            "wakfu_server.combat_conditions.canonical_aliases",
            return_value={"WP": "WP"},
        ):
            self.assertTrue(evaluate_condition(wp_zero, context(0, 7, ())))
            self.assertFalse(evaluate_condition(wp_zero, context(1, 7, ())))
            self.assertFalse(evaluate_condition(wp_zero, context(0, 7, (6178,))))
            self.assertTrue(evaluate_condition(wp_maximum, context(7, 7, (6178,))))
            self.assertFalse(evaluate_condition(wp_maximum, context(6, 7, (6178,))))
            self.assertFalse(evaluate_condition(wp_maximum, context(7, 7, ())))


if __name__ == "__main__":
    unittest.main()
