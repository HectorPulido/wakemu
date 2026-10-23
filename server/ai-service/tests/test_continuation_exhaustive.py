"""Adversarial custody, generator lifecycle and malformed-hint coverage."""
from copy import deepcopy
import random
from types import SimpleNamespace
import unittest

import test_turn_continuation as fixtures
from wakfu_ai.planning import turn_continuation as continuation
from wakfu_ai.planning.query_search import _warm_start_actions


class ContinuationIsolationTests(unittest.TestCase):
    @staticmethod
    def driver(runtime, holders, *, fail=False):
        @continuation.turn_scope
        def generate(value):
            holder = continuation.current()
            holder.begin(value)
            holders.append(holder)
            try:
                yield "first"
                if fail:
                    raise ValueError("continuation driver failed")
                yield continuation.current()
            finally:
                holders.append(continuation.current())

        return generate(runtime)

    def test_suspended_direct_driver_does_not_leak_holder_into_caller(self):
        holders = []
        driver = self.driver(fixtures.runtime(), holders)
        try:
            next(driver)
            self.assertIsNone(continuation.current())
        finally:
            driver.close()
        self.assertIs(holders[0], holders[-1])
        self.assertIsNone(continuation.current())

    def test_interleaved_direct_generators_with_same_native_ids_are_isolated(self):
        holders = []
        one = self.driver(fixtures.runtime(), holders)
        two = self.driver(fixtures.runtime(), holders)
        try:
            next(one)
            next(two)
            self.assertIsNot(holders[0], holders[1])
            self.assertIs(next(one), holders[0])
            self.assertIs(next(two), holders[1])
        finally:
            one.close()
            two.close()
        self.assertIsNone(continuation.current())

    def test_out_of_order_close_does_not_restore_a_closed_holder(self):
        holders = []
        first, second = fixtures.runtime(), fixtures.runtime()
        second.fight.id += 1
        one, two = self.driver(first, holders), self.driver(second, holders)
        next(one)
        next(two)
        one.close()
        self.assertIsNone(continuation.current())
        self.assertIs(next(two), holders[1])
        two.close()
        self.assertIsNone(continuation.current())

    def test_generator_exception_discards_only_its_own_holder(self):
        holders = []
        one = self.driver(fixtures.runtime(), holders, fail=True)
        two = self.driver(fixtures.runtime(), holders)
        try:
            next(one)
            next(two)
            with self.assertRaisesRegex(ValueError, "driver failed"):
                next(one)
            self.assertIs(next(two), holders[1])
            self.assertIsNone(continuation.current())
        finally:
            one.close()
            two.close()

    def test_throw_executes_cleanup_under_the_correct_holder(self):
        holders = []
        driver = self.driver(fixtures.runtime(), holders)
        next(driver)
        with self.assertRaisesRegex(RuntimeError, "external cancellation"):
            driver.throw(RuntimeError("external cancellation"))
        self.assertIs(holders[0], holders[-1])
        self.assertIsNone(continuation.current())

    def test_shared_publication_scope_reuses_holder_across_private_runtime_copies(self):
        value = fixtures.runtime()
        holders = []
        with continuation.scope(publication_required=True) as publisher:
            publisher.begin(value)
            for candidate in (deepcopy(value), deepcopy(value)):
                driver = self.driver(candidate, holders)
                next(driver)
                self.assertIs(holders[-1], publisher)
                driver.close()
                self.assertIs(continuation.current(), publisher)
        self.assertIsNone(continuation.current())


