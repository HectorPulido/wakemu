"""Archive an authentic native defeat and run its three original cleanups."""
import json
from pathlib import Path
import sys
import unittest


class ArchiveNoxNativeDefeat(unittest.TestCase):
    def runTest(self):
        m = sys.modules["test_nox_full_party_victory_v4"]
        r = m.retained_components[0]
        verify = r["authorized_scoped_policy_transition_verifier"]
        cp = sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT
        rv = cp["authorized_service_transition_verifier"]
        rushu_before = rv()
        c = r["case"]
        f = c.fight
        self.assertEqual(f.phase, "finished")
        self.assertEqual((f.native_table_turn, f.turn_id), (11, 114))
        self.assertEqual(len(r["cleanups"]), 3)
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.maps.boss_score_runtime import staged_score

        facts = dict(
            classification="Authentic native END11 defeat; three-million player victory unfulfilled",
            phase=f.phase,
            winner=f.winner,
            table=f.native_table_turn,
            turn=f.turn_id,
            score=staged_score(f),
            final_snapshot=snapshot(f, runtime=c.runtime),
            rng_state=c.rng.getstate(),
            receipt=r["receipt"],
            terminal_receipt=r.get("post_auspice_native_terminal_calendar"),
            nox_verification_final=verify(r),
            rushu_verification_before=rushu_before,
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
            cleanup_callbacks=3,
            no_gameplay_actions=True,
            released=False,
        )
        p = Path(
            ".runtime/parallel-readiness-20261021/nox-v4-native-end11-defeat-qualified-final-release.json"
        )
        p.write_text(json.dumps(facts, indent=2, default=str) + "\n")
        m.release_retained_components()
        m.RETAIN_COMPONENT = False
        self.assertEqual(m.retained_components, [])
        self.assertEqual(r["fixture"]._cleanups, [])
        self.assertEqual(r["cleanups"], [])
        self.assertIs(
            sys.modules["test_rushu_dd230_eleven_slot_opening"].RUSHU_ACTUAL_CHECKPOINT,
            cp,
        )
        facts.update(
            released=True,
            cleanup_callbacks_executed=3,
            retained_scope_empty=True,
            rushu_verification_after=rv(),
        )
        p.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ArchiveNoxNativeDefeat()])
