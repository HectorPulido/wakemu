"""Archive both authorized live scopes without any gameplay action."""
import importlib
import json
import sys
import unittest
from pathlib import Path


class ArchiveBothAuthorizedScopes(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_early_score"]
        record = nox.retained_components[0]
        verify = record["authorized_uid_transition_verifier"]
        nox_before = verify(record)
        rushu = importlib.import_module(
            "_qualification_rushu_dd230_archive_and_release"
        )
        result = unittest.TestResult()
        rushu.qualify().run(result)
        self.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))
        nox_after_rushu = verify(record)
        case = record["case"]
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.maps.boss_score_runtime import staged_score

        callbacks = len(record["cleanups"])
        facts = dict(
            classification="Archived incomplete encounter; no native terminal or victory claimed",
            no_gameplay_actions=True,
            no_new_admission=True,
            phase=case.fight.phase,
            table=case.fight.native_table_turn,
            turn=case.fight.turn_id,
            current=case.fight.current.id,
            score=staged_score(case.fight),
            final_checkpoint=snapshot(case.fight, runtime=case.runtime),
            rng_state=case.rng.getstate(),
            receipt=record["receipt"],
            prior_recovery=record.get("observer_only_interruption_recovery"),
            verification_before=nox_before,
            verification_after_rushu=nox_after_rushu,
            verification_final=verify(record),
            cleanup_callbacks=callbacks,
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
            released=False,
        )
        output = Path(
            ".runtime/parallel-readiness-20261021/nox-full-native-t15-incomplete-qualified-final-release.json"
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
        nox.release_retained_components()
        nox.RETAIN_COMPONENT = False
        self.assertEqual(nox.retained_components, [])
        self.assertEqual(record["fixture"]._cleanups, [])
        self.assertEqual(record["cleanups"], [])
        facts.update(
            released=True,
            cleanup_callbacks_executed=callbacks,
            retained_scope_empty=True,
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ArchiveBothAuthorizedScopes()])
