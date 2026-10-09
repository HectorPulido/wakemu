import json
from pathlib import Path
import unittest

from audit_class_conditional_transitions import (
    transition_cases,
    mandatory_caster_deck_references,
    literal_state_requirements,
    caller_rank,
    native_state_selector,
    focused_plans,
    observed_level_matches,
)
from audit_active_spells import encode_deck
from wakfu_server.spells import validate_deck


class ConditionalTransitionInventoryTests(unittest.TestCase):
    def test_counter_thresholds_use_literal_native_comparison_not_guessed_repeat_count(
        self,
    ):
        rows = literal_state_requirements(
            'GetStateLevel(1)>=100 and GetStateLevel(2,"target")==3 and not (GetStateLevel(4)>5)'
        )
        self.assertEqual(
            rows,
            [
                dict(state=1, selector="caster", level=100, comparison="minimum"),
                dict(state=2, selector="target", level=3, comparison="exact"),
            ],
        )
        self.assertFalse(observed_level_matches(99, rows[0]))
        self.assertTrue(observed_level_matches(100, rows[0]))
        self.assertFalse(observed_level_matches(4, rows[1]))
        requested = [dict(state=1, selector="caster", level=2, comparison="exact")]
        candidate = dict(
            spell=10,
            source_depth=1,
            native_state_applicator=100,
            native_state_parameters=[1, 0, 1, 0],
        )
        matching = dict(candidate, source_depth=2, native_state_parameters=[1, 0, 2, 0])
        self.assertLess(
            caller_rank(matching, 6, 20, {10}, set(), requested, 1),
            caller_rank(candidate, 6, 20, {10}, set(), requested, 1),
        )

    def test_state_focus_preserves_every_other_requirement_of_same_native_criterion(
        self,
    ):
        plans = [
            dict(preparation=[dict(state=1), dict(state=2)]),
            dict(preparation=[dict(state=3)]),
        ]
        selected = focused_plans(plans, [1])
        self.assertEqual(selected, plans[:1])
        self.assertEqual([row["state"] for row in selected[0]["preparation"]], [1, 2])

    def test_native_default_state_selector_is_caster_not_report_annotation(self):
        annotation = "native default selector: requires function contract"
        for raw in ("HasState(1)", "GetStateLevel(1)==2", "HasStateFromLevel(1,3)"):
            self.assertEqual(native_state_selector(raw, 1, annotation), "caster")
        self.assertEqual(
            native_state_selector('HasState(1,"target")', 1, annotation), "target"
        )
        self.assertEqual(
            native_state_selector("UnknownStateFunction(1)", 1, annotation), annotation
        )

    def test_exact_native_state_level_and_guarded_actual_grant_source_ranking(self):
        rows = literal_state_requirements(
            'HasState(1,2,"caster") and HasStateFromLevel(3,4,"target") and not HasState(5)'
        )
        self.assertEqual(
            rows,
            [
                dict(state=1, selector="caster", level=2, comparison="exact"),
                dict(state=3, selector="target", level=4, comparison="minimum"),
            ],
        )
        deep = dict(
            spell=10,
            source_depth=10,
            native_state_applicator=100,
            baseline_permission_observations=[],
        )
        shallow_grant = dict(
            spell=20,
            source_depth=2,
            native_state_applicator=200,
            baseline_permission_observations=[
                dict(breed=6, level=20, status="prepared_transaction")
            ],
        )
        self.assertLess(
            caller_rank(shallow_grant, 6, 20, {10}, set()),
            caller_rank(deep, 6, 20, {10}, set()),
        )

    def test_negative_alternative_and_target_decks_are_not_caster_requirements(self):
        self.assertEqual(
            mandatory_caster_deck_references(
                "IsSpellInDeck(1) and not IsSpellInDeck(2)"
            ),
            {1},
        )
        self.assertEqual(
            mandatory_caster_deck_references("IsSpellInDeck(1) or IsSpellInDeck(2)"),
            set(),
        )
        self.assertEqual(
            mandatory_caster_deck_references('IsSpellInDeck(3,"target")'), set()
        )
        self.assertEqual(
            mandatory_caster_deck_references(
                "(IsSpellInDeck(1) and IsSpellInDeck(2)) or IsSpellInDeck(1)"
            ),
            {1},
        )

    def plans(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/combat-inventory/class-casting-transition-plan-20261008.json"
        )
        return json.loads(path.read_text())["plans"]

    def test_all_requested_states_accounted_without_fabricating_callers(self):
        cases, inventory = transition_cases(self.plans())
        requested = {
            row["state"] for plan in self.plans() for row in plan["preparation"]
        }
        selected = {case["state"] for case in cases}
        absent = set(inventory["states_without_usable_caller_candidates"])
        self.assertEqual(requested, selected | absent)
        self.assertFalse(selected & absent)
        self.assertEqual(len(requested), 48)
        for case in cases:
            validate_deck(
                encode_deck(case["deck"], [case["passive"]] if case["passive"] else []),
                case["breed"],
                case["level"],
            )
            self.assertFalse(
                set(case["deck"]) & set(case["unavailable_deck_references"])
            )

    def test_case_bound_leaves_unselected_states_explicit(self):
        cases, inventory = transition_cases(self.plans(), maximum_cases=1)
        self.assertEqual(len(cases), 1)
        self.assertEqual(inventory["selected_states"], 1)
        self.assertEqual(
            len(inventory["unselected_states"]),
            inventory["states_with_caller_candidates"] - 1,
        )
