"""Lowest Astrub dialogues keep physical/encounter producers separate."""
import gzip
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import (
    conversation,
    conversation_story_authoring,
    mission_toolkit_contract,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/astrub_low_level_contracts.json"
)


class LowLevelConversationAuthoringTests(unittest.TestCase):
    def compile(self):
        document = json.loads(
            (
                ROOT
                / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        definitions, _ = conversation.validate_rules(document)
        exact = json.loads(
            (
                ROOT / "server/tests/fixtures/native_astrub_low_level_contracts.json"
            ).read_text()
        )["definitions"]
        definitions.update({d["d"]: d for d in exact})
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        native["node_index"] = {node["id"]: node for node in native["nodes"]}
        manifest = json.loads(MANIFEST.read_text())
        result = conversation_story_authoring.extend(
            document,
            definitions,
            native["node_index"],
            {s["ref"]: s for s in native["speakers"]},
            manifest,
        )
        return result, definitions, native, manifest

    def test_lowest_seven_quests_compile_additively_without_earning_physical_steps(
        self,
    ):
        result, definitions, native, manifest = self.compile()
        self.assertEqual(
            result,
            conversation_story_authoring.extend(
                result,
                definitions,
                native["node_index"],
                {s["ref"]: s for s in native["speakers"]},
                manifest,
            ),
        )
        targets = {
            (b["quest_id"], b["objective_id"])
            for b in result["bindings"]
            if b["quest_id"] in (2190, 2191, 2158, 2159, 2160, 2161, 2162)
        }
        self.assertEqual(
            targets, {(2191, 4282), (2159, 4278), (2161, 11548), (2162, 4299)}
        )
        self.assertEqual(
            {(d["quest_id"], d["objective_id"]) for d in manifest["pending_producers"]},
            {
                (2190, 4329),
                (2190, 4328),
                (2191, 4281),
                (2158, 4274),
                (2158, 4275),
                (2160, 4279),
                (2161, 4280),
                (2162, 4283),
                (2162, 4284),
                (2162, 4285),
            },
        )
        refs = {4057, 3272, 4067, 2542}
        self.assertFalse(any(p["reference_id"] in refs for p in result["turnins"]))

    def test_acceptance_is_explicit_and_native_node_guards_are_unchanged(self):
        result, _, native, _ = self.compile()
        for ref, quest, node, choice in (
            (4057, 2190, 7149, 15258),
            (3272, 2158, 7143, 15249),
            (4067, 2160, 7152, 15262),
            (2542, 2162, 7155, 15268),
        ):
            placement = next(
                p for p in result["placements"] if p["row"]["reference_id"] == ref
            )
            self.assertNotIn(quest, placement["available_quests_on_open"])
            self.assertEqual(placement["choice_starts"][0]["node_id"], node)
            self.assertEqual(placement["choice_starts"][0]["choice_id"], choice)
            self.assertIn(
                f"!IsAchievementComplete({quest})",
                placement["choice_starts"][0]["criterion"],
            )
        self.assertEqual(
            native["node_index"][7143]["criteria"], "not IsAchievementActive(2158)"
        )
        self.assertEqual(
            native["node_index"][7152]["criteria"], "not IsAchievementActive(2160)"
        )

    def test_child_admission_uses_actual_completed_precursors_not_display_levels(self):
        _, definitions, _, _ = self.compile()
        profile = json.loads(
            (
                ROOT
                / "server/wakfu_server/achievements/mission_profiles/astrub-low-level-followups.json"
            ).read_text()
        )
        mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(len(profile["bindings"]), 2)
        discovery = profile["bindings"][0]
        self.assertEqual(
            (discovery["quest_id"], discovery["objective_id"]), (2191, 4281)
        )
        self.assertEqual(
            discovery["event"], {"kind": "transport_registered", "reference": 27004}
        )
        self.assertEqual((discovery["maps"], discovery["instances"]), ([527], [0]))
        self.assertEqual(profile["links"], [])
        self.assertEqual(
            [
                (
                    a["event"]["kind"],
                    a["event"]["reference"],
                    a["quest_id"],
                    a["requires_completed"],
                )
                for a in profile["activations"]
            ],
            [
                ("quest_completed", 2190, 2191, [2190]),
                ("quest_completed", 2158, 2159, [2158]),
                ("quest_completed", 2160, 2161, [2160]),
            ],
        )
        self.assertEqual(
            [definitions[q]["cjI"] for q in (2190, 2158, 2160, 2162)], ["", "", "", ""]
        )


if __name__ == "__main__":
    unittest.main()
