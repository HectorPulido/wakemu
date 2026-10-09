import unittest
from random import Random
from types import SimpleNamespace
from wakfu_server.combat_transaction_rng import (
    transactional_spell_rng,
)
from wakfu_server.combat_random_transaction import rollback_external_rng


class TransactionRNGTests(unittest.TestCase):
    def test_nested_failure_restores_shared_transaction_owner(self):
        owner = Random(9)
        before = owner.getstate()

        @transactional_spell_rng
        def transaction(*, runtime_factory):
            runtime_factory.transaction_rng.random()
            runtime_factory.transaction_rng.randint(1, 100)
            raise ValueError("nested failure")

        with self.assertRaisesRegex(ValueError, "nested failure"):
            transaction(runtime_factory=SimpleNamespace(transaction_rng=owner))
        self.assertEqual(owner.getstate(), before)

    def test_success_advances_owner_and_custom_factory_has_no_inferred_rng(self):
        owner = Random(9)
        before = owner.getstate()

        @transactional_spell_rng
        def transaction(*, runtime_factory):
            if hasattr(runtime_factory, "transaction_rng"):
                return runtime_factory.transaction_rng.random()
            return 1

        transaction(runtime_factory=SimpleNamespace(transaction_rng=owner))
        self.assertNotEqual(owner.getstate(), before)
        self.assertEqual(transaction(runtime_factory=lambda *args: None), 1)

    def test_server_entry_restores_critical_draw_before_factory_creation(self):
        owner = Random(9)
        before = owner.getstate()

        @rollback_external_rng
        def prepare(*, rng):
            rng.random()
            raise ValueError("effect failure")

        with self.assertRaises(ValueError):
            prepare(rng=owner)
        self.assertEqual(owner.getstate(), before)
