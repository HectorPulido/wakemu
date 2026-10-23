"""Read the actual retained ninth-table Qq registry without taking an action."""
import json
from pathlib import Path
import sys
import unittest


class ReadCurrentGround(unittest.TestCase):
    def runTest(self):
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        rt = cp["runtime"]
        f = rt.fight
        rng_before = cp["rng"].getstate()
        self.assertEqual((f.native_table_turn, f.turn_id, f.current.id), (9, 54, 2))
        rows = []
        for uid, row in f.native_effect_areas.items():
            ledger = row.get("state_ledger")
            rows.append(
                dict(
                    uid=uid,
                    reference=row.get("reference"),
                    cell=row.get("cell"),
                    owner_id=row.get("owner_id"),
                    removed=row.get("removed"),
                    states=[
                        dict(
                            reference=e.reference,
                            uid=e.uid,
                            level=e.level,
                            caster=getattr(e, "caster_id", None),
                        )
                        for e in ledger.entries
                    ]
                    if ledger is not None
                    else [],
                    row_level=row.get("level"),
                    native_contract=row.get("native_area_contract"),
                )
            )
        facts = dict(
            table=f.native_table_turn,
            turn=f.turn_id,
            current=f.current.id,
            areas=rows,
            actors={
                str(i): dict(
                    hp=a.hp,
                    position=a.position,
                    stat8=a.effect_stats[8],
                    stats=dict(a.effect_stats),
                )
                for i, a in f.actors.items()
            },
            verification_before=before,
            verification_after=verify(),
            no_actions=True,
        )
        self.assertEqual(cp["rng"].getstate(), rng_before)
        facts["rng_unchanged"] = True
        Path(
            ".runtime/rushu-phase-review-20261021/rushu-a11-actual-t9-ground-registry.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReadCurrentGround()])
