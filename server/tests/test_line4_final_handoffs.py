"""Reviewed Chapter2 NPC handoffs compile over native mission/dialogue sources."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from tools.compile_line4_final_handoffs import compile_fragment
from wakfu_server.achievements import mission_toolkit_contract, mission_toolkit_planner


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
CONVERSATIONS = SERVER / "wakfu_server/maps/native_quest_conversation_contracts.json"
MANIFEST = (
    SERVER
    / "wakfu_server/achievements/conversation_archetypes/line4_final_handoffs.json"
)
PROFILE = (
    SERVER / "wakfu_server/achievements/mission_profiles/line4-final-handoffs.json"
)
NATIVE_QUESTS = ROOT / ".runtime/quest-extraction/native-quest-definitions.json"
NATIVE_NPCS = ROOT / "database/protocol/npc-dialogues.json.gz"

PATHS = {
    2712: (
        [-1724034232352753, 3819, 703, 5347],
        [[3225, 8086, 3281], [3281, 8087, 0]],
    ),
    2713: (
        [-2251799927089062, 3814, 698, 5348],
        [[3219, 8088, 3282], [3282, 8089, 0]],
    ),
    2714: (
        [-2251799934992048, 2805, 436, 5349],
        [[2315, 8094, 3283], [3283, 8098, 3284], [3284, 8102, 3285], [3285, 8103, 0]],
    ),
}
TARGET_ACTORS = {row[0] for row, _ in PATHS.values()}


def sources():
    native_quests = json.loads(NATIVE_QUESTS.read_text())
    definitions = {row["d"]: row for row in native_quests["definitions"]}
    native_npcs = json.loads(gzip.decompress(NATIVE_NPCS.read_bytes()))
    nodes = {row["id"]: row for row in native_npcs["nodes"]}
    speakers = {row["ref"]: row for row in native_npcs["speakers"]}
    base = json.loads(CONVERSATIONS.read_text())
    manifest = json.loads(MANIFEST.read_text())
    profile = json.loads(PROFILE.read_text())
    return base, definitions, nodes, speakers, manifest, profile


def planner_state(*, completed=()):
    completed = list(completed)
    return dict(
        variables={},
        objectives=[],
        running=[],
        completed=completed,
        active=sorted(completed),
        active_periods={},
        active_unknown=[],
        tracking=[],
        recent=[],
        completion_dates={str(quest): 1000 for quest in completed},
    )


class Line4FinalHandoffTests(unittest.TestCase):
    def test_compilation_is_additive_idempotent_and_preserves_native_rows(self):
        base, definitions, nodes, speakers, manifest, _profile = sources()
        before = deepcopy(base)
        compiled = compile_fragment(base, definitions, nodes, speakers, manifest)

        self.assertEqual(
            base, before, "source compiler must not mutate canonical input"
        )
        self.assertEqual(
            compile_fragment(compiled, definitions, nodes, speakers, manifest), compiled
        )
        self.assertEqual(
            [
                row
                for row in compiled["placements"]
                if row["row"]["actor_id"] not in TARGET_ACTORS
            ],
            [
                row
                for row in base["placements"]
                if row["row"]["actor_id"] not in TARGET_ACTORS
            ],
            "unrelated actor rows must remain byte-for-byte equivalent JSON data",
        )

        actual_bindings = {
            row["quest_id"]: row
            for row in compiled["bindings"]
            if row["quest_id"] in PATHS
        }
        self.assertEqual(set(actual_bindings), set(PATHS))
        for quest_id, (expected_binding, path) in PATHS.items():
            with self.subTest(quest=quest_id):
                binding = actual_bindings[quest_id]
                self.assertEqual(
                    [
                        binding["reference_id"],
                        binding["action_id"],
                        binding["objective_id"],
                    ],
                    expected_binding[1:],
                )
                self.assertEqual(
                    [binding["node_id"], binding["choice_id"]], path[-1][:2]
                )
                placement = next(
                    p
                    for p in compiled["placements"]
                    if p["row"]["actor_id"] == expected_binding[0]
                )
                self.assertEqual(
                    placement["row"],
                    next(
                        p["row"]
                        for p in base["placements"]
                        if p["row"]["actor_id"] == expected_binding[0]
                    ),
                )
                for edge in path:
                    self.assertIn(edge, placement["graph"])

        magnum = next(
            p
            for p in compiled["placements"]
            if p["row"]["actor_id"] == -1724034232352753
        )
        self.assertEqual(
            magnum["existing_native_actor"]["source_sha256"],
            "0410af8f82ee3c8a209efca093d0ebbdaf477be9f35801b1a63d4559f4e381cb",
        )
        self.assertEqual(magnum["existing_native_actor"]["quest_ids"], [2705, 2712])

        wool_payment = dict(
            reference_id=3819,
            action_id=703,
            node_id=3281,
            choice_id=8087,
            item_reference=19660,
            quantity=1,
        )
        payments = [
            row
            for row in compiled["turnins"]
            if row["reference_id"] == 3819
            and row["action_id"] == 703
            and row["node_id"] == 3281
            and row["choice_id"] == 8087
        ]
        self.assertEqual(payments, [wool_payment])
        self.assertNotIn(19664, [item["item_reference"] for item in payments])
        self.assertNotIn(19665, [item["item_reference"] for item in payments])

        # These quests are native definitions; this compiler may bind them but
        # cannot replace their mission data or reward table.
        by_id = {row["d"]: row for row in compiled["definitions"]}
        for quest_id in (2712, 2713, 2714):
            self.assertEqual(by_id[quest_id], definitions[quest_id])
        reward_4307 = next(row for row in definitions[2720]["cjK"] if row["d"] == 4307)
        self.assertEqual((reward_4307["aeV"], reward_4307["ckl"]), (5, [19660, 1]))
        self.assertEqual(
            [
                (row["d"], row["aeV"], row["ckl"])
                for row in definitions[2714]["cjK"]
                if row["d"] in (4302, 4308)
            ],
            [(4302, 5, [19661, 1]), (4308, 5, [19799, 1])],
        )
        self.assertEqual(compiled["reviewed_item_grants"], base["reviewed_item_grants"])

    def test_native_wool_reward_tampering_is_rejected(self):
        base, definitions, nodes, speakers, manifest, _profile = sources()
        changed = deepcopy(definitions)
        reward = next(row for row in changed[2720]["cjK"] if row["d"] == 4307)
        reward["ckl"] = [19660, 2]
        with self.assertRaisesRegex(ValueError, "native producer"):
            compile_fragment(base, changed, nodes, speakers, manifest)

    def test_profile_uses_real_native_admission_without_granting_later_objectives(self):
        _base, native, _nodes, _speakers, _manifest, profile = sources()
        ids = {2720, 2712, 2713, 2714, 2715}
        definitions = {identity: native[identity] for identity in ids}
        mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(profile["bindings"], [])
        self.assertEqual(profile["links"], [])

        character = dict(
            id=1,
            account_id=1,
            map_id=1134,
            instance_id=0,
            level=21,
            effective_level=21,
        )
        event = dict(kind="character_ready", reference=0, quantity=1)

        def plan(completed, level):
            character["level"] = level
            character["effective_level"] = level
            return mission_toolkit_planner.plan(
                planner_state(completed=completed),
                definitions,
                profile,
                event,
                character=character,
                store=None,
                now_ms=2000,
            )

        admitted = plan([2714], 21)
        self.assertEqual(admitted[0]["running"], [2715])
        self.assertEqual(admitted[0]["completed"], [2714])
        self.assertEqual(admitted[0]["objectives"], [])
        self.assertEqual(admitted[1:], ([], [], []))

        for completed, level in (([2714], 20), ([], 21)):
            with self.subTest(completed=completed, level=level):
                rejected = plan(completed, level)
                self.assertEqual(rejected[0]["running"], [])
                self.assertEqual(rejected[0]["objectives"], [])
                self.assertEqual(rejected[0]["completed"], completed)
                self.assertEqual(rejected[1:], ([], [], []))

        self.assertEqual(
            [
                (row["event"]["kind"], row["event"].get("reference"), row["quest_id"])
                for row in profile["activations"]
                if row["quest_id"] == 2715
            ],
            [("quest_completed", 2714, 2715), ("character_ready", 0, 2715)],
        )
        self.assertNotIn(5350, [o["objective_id"] for o in profile["bindings"]])
        self.assertNotIn(5351, [o["objective_id"] for o in profile["bindings"]])


if __name__ == "__main__":
    unittest.main()
