"""Archive the genuine two-Polary KO, then release the scoped Nox Store."""
import json, sys, unittest
from pathlib import Path


class ReleasePaidKo(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_nox_prelude_five_modes_and_polary"]
        self.assertEqual(len(recipe.retained_components), 1)
        record = recipe.retained_components[0]
        case = record["case"]
        fight = case.fight
        verification = recipe.verify_retained_component(record)
        self.assertTrue(verification["loaded_implementation_unchanged"])
        from wakfu_server.fight_checkpoint_store import snapshot

        archive = dict(
            reason="Root closes component scope: native two-Polary paid KO proven; unrelated AP fanout bug prevents3M certification. No retry of3AP sample.",
            final_checkpoint=snapshot(fight, runtime=case.runtime),
            rng_state=case.rng.getstate(),
            original_recipe_sha256=record["loaded_recipe_sha256"],
            verification=verification,
            attestation=sys.modules[
                "_nox_loaded_implementation_checkpoint_v2_canonical"
            ].describe(record["loaded_code_attestation"]),
            receipt=record["receipt"],
            cleanup_callbacks=len(record["cleanups"]),
            current=dict(
                table=fight.native_table_turn,
                turn=fight.turn_id,
                actor=fight.current.id,
            ),
            saved_record_fields={
                key: value
                for key, value in record.items()
                if key
                not in (
                    "case",
                    "runtime",
                    "fight",
                    "store",
                    "fixture",
                    "cleanups",
                    "rng",
                    "checkpoint",
                    "rng_state",
                    "loaded_code_attestation",
                    "loaded_code_roots",
                    "receipt",
                    "last_loaded_code_verification",
                )
                and isinstance(
                    value, (dict, list, tuple, str, int, float, bool, type(None))
                )
            },
            no_new_actions=True,
            full_victory=False,
        )
        output = Path(
            ".runtime/parallel-readiness-20261021/nox-native-prelude-two-paid-polary-ko-final-archive-release.json"
        )
        output.write_text(json.dumps(archive, indent=2, default=str) + "\n")
        recipe.release_retained_components()
        recipe.RETAIN_COMPONENT = False
        self.assertEqual(recipe.retained_components, [])
        self.assertEqual(record["fixture"]._cleanups, [])
        archive.update(
            released=True,
            retained_components_empty=True,
            cleanup_callbacks_executed=archive["cleanup_callbacks"],
            retain_component=False,
        )
        output.write_text(json.dumps(archive, indent=2, default=str) + "\n")
        rushu = sys.modules["test_rushu_native_party_phase_one"]
        self.assertTrue(
            rushu.verify_actual_checkpoint()["loaded_implementation_unchanged"]
        )


def qualify():
    return unittest.TestSuite([ReleasePaidKo()])
