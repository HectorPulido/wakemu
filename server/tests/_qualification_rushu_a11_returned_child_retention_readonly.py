"""Read actual retained child contexts without synthesizing a replay context."""
import json
from pathlib import Path
import sys
import unittest


class ReadRetainedChildren(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        v = cp["authorized_service_transition_verifier"]
        before = v()
        rng = cp["rng"].getstate()
        f = cp["runtime"].fight
        records = getattr(f, "native_retained_records", {})
        facts = dict(
            table=f.native_table_turn,
            turn=f.turn_id,
            current=f.current.id,
            records={str(uid): records.get(uid) for uid in (10072, 10078)},
            relevant_names=[
                name
                for name in vars(f)
                if "retained" in name or "native_effect" in name
            ],
            no_actions=True,
            verification_before=before,
            verification_after=v(),
        )
        self.assertEqual(cp["rng"].getstate(), rng)
        facts["rng_unchanged"] = True
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-returned-qq-retained-child-facts.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadRetainedChildren()])
