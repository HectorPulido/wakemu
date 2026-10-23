"""Continuation custody across actual shared Registry publication boundaries."""
from copy import deepcopy
import unittest

import test_world_shared
from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_ai.planning import turn_continuation as continuation


MOVE = dict(type="move", path=[[1, 0, 0]])
CAST = dict(type="cast", spellId=77, level=1, targetId=10, target=[0, 0, 0])


def binding(native):
    return continuation.binding(
        native,
        instance="shared-instance-test",
        catalog="c" * 64,
        policy_version="v1",
        policy={},
        source="source",
        root="root",
        request="request",
    )


class SharedContinuationTests(unittest.TestCase):
    def setUp(self):
        # Reuse the established real Registry/participant fixture without
        # duplicating its unrelated test cases.
        test_world_shared.SharedNativeAiTests.setUp(self)

    def test_private_generator_close_preserves_only_later_published_tail(self):
        calls, holders = [], []

        def runner(native):
            holder = continuation.current()
            holders.append(holder)
            calls.append(native)
            if len(calls) == 1:
                source = binding(native)
                native.fight.current.position = (1, 0, 0)
                holder.stage(
                    dict(
                        action=MOVE,
                        plan=[MOVE, CAST],
                        sourceKey="source",
                        rootState="root",
                        requestId="request",
                    ),
                    source,
                    native,
                )
                self.assertIsNone(holder.published)
                self.assertIsNotNone(holder.pending)
                yield [(123, b"native-move")], dict(action=deepcopy(MOVE))
                self.fail("Private runner must be closed after its publication")
            self.assertIsNot(native, calls[0])
            self.assertEqual(
                holder.proposal(native, binding(native))["actions"], [CAST]
            )
            self.assertEqual(self.shared.sequence, 1)
            native.fight.turn_index = 1
            native.awaiting_ack = 9
            yield [(12502, b"native-turn-end")], dict(action=dict(type="end_turn"))

        iterator = run_shared_turn(self.runtime, self.adapter, self.one, runner)
        next(iterator)
        self.assertIsNotNone(holders[0].published)
        self.assertEqual(self.shared.sequence, 1)
        next(iterator)
        with self.assertRaises(StopIteration):
            next(iterator)
        self.assertIsNone(continuation.current())
        self.assertIsNone(holders[0].published)

    def test_rejected_registry_publication_never_confirms_private_tail(self):
        holders = []

        def runner(native):
            holder = continuation.current()
            holders.append(holder)
            holder.stage(
                dict(
                    action=MOVE,
                    plan=[MOVE, CAST],
                    sourceKey="source",
                    rootState="root",
                    requestId="request",
                ),
                binding(native),
                native,
            )
            yield [(123, b"private-move")], dict(action=deepcopy(MOVE))

        def rejected(*args, **kwargs):
            raise RuntimeError("Registry publication failed")

        from unittest.mock import patch

        with patch.object(self.registry, "execute_server", rejected):
            with self.assertRaisesRegex(RuntimeError, "publication failed"):
                list(run_shared_turn(self.runtime, self.adapter, self.one, runner))
        self.assertIsNone(holders[0].published)
        self.assertIsNone(holders[0].pending)
        self.assertEqual(self.shared.sequence, 0)
        self.assertIsNone(continuation.current())


if __name__ == "__main__":
    unittest.main()
