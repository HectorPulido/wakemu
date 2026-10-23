"""Preserve authentic component evidence then close the unrecoverable paid scope."""
import json, sys, unittest
from pathlib import Path


class ReleaseNox(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_nox_cube24_fixed12_joint"]
        self.assertEqual(len(recipe.retained_components), 1)
        record = recipe.retained_components[0]
        verification = recipe.verify_retained_component(record)
        self.assertTrue(verification["loaded_implementation_unchanged"])
        from wakfu_server.fight_checkpoint_store import snapshot

        case = record["case"]
        fight = case.fight
        output = Path(
            ".runtime/parallel-readiness-20261021/nox-fixed12-qualified-components-final-release.json"
        )
        row = dict(
            reason="CSV requires paid Polary kill, AP and actual-profile 3M; table5 has no8977 or Polary and producer ended3",
            table=fight.native_table_turn,
            turn=fight.turn_id,
            current=fight.current.id,
            loaded_recipe_sha256=record["loaded_recipe_sha256"],
            verification=verification,
            cleanup_callbacks=len(record["cleanups"]),
            final_checkpoint=snapshot(fight, runtime=case.runtime),
            rng_state=case.rng.getstate(),
            receipt=record["receipt"],
            paid_rotation_qualification=record.get("paid_rotation_qualification"),
            ebony_polary_continuation=record.get("ebony_polary_continuation"),
            attestation=sys.modules["_nox_loaded_implementation_checkpoint"].describe(
                record["loaded_code_attestation"]
            ),
            historical_unittest_failure_preserved=True,
            new_admission=False,
        )
        output.write_text(json.dumps(row, indent=2, default=str) + "\n")
        recipe.release_retained_components()
        recipe.RETAIN_COMPONENT = False
        self.assertEqual(recipe.retained_components, [])
        self.assertEqual(record["fixture"]._cleanups, [])
        row.update(
            released=True,
            retained_components_empty=True,
            cleanup_callbacks_executed=row["cleanup_callbacks"],
            retain_component=False,
        )
        output.write_text(json.dumps(row, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ReleaseNox()])
