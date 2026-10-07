"""A direct native commit retains guards without a redundant simulation."""
import unittest

from test_native_session import make_runtime, StubOracle, StubTransport
from wakfu_ai.bridge.world_bridge import NativeSession


class NativeCommitHandoffTests(unittest.TestCase):
    def make_session(self, action=None, mutate=False):
        runtime = make_runtime()
        oracle, transport = StubOracle(runtime), StubTransport()
        session = NativeSession(
            oracle,
            transport,
            object(),
            policy={},
            policy_version="handoff-test",
            fight_instance_id="handoff-test",
        )

        def request(endpoint, payload):
            self.assertEqual(endpoint, "/v3/decide")
            if mutate:
                runtime.future_runtime_extension = "changed-during-request"
            return dict(
                status="decided",
                decision=dict(
                    protocol=3,
                    requestId=session.request_id,
                    sourceKey=session.source,
                    rootState=session.root,
                    action=action or dict(type="move", path=[[1, 0, 0]]),
                ),
            )

        transport._retry_request = request
        return session, oracle

    def test_standalone_decision_still_freshly_certifies_native_action(self):
        session, oracle = self.make_session()
        self.assertEqual(session.decide()["action"]["type"], "move")
        self.assertEqual(len(oracle.preview_calls), 1)
        self.assertEqual(oracle.runtime.fight.current.position, (0, 0, 0))

    def test_immediate_commit_mode_returns_without_spending_or_simulating(self):
        session, oracle = self.make_session()
        self.assertEqual(session.decide(certify=False)["action"]["type"], "move")
        self.assertEqual(oracle.preview_calls, [])
        self.assertEqual(oracle.runtime.fight.current.mp, 3)
        self.assertEqual(oracle.runtime.fight.current.position, (0, 0, 0))

    def test_immediate_commit_mode_still_rejects_changed_complete_source(self):
        session, oracle = self.make_session(mutate=True)
        with self.assertRaisesRegex(ValueError, "source changed"):
            session.decide(certify=False)
        self.assertEqual(oracle.preview_calls, [])

    def test_standalone_illegal_selection_still_fails_certification(self):
        session, _ = self.make_session(action=dict(type="move", path=[[99, 0, 0]]))
        with self.assertRaisesRegex(ValueError, "Illegal native movement"):
            session.decide()

    def test_certification_mode_rejects_non_boolean_values(self):
        session, _ = self.make_session()
        for value in (0, 1, None, "false"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "certification mode"
            ):
                session.decide(certify=value)