class ContinuationMalformedAndBindingTests(unittest.TestCase):
    def test_incomplete_boundary_disables_hint_without_inventing_native_fields(self):
        # Preparation-failure adapters may expose an actor and phase before
        # their complete fight/runtime exists. Optional custody must not mask
        # that original error with a missing revision or identity AttributeError.
        incomplete = SimpleNamespace(
            fight=SimpleNamespace(phase="active", current=SimpleNamespace(hp=20)),
            awaiting_ack=None,
            pending=[],
        )
        cases = [incomplete]
        for owner, name in (
            ("fight", "sequence"),
            ("fight", "id"),
            ("fight", "turn_id"),
            ("actor", "id"),
        ):
            value = fixtures.runtime()
            target = value.fight.current if owner == "actor" else value.fight
            delattr(target, name)
            cases.append(value)
        for value in cases:
            before = deepcopy(vars(value.fight))
            holder = continuation.TurnContinuation()
            holder.begin(value)
            self.assertFalse(holder.owns(value))
            self.assertIsNone(fixtures.bind(value))
            self.assertIsNone(holder.proposal(value, fixtures.bind(value)))
            self.assertEqual(vars(value.fight), before)

    def test_nonfinite_actor_health_disables_optional_custody(self):
        for health in (float("nan"), float("inf"), float("-inf")):
            value = fixtures.runtime()
            value.fight.current.hp = health
            self.assertIsNone(fixtures.bind(value))

    def test_all_provenance_fields_are_independent_and_fail_closed(self):
        for name in ("sourceKey", "rootState", "requestId"):
            for wrong in (None, "", "foreign", 1, [], {}):
                with self.subTest(name=name, wrong=wrong):
                    value = fixtures.runtime()
                    holder = continuation.TurnContinuation()
                    holder.stage(
                        fixtures.decision(**{name: wrong}), fixtures.bind(value), value
                    )
                    holder.confirm(value, action=fixtures.FIRST)
                    self.assertIsNone(holder.proposal(value, fixtures.bind(value)))

    def test_missing_and_invalid_policy_bindings_disable_optional_hint(self):
        value = fixtures.runtime()
        for key in ("instance", "catalog", "source", "root", "request"):
            for wrong in (None, "", 1, [], {}):
                self.assertIsNone(fixtures.bind(value, **{key: wrong}))
        for policy in ({"x": float("nan")}, {"x": float("inf")}, {"x": object()}):
            self.assertIsNone(fixtures.bind(value, policy=policy))

    def test_policy_dictionary_order_does_not_invalidate_equivalent_policy(self):
        value = fixtures.runtime()
        self.assertEqual(
            fixtures.bind(value, policy={"a": 1, "b": 2})["identity"],
            fixtures.bind(value, policy={"b": 2, "a": 1})["identity"],
        )

    def test_warm_start_malformed_corpus_never_becomes_an_action(self):
        invalid = [
            None,
            [],
            1,
            True,
            "warm",
            {},
            {"schema": continuation.SCHEMA, "actions": []},
            {"schema": continuation.SCHEMA, "actions": [fixtures.NEXT] * 4},
        ]
        actions = [
            None,
            [],
            {},
            dict(type="end_turn"),
            dict(type="unknown"),
            dict(type="move", path=[]),
            dict(type="move", path=[[True, 0, 0]]),
            dict(type="move", path=[[1, 0]]),
            dict(type="move", path=[[1, 0, 0]], extra=1),
        ]
        for coordinate in (None, True, 1.0, float("nan"), "1", [], {}):
            actions.append(dict(fixtures.FIRST, target=[coordinate, 0, 0]))
        for field in ("spellId", "level", "targetId"):
            for wrong in (None, True, 1.0, "1", [], {}):
                actions.append(dict(fixtures.FIRST, **{field: wrong}))
        invalid += [
            dict(schema=continuation.SCHEMA, actions=[action]) for action in actions
        ]
        for hint in invalid:
            with self.subTest(hint=hint):
                self.assertEqual(_warm_start_actions(hint), [])

    def test_randomized_valid_hint_decoding_copies_nested_coordinates(self):
        rng = random.Random(20261022)
        for _ in range(250):
            coordinate = [rng.randrange(-100, 100) for _ in range(3)]
            action = dict(fixtures.FIRST, target=coordinate)
            hint = dict(schema=continuation.SCHEMA, actions=[action])
            decoded = _warm_start_actions(hint)
            self.assertEqual(decoded, [action])
            decoded[0]["target"][0] += 1000
            self.assertNotEqual(decoded[0]["target"], action["target"])

    def test_discard_and_double_confirmation_cannot_resurrect_a_tail(self):
        value = fixtures.runtime()
        holder = continuation.TurnContinuation()
        holder.stage(fixtures.decision(), fixtures.bind(value), value)
        holder.discard()
        holder.confirm(value, action=fixtures.FIRST)
        self.assertIsNone(holder.proposal(value, fixtures.bind(value)))
        holder.stage(fixtures.decision(), fixtures.bind(value), value)
        holder.confirm(value, action=fixtures.FIRST)
        holder.confirm(value, action=fixtures.FIRST)
        self.assertIsNone(holder.proposal(value, fixtures.bind(value)))

    def test_bounded_tail_ignores_actions_beyond_three(self):
        value = fixtures.runtime()
        holder = continuation.TurnContinuation()
        plan = [fixtures.FIRST] + [deepcopy(fixtures.NEXT) for _ in range(3)] + [None]
        holder.stage(fixtures.decision(plan=plan), fixtures.bind(value), value)
        holder.confirm(value, action=fixtures.FIRST)
        self.assertEqual(
            len(holder.proposal(value, fixtures.bind(value))["actions"]), 3
        )


if __name__ == "__main__":
    unittest.main()
