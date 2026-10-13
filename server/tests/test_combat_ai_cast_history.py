from copy import deepcopy
import unittest
import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.combat_ai_cast_history import (
    POLICY,
    fresh_history,
    record_authorized_cast,
    has_cast_spell,
)


class AiCastHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transaction_fixtures.SpellTransactionTests.setUpClass()

    def fixture(self):
        fixture = transaction_fixtures.SpellTransactionTests()
        fixture.setUp()
        return fixture

    def test_fresh_fights_reset_local_policy_history(self):
        first = self.fixture().fight
        second = self.fixture().fight
        record_authorized_cast(first, 7, 6266)
        self.assertEqual(first.wakemu_ai_cast_history["policy"], POLICY)
        self.assertFalse(has_cast_spell(second, 7, 6266))
        self.assertEqual(second.wakemu_ai_cast_history, fresh_history())

    def test_actor_and_summon_identity_histories_are_isolated(self):
        fight = self.fixture().fight
        record_authorized_cast(fight, 7, 6266)
        self.assertFalse(has_cast_spell(fight, -7, 6266))
        self.assertTrue(has_cast_spell(fight, 7, 6266))
        record_authorized_cast(fight, -7, 6266)
        self.assertEqual(
            fight.wakemu_ai_cast_history["casts"], {"7": {"6266": 1}, "-7": {"6266": 1}}
        )

    def test_deepcopy_forecast_history_is_private(self):
        fight = self.fixture().fight
        preview = deepcopy(fight)
        record_authorized_cast(preview, 7, 6266)
        self.assertTrue(has_cast_spell(preview, 7, 6266))
        self.assertFalse(has_cast_spell(fight, 7, 6266))

    def test_real_transaction_records_before_factory_callback(self):
        fixture = self.fixture()
        seen = []

        def factory(preview, plan):
            seen.append(has_cast_spell(preview, 7, 6266))
            self.assertFalse(has_cast_spell(fixture.fight, 7, 6266))
            # A same-spell recursive predicate sees history before any root.
            self.assertFalse(not has_cast_spell(preview, 7, 6266))
            return fixture.factory(preview, plan)

        transaction = fixture.execute(factory=factory)
        self.assertEqual(seen, [True])
        self.assertTrue(has_cast_spell(transaction.fight, 7, 6266))

    def test_real_failed_serializer_does_not_adopt_and_successful_commit_does(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        fixture = self.fixture()
        runtime = RuntimeMessages(fixture.fight)
        transaction = fixture.execute()
        before = deepcopy(fixture.fight.wakemu_ai_cast_history)

        def fail(*args):
            raise ValueError("serializer failed")

        with self.assertRaisesRegex(ValueError, "serializer failed"):
            commit_spell_transaction(runtime, transaction, stats_serializer=fail)
        self.assertIs(runtime.fight, fixture.fight)
        self.assertEqual(runtime.fight.wakemu_ai_cast_history, before)
        commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda *args: b"stats"
        )
        self.assertTrue(has_cast_spell(runtime.fight, 7, 6266))

    def test_unknown_actor_and_forged_policy_fail_closed(self):
        fight = self.fixture().fight
        with self.assertRaises(ValueError):
            record_authorized_cast(fight, 999, 6266)
        fight.wakemu_ai_cast_history["policy"] = "native-unproven"
        with self.assertRaises(ValueError):
            has_cast_spell(fight, 7, 6266)
