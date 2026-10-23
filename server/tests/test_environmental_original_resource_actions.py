"""Complete original resource/action source joins without gameplay activation."""
import json
from collections import Counter
from pathlib import Path

from postgres_case import PostgresCase
from build_environmental_resource_actions import (
    digest,
    REVISION,
    RESOURCE_SHA,
    SEED_SHA,
)


class EnvironmentalOriginalResourceActionTests(PostgresCase):
    def test_all_313_native_scenarios_preserve_exact_stage_actions_and_eight_missing_stages(
        self,
    ):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        original = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
            ).read_text()
        )
        resources = {
            r["resource_reference"]: r
            for r in native_catalog.load(DATA_ROOT / "plant-resources.json")
        }
        seeds = native_catalog.load(DATA_ROOT / "seed-actions.json")
        expected, actions, refs = {}, {}, set()
        for row in original["scenarios"]:
            values = {key.lower(): value for key, value in row["configuration"].items()}
            if "ressourcerefid" not in values:
                continue
            ref, step = int(values["ressourcerefid"]), int(values["ressourcestep"])
            refs.add(ref)
            matches = [
                s for s in resources[ref]["stage_definitions"] if s["stage_id"] == step
            ]
            self.assertLessEqual(len(matches), 1)
            native_actions = [] if not matches else matches[0]["actions"]
            self.assertLessEqual(len(native_actions), 1)
            matched = bool(native_actions)
            expected[row["id"]] = (
                ref,
                step,
                0 if matched else None,
                "matched_original_action" if matched else "missing_original_stage",
            )
            if matched:
                actions[(ref, step, 0)] = native_actions[0]
        self.assertEqual((len(expected), len(refs), len(actions)), (313, 80, 78))
        self.assertFalse(any(r["resource_reference"] in refs for r in seeds))
        with self.store.connection() as db:
            bound = db.execute(
                "SELECT * FROM environmental_scenario_resource_actions"
            ).fetchall()
            self.assertEqual(
                {
                    r["scenario_id"]: (
                        r["resource_reference"],
                        r["native_step"],
                        r["action_ordinal"],
                        r["status"],
                    )
                    for r in bound
                },
                expected,
            )
            self.assertEqual(
                Counter(r["status"] for r in bound),
                dict(matched_original_action=305, missing_original_stage=8),
            )
            saved_resources = db.execute(
                "SELECT * FROM environmental_original_resources"
            ).fetchall()
            self.assertEqual({r["resource_reference"] for r in saved_resources}, refs)
            for row in saved_resources:
                self.assertEqual(
                    row["original_record"], resources[row["resource_reference"]]
                )
                self.assertEqual(
                    row["record_sha256"], digest(resources[row["resource_reference"]])
                )
            saved_actions = db.execute(
                "SELECT * FROM environmental_original_resource_actions"
            ).fetchall()
            self.assertEqual(len(saved_actions), 78)
            for row in saved_actions:
                native = actions[
                    (
                        row["resource_reference"],
                        row["native_step"],
                        row["action_ordinal"],
                    )
                ]
                self.assertEqual(row["original_action"], native)
                self.assertEqual(row["action_sha256"], digest(native))
                for field in (
                    "action_id",
                    "profession_id",
                    "minimum_level",
                    "duration_ms",
                    "item_reference",
                    "product_references",
                    "raw_getters",
                ):
                    self.assertEqual(row[field], native[field])
                self.assertEqual(row["native_criteria"], native["criteria"])
            self.assertEqual(
                Counter(r["raw_getters"]["csR"] for r in saved_actions),
                {False: 43, True: 35},
            )
            self.assertEqual({r["raw_getters"]["cvF"] for r in saved_actions}, {0})
            self.assertEqual({r["profession_id"] for r in saved_actions}, {0})
            self.assertEqual(sum(r["duration_ms"] == 2 for r in saved_actions), 1)
            self.assertEqual(sum(bool(r["item_reference"]) for r in saved_actions), 1)
            manifest = db.execute(
                "SELECT * FROM environmental_resource_action_source_versions"
            ).fetchone()
            self.assertFalse(manifest["server_activation_authorized"])
            self.assertEqual(manifest["catalog_revision"], native_catalog.release())
            self.assertEqual(manifest["catalog_revision"], REVISION)
            hashes = native_catalog.document_hashes()
            self.assertEqual(
                (
                    manifest["resource_document_sha256"],
                    manifest["seed_document_sha256"],
                ),
                (hashes["plant-resources.json"], hashes["seed-actions.json"]),
            )
            self.assertEqual(
                (RESOURCE_SHA, SEED_SHA),
                (hashes["plant-resources.json"], hashes["seed-actions.json"]),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            with self.assertRaisesRegex(Exception, "append-only"), db.transaction():
                db.execute(
                    "UPDATE environmental_original_resource_actions SET profession_id=1"
                )
