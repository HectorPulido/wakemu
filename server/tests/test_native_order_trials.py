"""Pure transition tests for reconstructed native pizza-order trials.

The nine-entry score matrix below is intentionally synthetic. Native scoring
weights have not been recovered, so these tests validate mechanics without
presenting fixture weights as production data.
"""

from copy import deepcopy
from dataclasses import replace
import unittest

from wakfu_server.achievements import native_order_trials as trials


SYNTHETIC_WEIGHTS = tuple(
    (recipe, 5 * (index + 1)) for index, recipe in enumerate(sorted(trials.RECIPES))
)
RULES = trials.OrderRules(SYNTHETIC_WEIGHTS)
ORDERS = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))


class NativeOrderTrialTests(unittest.TestCase):
    def action(self, state, action, receipt, **values):
        return trials.apply(
            state,
            RULES,
            owner_id=state.owner_id,
            encounter_id=state.encounter_id,
            receipt=receipt,
            action=action,
            **values,
        )

    def test_authority_requires_matching_owner_and_encounter(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        for owner, encounter in ((8, 41), (7, 42)):
            with self.subTest(owner=owner, encounter=encounter), self.assertRaisesRegex(
                ValueError, "authority mismatch"
            ):
                trials.apply(
                    state,
                    RULES,
                    owner_id=owner,
                    encounter_id=encounter,
                    receipt="committed-spawn",
                    action="spawn",
                    target_id=-1,
                    color="blue",
                )

    def test_snapshot_restore_continues_partial_order_without_replaying_receipts(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)

        # Earn one order, then checkpoint a second order after its ingredient
        # charge has been consumed onto a live larva.
        state = self.action(state, "spawn", "spawn-blue", target_id=-1, color="blue")
        state = self.action(state, "pickup", "pickup-tomato", ingredient="tomato")
        state = self.action(state, "tenderize", "tenderize-blue", target_id=-1)
        state = self.action(state, "garnish", "garnish-blue", target_id=-1)
        state = self.action(state, "bake", "bake-blue", target_id=-1)
        blue_score = dict(RULES.weights)[("blue", "tomato")]
        self.assertEqual(state.score, blue_score)
        self.assertNotIn(("blue", "tomato"), state.orders)

        state = self.action(state, "spawn", "spawn-red", target_id=-2, color="red")
        state = self.action(state, "pickup", "pickup-cheese", ingredient="cheese")
        state = self.action(state, "tenderize", "tenderize-red", target_id=-2)
        state = self.action(state, "garnish", "garnish-red", target_id=-2)
        self.assertEqual(state.charges, RULES.ingredient_batch - 1)
        self.assertEqual(state.larvae[0].ingredient, "cheese")

        checkpoint = trials.snapshot(state, RULES)
        reconnected = trials.restore(
            deepcopy(checkpoint), RULES, owner_id=7, encounter_id=41
        )
        self.assertEqual(reconnected, state)
        self.assertEqual(reconnected.score, blue_score)
        self.assertEqual(reconnected.orders, ORDERS[1:])
        self.assertEqual(reconnected.charges, 1)
        self.assertEqual(reconnected.larvae[0].actor_id, -2)

        replayed_bake = trials.apply(
            reconnected,
            RULES,
            owner_id=7,
            encounter_id=41,
            receipt="bake-blue",
            action="bake",
            target_id=-1,
        )
        replayed_garnish = trials.apply(
            reconnected,
            RULES,
            owner_id=7,
            encounter_id=41,
            receipt="garnish-red",
            action="garnish",
            target_id=-2,
        )
        self.assertIs(replayed_bake, reconnected)
        self.assertIs(replayed_garnish, reconnected)

        continued = trials.apply(
            reconnected,
            RULES,
            owner_id=7,
            encounter_id=41,
            receipt="bake-red-after-reconnect",
            action="bake",
            target_id=-2,
        )
        red_score = dict(RULES.weights)[("red", "cheese")]
        self.assertEqual(continued.score, blue_score + red_score)
        self.assertNotIn(("red", "cheese"), continued.orders)
        self.assertEqual(continued.strikes, 0)
        self.assertEqual(
            trials.restore(
                trials.snapshot(continued, RULES),
                RULES,
                owner_id=7,
                encounter_id=41,
            ),
            continued,
        )

    def test_restore_rejects_mismatched_authority_rules_and_malformed_state(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        state = self.action(state, "spawn", "spawn", target_id=-1, color="blue")
        state = self.action(state, "pickup", "pickup", ingredient="tomato")
        checkpoint = trials.snapshot(state, RULES)

        for owner, encounter in ((8, 41), (7, 42)):
            with self.subTest(owner=owner, encounter=encounter), self.assertRaisesRegex(
                ValueError, "incompatible order trial checkpoint"
            ):
                trials.restore(
                    checkpoint, RULES, owner_id=owner, encounter_id=encounter
                )

        changed_rules = trials.OrderRules(
            tuple((recipe, value + 5) for recipe, value in SYNTHETIC_WEIGHTS)
        )
        with self.assertRaisesRegex(ValueError, "incompatible order trial checkpoint"):
            trials.restore(checkpoint, changed_rules, owner_id=7, encounter_id=41)

        malformed = []
        duplicate_receipts = deepcopy(checkpoint)
        duplicate_receipts["receipts"].append(duplicate_receipts["receipts"][0])
        malformed.append(("duplicate receipts", duplicate_receipts))
        bool_charges = deepcopy(checkpoint)
        bool_charges["charges"] = True
        malformed.append(("boolean charge", bool_charges))
        duplicate_larvae = deepcopy(checkpoint)
        duplicate_larvae["larvae"].append(deepcopy(duplicate_larvae["larvae"][0]))
        malformed.append(("duplicate larva", duplicate_larvae))
        inconsistent_ingredient = deepcopy(checkpoint)
        inconsistent_ingredient["ingredient"] = None
        malformed.append(("ingredient reset with charges", inconsistent_ingredient))
        duplicate_orders = deepcopy(checkpoint)
        duplicate_orders["orders"] = [list(ORDERS[0]), list(ORDERS[0])]
        malformed.append(("duplicate order", duplicate_orders))

        for label, document in malformed:
            with self.subTest(label=label), self.assertRaises(ValueError):
                trials.restore(document, RULES, owner_id=7, encounter_id=41)

    def test_complete_score_matrix_and_three_distinct_orders_are_required(self):
        with self.assertRaisesRegex(ValueError, "complete reviewed scoring matrix"):
            trials.OrderRules(SYNTHETIC_WEIGHTS[:-1])
        incomplete = list(SYNTHETIC_WEIGHTS)
        incomplete[-1] = (incomplete[-1][0], 0)
        with self.assertRaisesRegex(ValueError, "complete reviewed scoring matrix"):
            trials.OrderRules(tuple(incomplete))
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        self.assertEqual(state.orders, ORDERS)
        with self.assertRaisesRegex(ValueError, "three distinct recipes"):
            trials.start(
                owner_id=7,
                encounter_id=41,
                hard_mode=True,
                orders=(ORDERS[0], ORDERS[0], ORDERS[2]),
            )

    def test_duplicate_committed_receipt_is_idempotent(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        spawned = self.action(state, "spawn", "receipt-1", target_id=-1, color="blue")
        replay = self.action(spawned, "spawn", "receipt-1", target_id=-2, color="red")
        self.assertIs(replay, spawned)
        self.assertEqual([larva.actor_id for larva in replay.larvae], [-1])

    def test_order_refill_requires_empty_queue_and_three_distinct_new_orders(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        with self.assertRaisesRegex(ValueError, "only when all three have been served"):
            self.action(state, "refill", "early-refill", next_orders=ORDERS)
        for index, (color, ingredient) in enumerate(ORDERS):
            actor = -(index + 1)
            state = self.action(
                state, "spawn", f"spawn-{index}", target_id=actor, color=color
            )
            state = self.action(
                state, "pickup", f"pickup-{index}", ingredient=ingredient
            )
            state = self.action(
                state, "tenderize", f"tenderize-{index}", target_id=actor
            )
            state = self.action(state, "garnish", f"garnish-{index}", target_id=actor)
            state = self.action(state, "bake", f"bake-{index}", target_id=actor)
        self.assertEqual(state.orders, ())
        replacement = (("blue", "cheese"), ("red", "pepper"), ("green", "tomato"))
        refilled = self.action(state, "refill", "refill", next_orders=replacement)
        self.assertEqual(refilled.orders, replacement)
        with self.assertRaisesRegex(ValueError, "three distinct recipes"):
            self.action(
                state,
                "refill",
                "bad-refill",
                next_orders=(replacement[0], replacement[0], replacement[2]),
            )

    def test_native_population_ceiling_changes_at_turns_one_six_and_ten(self):
        for turn, maximum in ((1, 1), (6, 2), (10, 3)):
            with self.subTest(turn=turn):
                self.assertEqual(trials.larva_limit(turn), maximum)
                state = replace(
                    trials.start(
                        owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS
                    ),
                    turn=turn,
                )
                for index in range(maximum):
                    state = self.action(
                        state,
                        "spawn",
                        f"turn-{turn}-spawn-{index}",
                        target_id=-(index + 1),
                        color="blue",
                    )
                with self.assertRaisesRegex(ValueError, "population limit"):
                    self.action(
                        state,
                        "spawn",
                        f"turn-{turn}-overflow",
                        target_id=-(maximum + 1),
                        color="red",
                    )

    def test_replacement_spawn_has_its_own_cap_and_survives_checkpoint_restore(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        state = self.action(
            state, "spawn", "constructor-spawn", target_id=-1, color="blue"
        )
        with self.assertRaisesRegex(ValueError, "population limit"):
            self.action(
                state, "spawn", "constructor-overflow", target_id=-2, color="red"
            )

        # The native replacement producer authorizes a separate cap of two
        # live larvae, even on the first turn when the constructor cap is one.
        state = self.action(
            state,
            "spawn",
            "replacement-spawn",
            target_id=-2,
            color="red",
            population_limit=2,
        )
        self.assertEqual({larva.actor_id for larva in state.larvae}, {-1, -2})
        self.assertEqual(state.turn, 1)

        checkpoint = trials.snapshot(state, RULES)
        restored = trials.restore(checkpoint, RULES, owner_id=7, encounter_id=41)
        self.assertEqual(restored, state)
        self.assertEqual(
            restored.receipts, frozenset({"constructor-spawn", "replacement-spawn"})
        )
        with self.assertRaisesRegex(ValueError, "population limit"):
            self.action(
                restored,
                "spawn",
                "replacement-overflow",
                target_id=-3,
                color="green",
                population_limit=2,
            )
        with self.assertRaisesRegex(ValueError, "native spawn population limit"):
            self.action(
                restored,
                "spawn",
                "invalid-bool-limit",
                target_id=-3,
                color="green",
                population_limit=True,
            )
        with self.assertRaisesRegex(ValueError, "native spawn population limit"):
            self.action(
                restored,
                "spawn",
                "invalid-zero-limit",
                target_id=-3,
                color="green",
                population_limit=0,
            )

        # Restored replacement capacity does not widen ordinary constructors.
        with self.assertRaisesRegex(ValueError, "population limit"):
            self.action(
                restored,
                "spawn",
                "default-constructor-overflow",
                target_id=-3,
                color="green",
            )

    def test_additive_ingredient_capacity_resets_on_type_change_and_survives_reconnect(
        self,
    ):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        for index, charges in enumerate((2, 4, 6)):
            state = self.action(
                state,
                "pickup",
                f"tomato-pickup-{index}",
                ingredient="tomato",
                charges_after=charges,
            )
        checkpoint = trials.snapshot(state, RULES)
        restored = trials.restore(checkpoint, RULES, owner_id=7, encounter_id=41)
        self.assertEqual((restored.ingredient, restored.charges), ("tomato", 6))
        self.assertEqual(
            restored.receipts,
            frozenset({"tomato-pickup-0", "tomato-pickup-1", "tomato-pickup-2"}),
        )

        replay = trials.apply(
            restored,
            RULES,
            owner_id=7,
            encounter_id=41,
            receipt="tomato-pickup-2",
            action="pickup",
            ingredient="tomato",
            charges_after=6,
        )
        self.assertIs(replay, restored)

        state = restored
        for index, charges in enumerate((8, 10, 10), start=3):
            state = self.action(
                state,
                "pickup",
                f"tomato-pickup-{index}",
                ingredient="tomato",
                charges_after=charges,
            )
        self.assertEqual(state.charges, RULES.ingredient_capacity)

        # A new barrel replaces the old supply; the same ingredient stacks.
        state = self.action(
            state, "pickup", "cheese-change", ingredient="cheese", charges_after=2
        )
        state = self.action(
            state, "pickup", "cheese-stack", ingredient="cheese", charges_after=4
        )
        state = self.action(state, "spawn", "larva", target_id=-1, color="blue")
        state = self.action(state, "tenderize", "tenderize", target_id=-1)
        state = self.action(state, "garnish", "garnish", target_id=-1)
        self.assertEqual((state.ingredient, state.charges), ("cheese", 3))

        before = state
        for label, witness in (("wrong count", 4), ("boolean count", True)):
            with self.subTest(label=label), self.assertRaisesRegex(
                ValueError, "additive pickup"
            ):
                self.action(
                    before,
                    "pickup",
                    f"bad-{label}",
                    ingredient="cheese",
                    charges_after=witness,
                )
        self.assertIs(state, before)
        with self.assertRaises(ValueError):
            trials.OrderRules(
                RULES.weights,
                score_threshold=RULES.score_threshold,
                strike_limit=RULES.strike_limit,
                ingredient_batch=RULES.ingredient_batch,
                ingredient_capacity=True,
            )

    def test_pickup_gives_two_charges_and_garnish_consumes_one(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        state = self.action(state, "spawn", "spawn", target_id=-1, color="blue")
        state = self.action(state, "pickup", "pickup", ingredient="tomato")
        self.assertEqual(state.charges, 2)
        state = self.action(state, "tenderize", "tenderize", target_id=-1)
        state = self.action(state, "garnish", "garnish", target_id=-1)
        self.assertEqual(state.charges, 1)
        self.assertEqual(state.larvae[0].ingredient, "tomato")

    def test_reapplied_tenderize_is_idempotent_until_authenticated_second_hit_death(
        self,
    ):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        state = self.action(state, "spawn", "spawn", target_id=-1, color="blue")
        state = self.action(state, "tenderize", "first", target_id=-1)
        after_expiry = self.action(
            state, "tenderize", "reapplied-after-expiry", target_id=-1
        )
        self.assertEqual(len(after_expiry.larvae), 1)
        self.assertTrue(after_expiry.larvae[0].tenderized)
        self.assertEqual(after_expiry.strikes, 0)

        state = self.action(
            after_expiry, "destroy_tenderized", "native-118970-death", target_id=-1
        )
        self.assertEqual(state.larvae, ())
        self.assertEqual(state.strikes, 0)

        not_tenderized = trials.start(
            owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS
        )
        not_tenderized = self.action(
            not_tenderized, "spawn", "other-spawn", target_id=-2, color="red"
        )
        with self.assertRaisesRegex(ValueError, "lacks its first tenderize"):
            self.action(
                not_tenderized,
                "destroy_tenderized",
                "unearned-native-death",
                target_id=-2,
            )

    def test_ungarnished_bake_and_escape_both_end_at_three_strikes(self):
        for action in ("bake", "escape"):
            with self.subTest(action=action):
                state = trials.start(
                    owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS
                )
                for index in range(3):
                    actor = -(index + 1)
                    state = self.action(
                        state,
                        "spawn",
                        f"{action}-spawn-{index}",
                        target_id=actor,
                        color="blue",
                    )
                    state = self.action(
                        state, action, f"{action}-strike-{index}", target_id=actor
                    )
                    self.assertEqual(state.strikes, index + 1)
                    self.assertEqual(state.finished, index == 2)

    def test_unrequested_garnished_recipe_scores_zero_without_a_strike(self):
        state = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        state = self.action(state, "spawn", "spawn", target_id=-1, color="blue")
        state = self.action(state, "pickup", "pickup", ingredient="pepper")
        state = self.action(state, "tenderize", "tenderize", target_id=-1)
        state = self.action(state, "garnish", "garnish", target_id=-1)
        state = self.action(state, "bake", "bake", target_id=-1)
        self.assertEqual(state.score, 0)
        self.assertEqual(state.strikes, 0)
        self.assertEqual(state.orders, ORDERS)

    def test_only_finished_hard_mode_score_at_threshold_qualifies(self):
        base = trials.start(owner_id=7, encounter_id=41, hard_mode=True, orders=ORDERS)
        self.assertFalse(trials.qualifies(replace(base, score=400), RULES))
        self.assertFalse(
            trials.qualifies(
                replace(base, hard_mode=False, score=500, finished=True), RULES
            )
        )
        self.assertFalse(
            trials.qualifies(replace(base, score=399, finished=True), RULES)
        )
        qualified = replace(base, score=400, finished=True)
        self.assertTrue(trials.qualifies(qualified, RULES))
        self.assertEqual(qualified.score_state_level, 80)
        self.assertEqual(replace(qualified, score=399).score_state_level, 79)


if __name__ == "__main__":
    unittest.main()
