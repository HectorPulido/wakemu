"""A timed out service RPC can only recover a recertified source-bound action."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_native_session import make_runtime, StubOracle, StubTransport
from wakfu_ai.bridge.world_bridge import NativeSession
from wakfu_ai.native.native_deadline import bounded, check, remaining


MOVE = dict(type="move", path=[[1, 0, 0]])


class PartialDecisionTests(unittest.TestCase):
    def fixture(
        self,
        *,
        change_snapshot=None,
        rejection=False,
        owner_expiry=False,
        source_change=False,
        no_certificate=False,
        late_decided=False
    ):
        value = make_runtime()
        oracle = StubOracle(value)
        now, allowances = [0.0], []

        class Transport(StubTransport):
            calls = 0

            def _retry_request(transport, endpoint, payload):
                self.assertEqual(endpoint, "/v3/decide")
                transport.calls += 1
                allowances.append(remaining())
                if no_certificate or transport.calls == 3:
                    now[0] = 1.3 if owner_expiry else 0.7
                    if source_change:
                        value.fight.current.hp -= 1
                    if late_decided:
                        return dict(
                            status="decided",
                            decision=dict(
                                protocol=3,
                                requestId=session.request_id,
                                sourceKey=session.source,
                                rootState=session.root,
                                action=dict(type="cast", spellId=999),
                                plan=[],
                            ),
                        )
                    check()
                    raise TimeoutError("synthetic service timeout")
                query = dict(
                    id=str(transport.calls),
                    operation="preview" if transport.calls == 1 else "repertoire",
                    state=session.root,
                )
                reply = dict(
                    status="query",
                    requestId=session.request_id,
                    sourceKey=session.source,
                    queries=[query],
                )
                if transport.calls == 1:
                    query["action"] = deepcopy(MOVE)
                else:
                    candidate = dict(
                        protocol=3,
                        requestId=session.request_id,
                        sourceKey=session.source,
                        rootState=session.root,
                        action=deepcopy(MOVE),
                        plan=[deepcopy(MOVE)],
                        partial=True,
                        unknownDependencies=["native_search_budget_partial"],
                    )
                    if change_snapshot is not None:
                        candidate = change_snapshot(candidate)
                    reply["incumbent"] = candidate
                return reply

        transport = Transport()
        session = NativeSession(
            oracle,
            transport,
            object(),
            policy={},
            policy_version="test",
            fight_instance_id="partial-test",
        )

        def describe(key):
            runtime = session.states[key]
            return dict(
                key=key,
                nativeContext=key,
                currentId=runtime.fight.current.id,
                turnId=runtime.fight.turn_id,
                stateRevision=runtime.fight.sequence,
            )

        session.describe = describe
        original = oracle.preview

        def preview(runtime, action):
            if rejection and oracle.preview_calls:
                raise ValueError("current native rule rejected recertification")
            return original(runtime, action)

        oracle.preview = preview

        def native_query(operation, key, query):
            if operation == "preview":
                private, _, _ = oracle.preview(session.states[key], query["action"])
                return describe(session.register(private))
            return dict(nativeMetadata=session.root)

        session._query = native_query
        return value, oracle, transport, session, now, allowances

    def test_rpc_timeout_keeps_last_certified_action_and_recertifies_even_when_disabled(
        self,
    ):
        value, oracle, transport, session, now, allowances = self.fixture()
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
            self.assertAlmostEqual(remaining(), 0.5)
        self.assertTrue(result["partial"])
        self.assertTrue(session.needs_cleanup)
        self.assertEqual(result["action"], MOVE)
        self.assertEqual(result["plan"], [MOVE])
        self.assertEqual(len(oracle.preview_calls), 2)
        self.assertEqual(transport.calls, 3)
        self.assertTrue(all(allowance <= 0.7 for allowance in allowances))
        self.assertEqual(value.fight.current.position, (0, 0, 0))
        self.assertEqual(value.fight.current.mp, 3)
        self.assertEqual(result["sourceKey"], session.source)

    def test_foreign_replayed_and_malformed_snapshots_do_not_authorize_fallback(self):
        corruptions = [
            lambda value: dict(value, requestId="old-request"),
            lambda value: dict(value, sourceKey="f" * 64),
            lambda value: dict(value, rootState="foreign-root"),
            lambda value: dict(value, protocol=True),
            lambda value: dict(value, partial=False),
            lambda value: dict(value, plan=[MOVE, MOVE]),
            lambda value: dict(
                value,
                action=dict(type="move", path=[[2, 0, 0]]),
                plan=[dict(type="move", path=[[2, 0, 0]])],
            ),
            lambda value: dict(value, unknownDependencies=[]),
            lambda value: None,
        ]
        for corruption in corruptions:
            with self.subTest(corruption=corruption):
                value, oracle, transport, session, now, _ = self.fixture(
                    change_snapshot=corruption
                )
                with bounded(1.2, clock=lambda: now[0]):
                    result = session.decide(certify=False)
                self.assertEqual(result["action"], dict(type="end_turn"))
                self.assertEqual(len(oracle.preview_calls), 1)
                self.assertEqual(value.fight.current.mp, 3)

    def test_recertification_rejection_falls_back_to_end_turn(self):
        value, oracle, _, session, now, _ = self.fixture(rejection=True)
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertIn(
            "native_partial_action_recertification_rejected",
            result["unknownDependencies"],
        )
        self.assertEqual(value.fight.current.mp, 3)

    def test_real_owner_expiry_does_not_resurrect_an_earlier_snapshot(self):
        _, oracle, _, session, now, _ = self.fixture(owner_expiry=True)
        with bounded(1.2, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                session.decide(certify=False)
        self.assertEqual(len(oracle.preview_calls), 1)

    def test_source_change_during_timed_out_rpc_remains_fatal(self):
        _, oracle, _, session, now, _ = self.fixture(source_change=True)
        with bounded(1.2, clock=lambda: now[0]):
            with self.assertRaisesRegex(ValueError, "source changed"):
                session.decide(certify=False)
        self.assertEqual(len(oracle.preview_calls), 1)

    def test_no_certified_snapshot_returns_end_turn_without_inventing_action(self):
        value, oracle, _, session, now, _ = self.fixture(no_certificate=True)
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertEqual(oracle.preview_calls, [])
        self.assertEqual(value.fight.current.mp, 3)

    def test_late_complete_reply_cannot_replace_the_previously_certified_snapshot(self):
        _, oracle, _, session, now, _ = self.fixture(late_decided=True)
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertTrue(result["partial"])
        self.assertEqual(result["action"], MOVE)
        self.assertEqual(len(oracle.preview_calls), 2)

    def test_network_elapsed_time_cannot_restart_a_frozen_risk_allowance(self):
        _, _, transport, session, now, _ = self.fixture()
        original_rpc, original_query = transport._retry_request, session._query
        observed = []

        def delayed_rpc(endpoint, payload):
            reply = original_rpc(endpoint, payload)
            if transport.calls == 2:
                now[0] = 0.4
                reply["queries"][0]["searchAllowanceMs"] = 500
            return reply

        def inspect_query(operation, key, query):
            if operation == "repertoire":
                observed.append(remaining())
            return original_query(operation, key, query)

        transport._retry_request, session._query = delayed_rpc, inspect_query
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], MOVE)
        self.assertEqual(len(observed), 1)
        self.assertAlmostEqual(observed[0], 0.1)

    def test_explicit_risk_phase_reset_retires_an_earlier_raw_incumbent(self):
        _, oracle, transport, session, now, _ = self.fixture()
        original = transport._retry_request

        def risk_phase(endpoint, payload):
            if transport.calls < 2:
                return original(endpoint, payload)
            transport.calls += 1
            if transport.calls == 3:
                return dict(
                    status="query",
                    requestId=session.request_id,
                    sourceKey=session.source,
                    incumbent=None,
                    queries=[
                        dict(id="risk:1", operation="repertoire", state=session.root)
                    ],
                )
            now[0] = 0.7
            check()
            raise TimeoutError("risk phase response timeout")

        transport._retry_request = risk_phase
        with bounded(1.2, clock=lambda: now[0]):
            result = session.decide(certify=False)
        self.assertEqual(result["action"], dict(type="end_turn"))
        self.assertEqual(len(oracle.preview_calls), 1)


if __name__ == "__main__":
    unittest.main()
