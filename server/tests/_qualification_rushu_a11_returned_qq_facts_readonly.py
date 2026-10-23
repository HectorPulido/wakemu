"""Read original returned glyph constructor evidence without any gameplay."""
import json
from pathlib import Path
import sys
import unittest


class ReadReturnedQqs(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        f = cp["runtime"].fight
        rng = cp["rng"].getstate()
        rows = {}
        for uid in (4881, 4899):
            row = f.native_effect_areas.get(uid)
            if row is None:
                rows[str(uid)] = None
                continue
            values = {
                key: value for key, value in row.items() if key not in ("state_ledger",)
            }
            ledger = row.get("state_ledger")
            values["state_ledger_entries"] = (
                [
                    dict(
                        uid=e.uid,
                        reference=e.reference,
                        level=e.level,
                        caster=getattr(e, "caster_id", None),
                        effect_ids=getattr(e, "effect_ids", None),
                    )
                    for e in ledger.entries
                ]
                if ledger is not None
                else []
            )
            rows[str(uid)] = values
        facts = dict(
            table=f.native_table_turn,
            turn=f.turn_id,
            current=f.current.id,
            rows=rows,
            verification_before=before,
            verification_after=verify(),
            no_actions=True,
        )
        self.assertEqual(cp["rng"].getstate(), rng)
        facts["rng_unchanged"] = True
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-returned-qq-constructor-facts.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadReturnedQqs()])
