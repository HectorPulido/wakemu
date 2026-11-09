from copy import deepcopy
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_entry


class _Runtime:
    def __init__(self):
        self.fight = SimpleNamespace(
            phase="active",
            current=SimpleNamespace(id=-7, position=(0, 0, 0)),
            turn_id=1,
        )
        self.awaiting_ack = None
        self.pending = []
        self.ends = 0

    def end_server_turn(self, actor_id, turn_id):
        self.ends += 1
        self.awaiting_ack = turn_id
        return [(9000, b"end")]


class _Oracle:
    def __init__(self, runtime):
        self.runtime = runtime
        self.identity = "source-1"
        self.identity_calls = 0
        self.commits = []

    def state_identity(self, runtime):
        self.identity_calls += 1
        return self.identity

    def commit(self, action, *, stats_serializer):
        self.commits.append(deepcopy(action))
        if action["type"] == "end_turn":
            return self.runtime.end_server_turn(-7, 1)
        return [(12588, b"action")]


class _Transport:
    def __init__(self, callback):
        self.callback = callback
        self.requests = []

    def request(self, endpoint, request, *, deadline):
        self.requests.append(deepcopy(request))
        return self.callback(request, len(self.requests))


def _snapshot(oracle, *, excluded_actions=(), budget_ms=500):
    identity = oracle.state_identity(oracle.runtime)
    oracle.state_identity(oracle.runtime)
    return dict(
        protocol=1,
        source={"nativeIdentity": identity},
        board={"fixture": "compact"},
        native={},
        limits={"maxActions": 1},
    )


def _reply(request, action):
    return 200, dict(
        protocol=1,
        requestId=request["requestId"],
        source=deepcopy(request["source"]),
        action=action,
        alternatives=[],
    )


class FinalSnapshotIdentityTests(unittest.TestCase):
    def drive(self, oracle, transport):
        with patch.object(jondo_entry, "build_snapshot", _snapshot):
            return list(
                jondo_entry.run_prepared_turn(
                    oracle.runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 5,
                    max_actions=1,
                )
            )

    def test_snapshot_identity_is_reused_after_reply_with_same_action_packets(self):
        runtime = _Runtime()
        oracle = _Oracle(runtime)
        action = {"type": "end_turn"}
        transport = _Transport(lambda request, _count: _reply(request, action))

        deliveries = self.drive(oracle, transport)

        # Build retains its initial/final checks. The caller's post-reply
        # identity becomes the before-action guard, removing the old fourth
        # whole-graph fingerprint without changing the chosen packet.
        self.assertEqual(oracle.identity_calls, 3)
        self.assertEqual(oracle.commits, [action])
        self.assertEqual(runtime.ends, 1)
        self.assertEqual(deliveries[0][0], [(9000, b"end")])
        self.assertEqual(transport.requests[0]["source"]["nativeIdentity"], "source-1")
        self.assertEqual(transport.requests[0]["board"], {"fixture": "compact"})

    def test_mutation_during_snapshot_or_planner_cannot_reach_commit(self):
        runtime = _Runtime()
        oracle = _Oracle(runtime)

        def stale_snapshot(current_oracle, **kwargs):
            request = _snapshot(current_oracle, **kwargs)
            current_oracle.identity = "source-2"
            return request

        with patch.object(jondo_entry, "build_snapshot", stale_snapshot):
            with self.assertRaisesRegex(ValueError, "Native source changed"):
                list(
                    jondo_entry.run_prepared_turn(
                        runtime,
                        oracle,
                        object(),
                        _Transport(
                            lambda request, _count: _reply(
                                request, {"type": "end_turn"}
                            )
                        ),
                        deadline=time.monotonic() + 5,
                        max_actions=1,
                    )
                )
        self.assertEqual(oracle.commits, [])
        self.assertEqual(runtime.ends, 0)

    def test_planner_retry_checks_source_before_reusing_snapshot(self):
        runtime = _Runtime()
        oracle = _Oracle(runtime)

        def stale_busy_reply(request, count):
            oracle.identity = "source-2"
            return 503, {"error": "busy"}

        transport = _Transport(stale_busy_reply)
        with patch.object(jondo_entry, "build_snapshot", _snapshot):
            with self.assertRaisesRegex(ValueError, "Native source changed"):
                list(
                    jondo_entry.run_prepared_turn(
                        runtime,
                        oracle,
                        object(),
                        transport,
                        deadline=time.monotonic() + 5,
                        max_actions=1,
                    )
                )
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(oracle.commits, [])

    def test_custom_reply_keeps_per_candidate_identity_fingerprint(self):
        class CustomAction(dict):
            pass

        runtime = _Runtime()
        oracle = _Oracle(runtime)
        action = CustomAction(type="end_turn")
        transport = _Transport(lambda request, _count: _reply(request, action))
        self.drive(oracle, transport)
        # Two build checks, the reply check, and conservative custom fallback.
        self.assertEqual(oracle.identity_calls, 4)

    def test_reuse_is_consumed_before_first_commit_attempt(self):
        runtime = _Runtime()
        oracle = _Oracle(runtime)
        rejected = {"type": "cast", "spellId": 99}
        accepted = {"type": "cast", "spellId": 7}

        def commit(action, *, stats_serializer):
            oracle.commits.append(deepcopy(action))
            if action["spellId"] == 99:
                raise ValueError("native reject")
            return [(12588, b"native")]

        oracle.commit = commit
        transport = _Transport(
            lambda request, _count: (
                200,
                dict(
                    protocol=1,
                    requestId=request["requestId"],
                    source=deepcopy(request["source"]),
                    action=rejected,
                    alternatives=[accepted],
                ),
            )
        )
        deliveries = self.drive(oracle, transport)

        # Snapshot's two guards, reply guard, rejection recheck, then a fresh
        # candidate guard. The stale reply identity is consumed at the first
        # attempted commit and cannot be reused for the alternative.
        self.assertEqual(oracle.identity_calls, 5)
        self.assertEqual(oracle.commits, [rejected, accepted])
        self.assertEqual(deliveries[0][0], [(12588, b"native")])

    def test_custom_validator_replacement_disables_identity_reuse(self):
        runtime = _Runtime()
        oracle = _Oracle(runtime)
        action = {"type": "end_turn"}
        transport = _Transport(lambda request, _count: _reply(request, action))
        original = jondo_entry.action_key

        def compatible_action_key(value):
            return original(value)

        with patch.object(jondo_entry, "action_key", compatible_action_key):
            self.drive(oracle, transport)
        self.assertEqual(oracle.identity_calls, 4)

    def test_json_tree_cycles_and_excessive_depth_fall_back_without_raising(self):
        cyclic = []
        cyclic.append(cyclic)
        deep = current = []
        for _ in range(80):
            child = []
            current.append(child)
            current = child
        self.assertFalse(jondo_entry._exact_json_tree(cyclic))
        self.assertFalse(jondo_entry._exact_json_tree(deep))


if __name__ == "__main__":
    unittest.main()
