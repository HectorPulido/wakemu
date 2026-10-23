"""Archive the original qualified endpoint and execute its original cleanups."""
import importlib
import json
from pathlib import Path
import unittest


class ArchiveAndReleaseRushu(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_native_party_phase_one")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        verification = recipe.verify_actual_checkpoint()
        self.assertTrue(verification["loaded_implementation_unchanged"])
        from wakfu_server.fight_checkpoint_store import snapshot

        runtime = checkpoint["runtime"]
        current = runtime.fight
        callbacks = len(checkpoint["cleanups"])
        self.assertEqual(callbacks, 3)
        output = Path(
            ".runtime/parallel-readiness-20261021/rushu-full230-qualified-end5-drop-damage-final-release.json"
        )
        facts = dict(
            reason="Preserve genuine components; next earned3M encounter requires the qualified actor-point resolver fix at admission, without replacing a retained implementation",
            table=current.native_table_turn,
            turn=current.turn_id,
            current=current.current.id,
            verification=verification,
            cleanup_callbacks=callbacks,
            final_checkpoint=snapshot(current, runtime=runtime),
            rng_state=checkpoint["rng"].getstate(),
            receipt=checkpoint["receipt"],
            prefix_receipt=checkpoint["receipt_path"],
            continuation_receipt=checkpoint.get("continuation_receipt_path"),
            actual_damage_receipt=checkpoint.get("last_damage_receipt"),
            loaded_implementation=checkpoint["loaded_implementation_description"],
            historical_failures_preserved=True,
            new_admission=False,
            released=False,
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
        recipe.release_actual_checkpoint()
        recipe.RUSHU_HOLD_ACTUAL_CHECKPOINT = False
        self.assertIsNone(recipe.RUSHU_ACTUAL_CHECKPOINT)
        self.assertEqual(checkpoint["cleanups"], [])
        self.assertEqual(checkpoint["fixture"]._cleanups, [])
        facts.update(
            released=True,
            cleanup_callbacks_executed=callbacks,
            retained_scope_empty=True,
        )
        output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ArchiveAndReleaseRushu()])
