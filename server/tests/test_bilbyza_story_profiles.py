"""Bilbyza regional story declarations remain tied to native sources."""

import json
import os
from pathlib import Path
import unittest

from wakfu_server import generic_transports
from wakfu_server.achievements import mission_toolkit_contract
from wakfu_server.combat_geometry import published_geometry
from wakfu_server import monsters
from wakfu_server.owned_story_configuration import compile_story
from wakfu_server.storage.postgres import Database


ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "wakfu_server/maps/owned_story_profiles"
ACHIEVEMENTS = ROOT / "wakfu_server/achievements"


def load(path):
    return json.loads(path.read_text())


class BilbyzaStoryProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("WAKFU_DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "WAKFU_DATABASE_URL is required for native-source validation"
            )
        database = Database(
            dsn,
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
            min_size=1,
            max_size=1,
        )
        try:
            with database.connection() as db:
                revision = db.execute(
                    "SELECT revision FROM native_quest_metadata_releases "
                    "ORDER BY imported_at DESC LIMIT 1"
                ).fetchone()["revision"]
                rows = db.execute(
                    "SELECT definition_id,data FROM native_quest_metadata_definitions "
                    "WHERE revision=%s AND definition_id=ANY(%s)",
                    (revision, [1260, 1261, 1262, 1263, 1264]),
                ).fetchall()
            cls.native = {row["definition_id"]: row["data"]["native"] for row in rows}
        finally:
            database.close()

    def test_native_mission_and_kiosk_contracts_preserve_finite_progression(self):
        profile = load(ACHIEVEMENTS / "mission_profiles/bilbyza-85-introduction.json")
        mission_toolkit_contract.validate(profile, self.native)
        self.assertEqual(
            [row["quest_id"] for row in profile["activations"]],
            [1260, 1260, 1261, 1262, 1263],
        )
        self.assertFalse(any(row["quest_id"] == 1264 for row in profile["activations"]))
        self.assertEqual(
            [
                (row["quest_id"], row["event"]["reference"])
                for row in profile["activations"]
                if row["event"]["kind"] == "quest_completed"
            ],
            [(1261, 1260), (1262, 1261), (1263, 1262)],
        )

        native_kiosk = load(ACHIEVEMENTS / "quest_interactions/bilbyza-kiosk.json")
        kiosk = native_kiosk["bindings"][0]
        self.assertEqual(
            (
                kiosk["map_id"],
                kiosk["object_id"],
                kiosk["quest_id"],
                kiosk["objective_id"],
            ),
            (458, 18974, 1260, 2389),
        )
        self.assertEqual(kiosk["native_effect_reference"], 2537)
        self.assertEqual(
            kiosk["native_criterion"],
            "GetRealLevel()>=85 && GetItemQuantity(17515) == 0 && not IsAchievementComplete(1260)",
        )
        generic = load(
            ROOT / "wakfu_server/maps/native_generic_profiles/bilbyza-kiosk.json"
        )
        effects = generic["entries"][0]["program"]["groups"][0]["actions"][0]["effects"]
        by_effect = {row["action_reference"]: row for row in effects}
        self.assertEqual(set(by_effect), {359, 369, 492, 2537})
        self.assertEqual(by_effect[492]["parameters"], ["2316"])
        self.assertEqual(
            by_effect[492]["criterion"],
            "GetRealLevel()>=85 && GetItemQuantity(17515) == 0 && IsAchievementComplete(1260)",
        )

    def test_party_and_raft_compile_against_original_geometry_transports_and_monsters(
        self,
    ):
        sources = {
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        }
        manifest = load(MAPS / "bilbyza-party-560.instance.json")
        controller = load(MAPS / manifest["controller_file"])
        encounters = load(MAPS / manifest["encounters_file"])
        exploration = load(MAPS / manifest["exploration_file"])
        compiled = compile_story(
            manifest,
            controller=controller,
            encounters=encounters,
            geometry=published_geometry(560),
            exploration=exploration,
            sources=sources,
            monster=monsters.reference,
        )
        self.assertEqual(compiled, load(MAPS / "bilbyza-party-560.configuration.json"))
        self.assertEqual(
            (
                compiled["route"]["entry_map_id"],
                compiled["route"]["entry_object_id"],
                compiled["route"]["destination_id"],
            ),
            (458, 19114, 1227),
        )
        roster = compiled["compiled_plan"]["rooms"][0]["monsters"]
        self.assertEqual(
            [(row["ref_id"], row["count"]) for row in roster],
            [(2519, 1), (2520, 1), (2521, 1), (2648, 2)],
        )
        self.assertTrue(
            all(row["native_min_level"] == row["native_max_level"] for row in roster)
        )
        self.assertEqual(compiled["topology"]["physical_exit_objects"], [])
        self.assertEqual(
            [
                (row["source_id"], row["destination_id"])
                for row in compiled["topology"]["native_story_exits"]
            ],
            [(19115, 1226)],
        )

        raft_manifest = load(MAPS / "bilbyza-raft-557.instance.json")
        raft_controller = load(MAPS / raft_manifest["controller_file"])
        raft_exploration = load(MAPS / raft_manifest["exploration_file"])
        raft = compile_story(
            raft_manifest,
            controller=raft_controller,
            encounters=None,
            geometry=published_geometry(557),
            exploration=raft_exploration,
            sources=sources,
            monster=None,
        )
        self.assertEqual(raft, load(MAPS / "bilbyza-raft-557.configuration.json"))
        self.assertEqual(
            (
                raft["route"]["entry_map_id"],
                raft["route"]["entry_object_id"],
                raft["route"]["destination_id"],
            ),
            (458, 18981, 1289),
        )
        self.assertEqual(raft["compiled_plan"]["rooms"], [])
        self.assertEqual(
            [
                (row["source_id"], row["destination_id"])
                for row in raft["topology"]["native_story_exits"]
            ],
            [(18984, 1290)],
        )


if __name__ == "__main__":
    unittest.main()
