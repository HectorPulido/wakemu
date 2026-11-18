"""Focused tests for the authored, explicitly approximate pizza scoring matrix."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.maps import native_order_trial_rules
from wakfu_server.achievements import native_order_trials


class NativeOrderTrialRulesTests(unittest.TestCase):
    def test_checked_in_rules_are_complete_and_provenance_is_honest(self):
        rules, provenance = native_order_trial_rules.load()
        source = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/achievements/order_trial_profiles/astrub_pizzlarva.scoring.json"
        )
        document = json.loads(source.read_text())

        self.assertEqual(provenance["kind"], "reviewed_reconstruction")
        self.assertIn("not recovered official", document["native_accuracy"])
        self.assertEqual(len(rules.weights), 9)
        self.assertEqual(len({pair for pair, _points in rules.weights}), 9)
        self.assertTrue(
            all(points > 0 and points % 5 == 0 for _, points in rules.weights)
        )
        self.assertEqual((rules.score_threshold, rules.strike_limit), (400, 3))
        self.assertEqual((rules.ingredient_batch, rules.ingredient_capacity), (2, 10))

        missing = deepcopy(document)
        missing["weights"].pop()
        malformed = deepcopy(document)
        malformed["weights"][0][2] = True
        forged = deepcopy(document)
        forged["provenance"]["kind"] = "official_native"
        for changed in (missing, malformed, forged):
            with self.subTest(change=changed["provenance"]):
                with self.assertRaises(ValueError):
                    native_order_trial_rules.validate(changed)

    def test_loaded_rules_score_exact_boundary_and_only_hard_mode_qualifies(self):
        rules, _provenance = native_order_trial_rules.load()
        recipe_weights = dict(rules.weights)

        batches_395 = (
            (("blue", "tomato"), ("blue", "cheese"), ("blue", "pepper")),
            (("blue", "pepper"), ("red", "pepper"), ("green", "pepper")),
            (("red", "pepper"), ("green", "tomato"), ("green", "pepper")),
        )
        batches_400 = (
            (("blue", "tomato"), ("blue", "cheese"), ("blue", "pepper")),
            (("blue", "cheese"), ("red", "pepper"), ("green", "pepper")),
            (("red", "pepper"), ("green", "cheese"), ("green", "pepper")),
        )
        self.assertEqual(
            sum(recipe_weights[pair] for batch in batches_395 for pair in batch), 395
        )
        self.assertEqual(
            sum(recipe_weights[pair] for batch in batches_400 for pair in batch), 400
        )

        def serve(hard_mode, batches, encounter_id):
            first, *remaining = batches
            state = native_order_trials.start(
                owner_id=7, encounter_id=encounter_id, hard_mode=hard_mode, orders=first
            )
            serial = 0

            def act(action, **kwargs):
                nonlocal state, serial
                serial += 1
                state = native_order_trials.apply(
                    state,
                    rules,
                    owner_id=7,
                    encounter_id=encounter_id,
                    receipt=f"{encounter_id}:{serial}",
                    action=action,
                    **kwargs,
                )

            for batch_index, batch in enumerate(batches):
                if batch_index:
                    act("refill", next_orders=batch)
                for color, ingredient in batch:
                    larva_id = 1000 + serial
                    act("spawn", target_id=larva_id, color=color)
                    act("pickup", ingredient=ingredient)
                    act("tenderize", target_id=larva_id)
                    act("garnish", target_id=larva_id)
                    act("bake", target_id=larva_id)
            return lambda: state, act

        below_state, _ = serve(True, batches_395, 1)
        below = below_state()
        self.assertEqual((below.score, below.score_state_level), (395, 79))
        self.assertFalse(native_order_trials.qualifies(below, rules))

        hard_state, hard_act = serve(True, batches_400, 2)
        hard = hard_state()
        self.assertEqual((hard.score, hard.score_state_level), (400, 80))
        for index, color in enumerate(("blue", "red", "green")):
            larva_id = 2001 + index
            hard_act("spawn", target_id=larva_id, color=color)
            hard_act("escape", target_id=larva_id)
        hard = hard_state()
        self.assertTrue(hard.finished)
        self.assertEqual(hard.strikes, 3)
        self.assertTrue(native_order_trials.qualifies(hard, rules))

        normal_state, normal_act = serve(False, batches_400, 3)
        for index, color in enumerate(("blue", "red", "green")):
            larva_id = 3001 + index
            normal_act("spawn", target_id=larva_id, color=color)
            normal_act("escape", target_id=larva_id)
        normal = normal_state()
        self.assertEqual(normal.score, 400)
        self.assertTrue(normal.finished)
        self.assertFalse(native_order_trials.qualifies(normal, rules))


if __name__ == "__main__":
    unittest.main()
