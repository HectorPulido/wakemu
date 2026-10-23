import copy
import unittest

from tools.prepare_admitted_dungeon_rosters import prepare


class PrepareAdmittedDungeonRostersTests(unittest.TestCase):
    def setUp(self):
        self.native = [
            dict(
                ref=ref,
                name=str(ref),
                min_level=1,
                max_level=10,
                native_abilities=[dict(spell_id=549)],
            )
            for ref in (1, 2, 3)
        ]
        self.policy = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                str(ref): dict(min_level=1, max_level=10, spell_ids=[549])
                for ref in (1, 3)
            },
        )
        rooms = []
        for order in (1, 2, 3):
            rows = [
                dict(ref_id=1, count=4, role="monster"),
                dict(ref_id=2, count=3, role="monster"),
            ]
            rows.append(
                dict(
                    ref_id=3 if order == 3 else 1,
                    count=1,
                    role="boss" if order == 3 else "monster",
                )
            )
            rooms.append(dict(order=order, monsters=rows, diagnostics=[]))
        self.configuration = dict(
            version=3,
            topology=dict(rooms=[dict(order=order) for order in (1, 2, 3)]),
            route=dict(key="test"),
            context_policy=dict(policy_version=3, difficulty_level=2),
            level_policy=dict(mode="native_minimum"),
            provenance="existing",
            evidence_hashes=dict(plan="old", topology="preserved", route="preserved"),
            compiled_plan=dict(
                slug="test",
                definition_id=1,
                rooms=rooms,
                official=False,
                reviewed_official=False,
                generated_fields=[dict(order=order) for order in (1, 2, 3, 4)],
                roster_policy_evidence=dict(
                    official=False,
                    policy_mode="generated_native_species_policy",
                    boss_references=[3],
                ),
            ),
        )

    def test_rebuild_supersedes_stale_annotations_preserves_structure_and_boss(self):
        before = copy.deepcopy(self.configuration)
        result = prepare(self.configuration, self.native, self.policy, version=4)
        self.assertEqual(self.configuration, before)
        self.assertEqual(result["topology"], before["topology"])
        self.assertEqual(result["route"], before["route"])
        self.assertEqual(result["level_policy"]["mode"], before["level_policy"]["mode"])
        self.assertEqual(result["level_policy"]["provenance"], result["provenance"])
        self.assertEqual(result["context_policy"]["difficulty_level"], 2)
        self.assertEqual(result["context_policy"]["policy_version"], 4)
        self.assertEqual(
            [row["order"] for row in result["compiled_plan"]["generated_fields"]],
            [1, 2, 3],
        )
        rooms = result["compiled_plan"]["rooms"]
        self.assertEqual(
            [sum(row["count"] for row in room["monsters"]) for room in rooms], [8, 8, 8]
        )
        self.assertEqual(
            [
                [row["ref_id"] for row in room["monsters"] if row["role"] == "boss"]
                for room in rooms
            ],
            [[], [], [3]],
        )
        self.assertFalse(
            any(row["ref_id"] == 2 for room in rooms for row in room["monsters"])
        )
        evidence = result["compiled_plan"]["roster_policy_evidence"]
        self.assertEqual(
            evidence["species_pool_provenance"], "previous_immutable_published_roster"
        )
        self.assertFalse(evidence["previous_generated_fields_reused"])
        self.assertEqual(
            result,
            prepare(
                self.configuration, list(reversed(self.native)), self.policy, version=4
            ),
        )

    def test_unadmitted_final_boss_is_not_replaced(self):
        del self.policy["enabled_monsters"]["3"]
        with self.assertRaisesRegex(ValueError, "3 lacks ordinary NPC admission"):
            prepare(self.configuration, self.native, self.policy, version=4)

    def test_reviewed_or_older_configurations_cannot_be_rebuilt_as_generated(self):
        with self.assertRaises(ValueError):
            prepare(self.configuration, self.native, self.policy, version=3)
        self.configuration["compiled_plan"]["reviewed_official"] = True
        with self.assertRaises(ValueError):
            prepare(self.configuration, self.native, self.policy, version=4)
