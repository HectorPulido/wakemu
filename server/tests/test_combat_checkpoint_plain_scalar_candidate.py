"""Exact-scalar-first checkpoint conversion preserves existing authority."""

from contextlib import ExitStack
from dataclasses import dataclass
import inspect
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import fight_checkpoint_store as checkpoints
from wakfu_server.characters.owned_social_context import OwnedSocialContext
from wakfu_server.combat_carrying import NativeCarryPair
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_instance_level_group import InstanceDifficultySnapshot
from wakfu_server.combat_state_ledger import StateLedger


def scalar_first_candidate():
    source = inspect.getsource(checkpoints._plain)
    signature = "def _plain(value):\n"
    if not source.startswith(signature):
        raise AssertionError("Checkpoint converter source shape changed")
    candidate_source = source.replace(
        signature,
        signature
        + "    if value is None or type(value) in (str, int, float, bool):\n"
        + "        return value\n",
        1,
    )
    scope = dict(checkpoints.__dict__)
    exec(
        compile(candidate_source, "<exact-scalar-first-checkpoint-test>", "exec"), scope
    )
    return scope["_plain"]


class CheckpointPlainScalarCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = staticmethod(checkpoints._plain)
        cls.candidate = staticmethod(scalar_first_candidate())

    def test_exact_primitives_keep_identity(self):
        values = (None, "text", 0, 1 << 60, 1.25, True, False)
        for function in (self.baseline, self.candidate):
            for value in values:
                with self.subTest(function=function.__name__, value=value):
                    self.assertIs(function(value), value)

    def test_primitive_subclasses_and_unattested_objects_stay_rejected(self):
        class IntSubclass(int):
            pass

        class StrSubclass(str):
            pass

        @dataclass
        class UnknownRecord:
            value: int

        values = (IntSubclass(7), StrSubclass("seven"), UnknownRecord(7), object())
        for function in (self.baseline, self.candidate):
            for value in values:
                with self.subTest(
                    function=function.__name__, value=type(value).__name__
                ):
                    with self.assertRaisesRegex(ValueError, "nonserializable"):
                        function(value)

    def typed_graph(self):
        book = CopyBookAction((7 << 32) | 6266, 6266, 20, False, True, False)
        ledger = StateLedger(7)
        values = {
            "social": OwnedSocialContext(
                actor_id=7,
                account_id=9,
                nation_id=30,
                guild_id=None,
                guild_level=0,
                source_revision="candidate-test-r1",
            ),
            "carry": NativeCarryPair(7, 8, (2, 3, 0), 1, 2, 19, 144),
            "book": book,
            "instance": InstanceDifficultySnapshot(7, None, "fBg.drG.Optional.empty"),
            "ledger": ledger,
        }
        fight = SimpleNamespace(actors={}, typed_authority=values)
        return fight, values

    def test_typed_nested_checkpoint_graph_matches_baseline_json(self):
        fight, typed = self.typed_graph()
        self.assertIsInstance(typed["carry"], NativeCarryPair)
        self.assertIsInstance(typed["book"], CopyBookAction)
        self.assertIsInstance(typed["instance"], InstanceDifficultySnapshot)
        self.assertIsInstance(typed["ledger"], StateLedger)
        with ExitStack() as stack:
            stack.enter_context(patch.object(checkpoints, "_plain", self.baseline))
            baseline = checkpoints.snapshot(fight)
        with ExitStack() as stack:
            stack.enter_context(patch.object(checkpoints, "_plain", self.candidate))
            candidate = checkpoints.snapshot(fight)
        self.assertEqual(baseline, candidate)
        self.assertEqual(
            json.dumps(baseline, sort_keys=True, separators=(",", ":")),
            json.dumps(candidate, sort_keys=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()
