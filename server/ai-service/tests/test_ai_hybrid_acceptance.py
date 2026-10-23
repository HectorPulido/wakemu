"""Real native selection, private forecasting and transactional turn acceptance."""
import unittest

import test_native_oracle as native_fixtures
from test_native_session import StubTransport
from wakfu_ai.bridge.world_bridge import NativeSession
from wakfu_ai.context.native_context import encode
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.planning.query_search import search
from wakfu_server.combat_runtime_messages import RuntimeMessages


class HybridNativeAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixtures.NativeOracleTests.setUpClass()

    def test_selected_native_attack_preserves_source_then_commits_once_and_acks(self):
        from wakfu_server.spells import default_deck

        fixture = native_fixtures.NativeOracleTests.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle = native_fixtures.NativeOracleTests.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        transport = StubTransport()
        session = NativeSession(
            oracle,
            transport,
            None,
            policy={"limits": {"depth": 1, "beam": 4, "nodes": 16, "budgetMs": 10000}},
            policy_version="hybrid-native-acceptance",
            fight_instance_id="hybrid-native-acceptance",
        )
        envelope = session.envelope()
        # Rival forecasting has an independent corpus; this acceptance follows
        # the selected own action through real native execution and delivery.
        envelope["operations"] = [
            operation
            for operation in envelope["operations"]
            if operation != "project_turn"
        ]
        store = type("Store", (), {"json": lambda _, key: transport.graphs[key]})()
        before = encode(runtime)
        coroutine = search(envelope, store)
        request = next(coroutine)
        while True:
            try:
                request = coroutine.send(session.query(request))
            except StopIteration as completed:
                decision = completed.value
                break
        self.assertEqual(encode(runtime), before)
        session.guard()
        action = decision["action"]
        self.assertEqual(action["type"], "cast", decision)
        self.assertEqual(action["targetId"], fixture.pc.id)
        preview, _, _ = oracle.preview(runtime, action)
        self.assertLess(preview.fight.actors[fixture.pc.id].hp, fixture.pc.hp)
        self.assertEqual(encode(runtime), before)

        def fail_delivery(*args, **kwargs):
            raise ValueError("hybrid acceptance delivery failure")

        with self.assertRaisesRegex(ValueError, "hybrid acceptance delivery failure"):
            oracle.commit(action, stats_serializer=fail_delivery)
        self.assertEqual(encode(runtime), before)
        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=runtime.fight.id,
        )
        initial_action_id = runtime.action_id
        packets = oracle.commit(action, stats_serializer=serializer)
        self.assertTrue(packets)
        self.assertEqual(runtime.action_id, initial_action_id + 1)
        self.assertEqual(
            runtime.fight.actors[fixture.pc.id].hp,
            preview.fight.actors[fixture.pc.id].hp,
        )
        usage = runtime.fight.native_spell_usage[str(fixture.npc.id)]
        self.assertEqual(usage["casts"][str(action["spellId"])], 1)
        self.assertEqual(
            usage["targets"][str(action["spellId"])][str(fixture.pc.id)], 1
        )
        self.assertIsNone(runtime.awaiting_ack)
        ended = oracle.commit({"type": "end_turn"}, stats_serializer=serializer)
        self.assertTrue(ended)
        self.assertIsNotNone(runtime.awaiting_ack)
        self.assertTrue(runtime.pending)


if __name__ == "__main__":
    unittest.main()
