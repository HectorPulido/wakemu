import random
import unittest
from types import SimpleNamespace
from wakfu_server.combat_critical import choose_critical
from wakfu_server.combat_random_transaction import rollback_external_rng


class CriticalTests(unittest.TestCase):
    def actor(self, chance):
        return SimpleNamespace(effect_stats={9: chance})

    def test_inclusive_roll_uses_live_modified_chance(self):
        class Draw:
            def randint(self, a, b):
                self.bounds = (a, b)
                return 37

        rng = Draw()
        self.assertTrue(choose_critical(self.actor(37), rng=rng).critical)
        self.assertFalse(choose_critical(self.actor(36), rng=rng).critical)
        self.assertEqual(rng.bounds, (1, 100))
        self.assertEqual(
            choose_critical(self.actor(37), rng=rng).diagnostic()["critical_roll"], 37
        )

    def test_guaranteed_impossible_and_branchless_consume_no_draw(self):
        class Forbidden:
            def randint(self, a, b):
                raise AssertionError("Unexpected random draw")

        for chance, expected in ((-1000, False), (0, False), (100, True), (1000, True)):
            self.assertEqual(
                choose_critical(self.actor(chance), rng=Forbidden()).critical, expected
            )
        self.assertFalse(
            choose_critical(
                self.actor(99), rng=Forbidden(), critical_available=False
            ).critical
        )

    def test_unknown_authority_and_malformed_draw_reject(self):
        for actor in (SimpleNamespace(), self.actor(True), self.actor(1001)):
            with self.assertRaises(ValueError):
                choose_critical(actor, rng=random.Random(1))

        class Invalid:
            def randint(self, a, b):
                return 0

        with self.assertRaises(ValueError):
            choose_critical(self.actor(20), rng=Invalid())

    def test_explicit_override_does_not_require_guessed_snapshot(self):
        self.assertFalse(choose_critical(None, rng=None, mode="normal").critical)
        self.assertTrue(choose_critical(None, rng=None, mode="critical").critical)
        with self.assertRaises(ValueError):
            choose_critical(None, rng=None, mode="critical", critical_available=False)

    def test_one_decision_shared_by_all_effects_and_failed_cast_restores_rng(self):
        rng = random.Random(9)
        before = rng.getstate()

        @rollback_external_rng
        def cast(*, rng, reject):
            decision = choose_critical(self.actor(30), rng=rng)
            branches = [decision.critical for _ in range(3)]
            if reject:
                raise ValueError("Child rejected")
            return branches

        with self.assertRaises(ValueError):
            cast(rng=rng, reject=True)
        self.assertEqual(rng.getstate(), before)
        branches = cast(rng=rng, reject=False)
        expected = random.Random(9)
        expected.randint(1, 100)
        self.assertEqual(rng.getstate(), expected.getstate())
        self.assertEqual(len(set(branches)), 1)

    def test_boundary_restores_branch_draw_and_children_on_failure(self):
        from wakfu_server.combat_critical import prepare_with_critical

        rng = random.Random(7)
        before = rng.getstate()

        def failure(*, critical, rng):
            rng.randint(1, 100)
            raise ValueError("Mandatory effect rejected")

        with self.assertRaises(ValueError):
            prepare_with_critical(self.actor(40), rng=rng, prepare=failure)
        self.assertEqual(rng.getstate(), before)

        def success(*, critical, rng):
            return critical, rng.randint(1, 100)

        decision, result = prepare_with_critical(
            self.actor(40), rng=rng, prepare=success
        )
        expected = random.Random(7)
        roll = expected.randint(1, 100)
        child = expected.randint(1, 100)
        self.assertEqual(decision.critical, roll <= 40)
        self.assertEqual(result, (roll <= 40, child))
        self.assertEqual(rng.getstate(), expected.getstate())

    def test_original_ui_availability_catalog_is_exact_not_subtree(self):
        from wakfu_server.combat_critical import spell_critical_available

        self.assertTrue(spell_critical_available(6908, 20))
        self.assertTrue(spell_critical_available(2043, 20))
        self.assertFalse(spell_critical_available(7225, 20))
        with self.assertRaises(ValueError):
            spell_critical_available(999999999, 20)
        with self.assertRaises(ValueError):
            spell_critical_available(6908, 201)

    def test_real_auto_entry_rolls_inside_reversible_boundary_and_reuses_branch(self):
        import struct
        from unittest.mock import patch
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.spells import encode_deck

        actor = SimpleNamespace(
            id=1,
            effect_stats={4: 6, 9: 40},
            effective_level=20,
            controlled=True,
            owner_id=1,
            hp=100,
        )
        fight = SimpleNamespace(
            actors={1: actor},
            native_spell_grants={},
            phase="active",
            current=actor,
        )
        rng = random.Random(7)
        before = rng.getstate()
        body = struct.pack(">qqiih", 1, (1 << 32) | 6908, 0, 0, 0)
        shared = []

        def runtime(*a, **kw):
            shared.append((kw["critical"], kw["rng"]))
            return object(), SimpleNamespace(cast_condition=lambda *a: None)

        def reject(*a, **kw):
            rng.randint(1, 100)
            raise ValueError("Mandatory child rejects")

        with patch(
            "wakfu_server.combat_server_spell.server_runtime", side_effect=runtime
        ), patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ), patch(
            "wakfu_server.combat_server_spell.prepare_spell_transaction",
            side_effect=reject,
        ):
            with self.assertRaises(ValueError):
                prepare_server_spell(
                    body,
                    {"id": 1, "breed": 16, "level": 20},
                    [],
                    fight,
                    1,
                    encode_deck([6908], []),
                    action_id=1,
                    line_of_sight=None,
                    critical=None,
                    rng=rng,
                )
        self.assertEqual(rng.getstate(), before)
        self.assertIs(shared[0][1], rng)
        result = SimpleNamespace(plan={})
        with patch(
            "wakfu_server.combat_server_spell.server_runtime", side_effect=runtime
        ), patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ), patch(
            "wakfu_server.combat_server_spell.prepare_spell_transaction",
            return_value=result,
        ) as prepare:
            out = prepare_server_spell(
                body,
                {"id": 1, "breed": 16, "level": 20},
                [],
                fight,
                1,
                encode_deck([6908], []),
                action_id=1,
                line_of_sight=None,
                critical=None,
                rng=rng,
            )
        expected = random.Random(7)
        roll = expected.randint(1, 100)
        self.assertEqual(out.plan["critical_decision"]["critical_roll"], roll)
        self.assertEqual(prepare.call_args.kwargs["critical"], roll <= 40)
        self.assertEqual(shared[-1][0], roll <= 40)
        self.assertEqual(rng.getstate(), expected.getstate())
