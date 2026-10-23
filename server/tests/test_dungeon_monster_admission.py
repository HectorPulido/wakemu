import copy
import unittest
from unittest.mock import patch

from wakfu_server.dungeon_local_roster_policy import draft
from wakfu_server.dungeon_monster_admission import admitted, current_policy


class DungeonMonsterAdmissionTests(unittest.TestCase):
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
        self.plan = dict(slug="test", definition_id=1, rooms=[])
        self.definition = dict(id=1, type="DUNGEON_2_ROOMS", raw_cno=[1, 2, 3])

    def build(self, **changes):
        return draft(
            changes.get("plan", self.plan),
            self.definition,
            self.native,
            admission_policy=self.policy,
            **changes.get("options", {})
        )

    def test_generated_filler_requires_admission_preserving_pool_and_source(self):
        before = copy.deepcopy(self.plan)
        result = self.build(options=dict(boss_references=(3,)))
        self.assertEqual(result["species_pool"], [1, 2, 3])
        self.assertEqual(result["native_species_pool"], [1, 2, 3])
        self.assertEqual(result["admitted_species_pool"], [1, 3])
        self.assertEqual(result["excluded_unadmitted_references"], [2])
        self.assertEqual(self.plan, before)
        self.assertTrue(
            all(row["ref_id"] == 1 for row in result["rooms"][0]["monsters"])
        )
        self.assertEqual(sum(row["count"] for row in result["rooms"][0]["monsters"]), 8)
        self.assertEqual(
            sum(
                row["count"]
                for row in result["rooms"][-1]["monsters"]
                if row["ref_id"] == 3
            ),
            1,
        )

    def test_unadmitted_authored_complete_room_and_final_boss_fail_without_substitution(
        self,
    ):
        room = dict(
            order=1, diagnostics=[], monsters=[dict(ref_id=2, count=4, role="boss")]
        )
        plan = dict(self.plan, rooms=[room])
        before = copy.deepcopy(plan)
        with self.assertRaisesRegex(ValueError, "2 lacks ordinary NPC admission"):
            self.build(plan=plan)
        self.assertEqual(plan, before)
        with self.assertRaisesRegex(ValueError, "2 lacks ordinary NPC admission"):
            self.build(options=dict(boss_references=(2,)))

    def test_no_eligible_fillers_fails_instead_of_empty_or_boss_padding(self):
        self.policy["enabled_monsters"].pop("1")
        with self.assertRaisesRegex(ValueError, "non-boss species"):
            self.build(options=dict(boss_references=(3,)))

    def test_exact_grade_and_owned_book_intersection_ignore_conditional_costs(self):
        native = self.native[0]
        self.assertTrue(admitted(self.policy, 1, 1, 10, native=native))
        self.assertFalse(admitted(self.policy, 1, 1, 11, native=native))
        self.policy["enabled_monsters"]["1"]["spell_ids"] = [999]
        self.assertFalse(admitted(self.policy, 1, 1, 10, native=native))

    def test_empty_book_preserves_existing_qualified_event_controller(self):
        self.policy["enabled_monsters"]["1"]["spell_ids"] = []
        native = dict(self.native[0], native_abilities=[])
        with patch(
            "wakfu_server.combat_npc_event_controller.event_controller_record",
            return_value=object(),
        ) as controller:
            self.assertTrue(admitted(self.policy, 1, 1, 10, native=native))
            self.assertEqual(
                {call.args[-1] for call in controller.call_args_list}, {1, 10}
            )
        with patch(
            "wakfu_server.combat_npc_event_controller.event_controller_record",
            return_value=None,
        ):
            self.assertFalse(admitted(self.policy, 1, 1, 10, native=native))

    def test_policy_loader_uses_three_indexed_records(self):
        records = dict(
            schema="native-npc-activation-v1", legacy_spell_ids=[], enabled_monsters={}
        )
        with patch(
            "wakfu_server.native_catalog.record",
            side_effect=lambda path, collection, key: records[key],
        ) as reader:
            self.assertEqual(current_policy(), records)
            self.assertEqual(reader.call_count, 3)
            self.assertTrue(
                all(
                    call.args[1] == "activation_policy"
                    for call in reader.call_args_list
                )
            )

    def test_admitted_ultimate_and_raid_profiles_never_become_ordinary_fillers(self):
        self.policy["enabled_monsters"]["2"] = dict(
            min_level=1, max_level=10, spell_ids=[549]
        )
        for flag in (49, 99):
            with self.subTest(flag=flag):
                self.native[1]["raw_visual_arrays"] = dict(csc=[flag])
                result = self.build(options=dict(boss_references=(3,)))
                self.assertTrue(
                    all(row["ref_id"] == 1 for row in result["rooms"][0]["monsters"])
                )
                self.assertFalse(
                    any(
                        row["ref_id"] == 2
                        for room in result["rooms"]
                        for row in room["monsters"]
                    )
                )

    def test_boss_only_ordinary_pool_requires_explicit_composition_not_repeated_fillers(
        self,
    ):
        self.native = [self.native[0]]
        self.native[0]["raw_visual_arrays"] = dict(csc=[49])
        self.definition["raw_cno"] = [1]
        with self.assertRaisesRegex(ValueError, "non-boss species"):
            self.build()
        self.definition["type"] = "ULTIMATE_BOSS"
        result = self.build(options=dict(room_count=1))
        self.assertEqual(
            [
                (row["ref_id"], row["count"], row["role"])
                for row in result["rooms"][0]["monsters"]
            ],
            [(1, 1, "boss")],
        )
