import random
import unittest
from unittest.mock import patch
from wakfu_server.combat_random_transaction import rollback_external_rng


class RandomTransactionTests(unittest.TestCase):
    def test_rejection_restores_and_success_advances(self):
        rng = random.Random(44)
        initial = rng.getstate()

        @rollback_external_rng
        def execute(*, rng=None, reject=False):
            value = rng.randrange(10)
            if reject:
                raise ValueError("Mandatory child failed")
            return value

        with self.assertRaises(ValueError):
            execute(rng=rng, reject=True)
        self.assertEqual(rng.getstate(), initial)
        execute(rng=rng)
        self.assertNotEqual(rng.getstate(), initial)

    def test_real_spell_entry_restores_external_rng_after_factory_failure(self):
        from wakfu_server.combat_server_spell import prepare_server_spell

        rng = random.Random(5)
        initial = rng.getstate()

        def failure(*args, **kwargs):
            kwargs["rng"].randrange(100)
            raise ValueError("Unsupported native child")

        with patch(
            "wakfu_server.combat_server_spell.server_runtime", side_effect=failure
        ):
            with self.assertRaises(ValueError):
                prepare_server_spell(
                    b"",
                    {"id": 1},
                    [],
                    __import__("types").SimpleNamespace(
                        actors={
                            1: __import__("types").SimpleNamespace(effect_stats={4: 6})
                        }
                    ),
                    1,
                    b"",
                    action_id=1,
                    line_of_sight=None,
                    critical=False,
                    rng=rng,
                )
        self.assertEqual(rng.getstate(), initial)

    def test_nonreversible_external_rng_rejects_before_action(self):
        called = []
        wrapped = rollback_external_rng(lambda **kw: called.append(True))
        with self.assertRaises(ValueError):
            wrapped(rng=object())
        self.assertEqual(called, [])
        wrapped()
        self.assertEqual(called, [True])

    def test_weapon_entry_rejection_preserves_rng(self):
        from wakfu_server.combat_weapon import prepare_server_weapon

        rng = random.Random(8)
        before = rng.getstate()
        # Invalid framing rejects before any combat/resource mutation.
        with self.assertRaises(ValueError):
            prepare_server_weapon(
                b"",
                {},
                [],
                None,
                1,
                b"",
                action_id=1,
                line_of_sight=None,
                critical=False,
                rng=rng,
            )
        self.assertEqual(rng.getstate(), before)
        self.assertTrue(hasattr(prepare_server_weapon, "__wrapped__"))
