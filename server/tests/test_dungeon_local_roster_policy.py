import copy
import unittest

from wakfu_server.dungeon_local_roster_policy import draft as native_draft


def draft(plan, definition, native, **kwargs):
    kwargs.setdefault(
        "admission_policy",
        {
            "schema": "native-npc-activation-v1",
            "enabled_monsters": {
                str(row["ref"]): {
                    "min_level": 1,
                    "max_level": 32767,
                    "spell_ids": [549],
                }
                for row in native
            },
        },
    )
    native = [dict(row, native_abilities=[{"spell_id": 549}]) for row in native]
    return native_draft(plan, definition, native, **kwargs)


class DungeonLocalRosterPolicyTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "slug": "draft-test",
            "definition_id": 10,
            "rooms": [],
            "roster_ready": False,
        }
        self.definition = {"id": 10, "type": "DUNGEON_3_ROOMS", "raw_cno": [3, 1, 2]}
        self.native = [
            {"ref": i, "name": str(i), "min_level": 5, "max_level": 10}
            for i in (1, 2, 3)
        ]

    def test_native_type_room_count_and_local_quantities_are_deterministic(self):
        first = draft(self.plan, self.definition, self.native)
        second = draft(
            self.plan,
            {**self.definition, "raw_cno": [2, 1, 3]},
            list(reversed(self.native)),
        )
        self.assertEqual(first, second)
        self.assertEqual(first["room_count"], 3)
        self.assertEqual(first["room_count_source"], "native_eQM_room_type")
        self.assertFalse(first["official"])
        self.assertFalse(first["runtime_ready"])
        self.assertFalse(first["original_plan"]["roster_ready"])
        for room in first["rooms"]:
            self.assertFalse(room["official"])
            self.assertEqual(sum(row["count"] for row in room["monsters"]), 8)
            self.assertEqual({row["role"] for row in room["monsters"]}, {"monster"})

    def test_complete_guide_room_is_preserved_byte_for_byte(self):
        room = {
            "order": 1,
            "diagnostics": [],
            "monsters": [
                {"ref_id": 2, "count": 4, "name": "Known boss", "role": "boss"}
            ],
        }
        plan = {**self.plan, "rooms": [room]}
        before = copy.deepcopy(plan)
        result = draft(plan, self.definition, self.native)
        self.assertEqual(result["rooms"][0]["monsters"], room["monsters"])
        self.assertFalse(result["rooms"][0]["policy_applied"])
        self.assertEqual(plan, before)

    def test_partial_known_quantities_remain_and_unknown_fields_are_annotated(self):
        known = {"ref_id": 2, "count": 4, "name": "Known", "role": "monster"}
        unknown = {
            "ref_id": None,
            "count": None,
            "name": "Unresolved boss",
            "role": "boss",
        }
        room = {
            "order": 1,
            "diagnostics": ["incomplete_composition"],
            "monsters": [known, unknown],
        }
        result = draft({**self.plan, "rooms": [room]}, self.definition, self.native)
        rows = result["rooms"][0]["monsters"]
        self.assertEqual(rows[0]["count"], 4)
        self.assertEqual(rows[0]["ref_id"], 2)
        self.assertEqual(rows[0]["name"], "Known")
        self.assertEqual(rows[1]["count"], 1)
        self.assertEqual(rows[1]["role"], "monster")
        generated = result["rooms"][0]["generated_fields"][0]
        self.assertEqual(generated["original_monster"], unknown)
        self.assertEqual(sum(row["count"] for row in rows), 8)

    def test_no_inferred_room_count_from_three_players_or_ultimate_kind(self):
        for kind in ("DUNGEON_3_PLAYERS", "ULTIMATE_BOSS", "INFINITE_WAVE"):
            with self.assertRaises(ValueError):
                draft(self.plan, {**self.definition, "type": kind}, self.native)
        result = draft(
            self.plan,
            {**self.definition, "type": "ULTIMATE_BOSS"},
            self.native,
            room_count=1,
            boss_references=(1,),
        )
        self.assertEqual(result["room_count_source"], "explicit_local_room_count")
        self.assertFalse(result["official"])

    def test_ultimate_single_species_is_one_boss_without_padding(self):
        result = draft(
            self.plan,
            {**self.definition, "type": "ULTIMATE_BOSS", "raw_cno": [2]},
            self.native,
            room_count=1,
        )
        self.assertEqual(
            [
                (m["ref_id"], m["count"], m["role"])
                for m in result["rooms"][0]["monsters"]
            ],
            [(2, 1, "boss")],
        )

    def test_explicit_final_boss_never_pads_early_rooms(self):
        result = draft(self.plan, self.definition, self.native, boss_references=(3,))
        for room in result["rooms"][:-1]:
            self.assertNotIn(3, [m["ref_id"] for m in room["monsters"]])
        self.assertEqual(
            sum(
                m["count"] for m in result["rooms"][-1]["monsters"] if m["ref_id"] == 3
            ),
            1,
        )

    def test_unresolved_ultimate_preboss_is_not_replaced_with_final_boss(self):
        rooms = [
            {
                "order": 1,
                "monsters": [
                    {"name": "Boufrog", "ref_id": None, "count": 1, "role": "unknown"}
                ],
                "diagnostics": ["unresolved_ref"],
            },
            {
                "order": 2,
                "monsters": [
                    {"name": "Magmog", "ref_id": 2, "count": 1, "role": "boss"}
                ],
                "diagnostics": ["partial"],
            },
        ]
        with self.assertRaisesRegex(ValueError, "intermediate encounter"):
            draft(
                {**self.plan, "rooms": rooms},
                {**self.definition, "type": "ULTIMATE_BOSS", "raw_cno": [2]},
                self.native,
            )

    def test_generated_native_boss_is_reserved_only_for_final_room(self):
        pool = (123, 124, 125, 785, 2157)
        native = [
            {
                "ref": ref,
                "name": str(ref),
                "min_level": 8,
                "max_level": 28,
                "raw_visual_arrays": {"csc": [43] if ref == 2157 else []},
            }
            for ref in pool
        ]
        definition = {
            **self.definition,
            "type": "DUNGEON_4_ROOMS",
            "raw_cno": list(pool),
        }
        result = draft(self.plan, definition, native)
        self.assertEqual(result["boss_references"], [2157])
        self.assertEqual(len(result["rooms"]), 4)
        for room in result["rooms"][:-1]:
            self.assertNotIn(2157, [row["ref_id"] for row in room["monsters"]])
            self.assertTrue(all(row["role"] == "monster" for row in room["monsters"]))
        final = result["rooms"][-1]["monsters"]
        self.assertEqual(sum(row["count"] for row in final if row["ref_id"] == 2157), 1)
        self.assertEqual(
            sum(row["role"] == "boss" for row in final),
            1,
        )

    def test_malformed_boolean_native_boss_flag_is_not_inferred(self):
        native = [
            {
                "ref": 123,
                "name": "123",
                "min_level": 8,
                "max_level": 18,
                "raw_visual_arrays": {"csc": [43, True]},
            }
        ]
        result = draft(
            self.plan,
            {**self.definition, "type": "DUNGEON_2_ROOMS", "raw_cno": [123]},
            native,
        )
        self.assertEqual(result["boss_references"], [])
        self.assertTrue(
            all(
                row["role"] == "monster"
                for room in result["rooms"]
                for row in room["monsters"]
            )
        )

    def test_explicit_boss_selection_excludes_other_native_bosses_from_slots(self):
        pool = (123, 124, 2157)
        native = [
            {
                "ref": ref,
                "name": str(ref),
                "min_level": 8,
                "max_level": 28,
                "raw_visual_arrays": {"csc": [43] if ref in (123, 2157) else []},
            }
            for ref in pool
        ]
        result = draft(
            self.plan,
            {**self.definition, "type": "DUNGEON_3_ROOMS", "raw_cno": list(pool)},
            native,
            boss_references=(123,),
        )
        self.assertEqual(result["boss_references"], [123])
        self.assertTrue(
            all(
                2157 not in [row["ref_id"] for row in room["monsters"]]
                for room in result["rooms"]
            )
        )
        self.assertEqual(
            sum(
                row["count"]
                for row in result["rooms"][-1]["monsters"]
                if row["ref_id"] == 123
            ),
            1,
        )

    def test_multiple_native_bosses_require_explicit_final_boss(self):
        native = [
            {
                "ref": ref,
                "name": str(ref),
                "min_level": 8,
                "max_level": 28,
                "raw_visual_arrays": {"csc": [43]},
            }
            for ref in (123, 2157)
        ]
        with self.assertRaisesRegex(ValueError, "Multiple native bosses"):
            draft(
                self.plan,
                {**self.definition, "type": "DUNGEON_2_ROOMS", "raw_cno": [123, 2157]},
                native,
            )

    def test_known_ultimate_quantity_is_preserved_without_synthetic_padding(self):
        room = {
            "order": 1,
            "monsters": [{"ref_id": 2, "count": 1, "role": "boss"}],
            "diagnostics": ["partial"],
        }
        result = draft(
            {**self.plan, "rooms": [room]},
            {**self.definition, "type": "ULTIMATE_BOSS", "raw_cno": [2]},
            self.native,
        )
        self.assertEqual(len(result["rooms"][0]["monsters"]), 1)
        self.assertEqual(result["rooms"][0]["monsters"][0]["count"], 1)

    def test_known_regular_counts_do_not_crowd_out_missing_final_boss(self):
        room = {
            "order": 1,
            "monsters": [{"ref_id": 1, "count": 8, "role": "monster"}],
            "diagnostics": ["partial"],
        }
        result = draft(
            {**self.plan, "rooms": [room]},
            self.definition,
            self.native,
            boss_references=(3,),
        )
        rows = result["rooms"][0]["monsters"]
        self.assertEqual(rows[0]["count"], 8)
        self.assertEqual([(m["ref_id"], m["count"]) for m in rows[1:]], [(3, 1)])

    def test_conflicts_malformed_counts_and_unavailable_pool_fail_closed(self):
        for capacity in (True, 0, 122):
            with self.assertRaises(ValueError):
                draft(self.plan, self.definition, self.native, capacity=capacity)
        with self.assertRaises(ValueError):
            draft(self.plan, {**self.definition, "id": 11}, self.native)
        with self.assertRaises(ValueError):
            draft(self.plan, {**self.definition, "raw_cno": [999]}, self.native)
        room = {
            "order": 1,
            "diagnostics": ["partial"],
            "monsters": [{"ref_id": 1, "count": 122}],
        }
        with self.assertRaises(ValueError):
            draft({**self.plan, "rooms": [room]}, self.definition, self.native)
        with self.assertRaises(ValueError):
            draft(
                {**self.plan, "rooms": [{**room, "monsters": []}]},
                self.definition,
                self.native,
                room_count=2,
            )

    def test_complete_over_capacity_and_invalid_known_grades_are_not_rewritten(self):
        room = {
            "order": 1,
            "diagnostics": [],
            "monsters": [{"ref_id": 1, "count": 122}],
        }
        with self.assertRaises(ValueError):
            draft({**self.plan, "rooms": [room]}, self.definition, self.native)
        with self.assertRaises(ValueError):
            draft(
                {**self.plan, "rooms": [{**room, "monsters": []}]},
                self.definition,
                self.native,
                room_count=True,
            )
        native = [
            {**row, "min_level": 0} if row["ref"] == 1 else row for row in self.native
        ]
        room = {
            **room,
            "diagnostics": ["partial"],
            "monsters": [{"ref_id": 1, "count": 1}],
        }
        with self.assertRaises(ValueError):
            draft({**self.plan, "rooms": [room]}, self.definition, native)

    def test_known_nine_preserved_with_eight_generation_target(self):
        for diagnostics in ([], ["partial"]):
            room = {
                "order": 1,
                "diagnostics": diagnostics,
                "monsters": [{"ref_id": 1, "count": 9}],
            }
            result = draft({**self.plan, "rooms": [room]}, self.definition, self.native)
            self.assertEqual(
                sum(row["count"] for row in result["rooms"][0]["monsters"]), 9
            )
            self.assertEqual(result["transport_npc_capacity"], 121)
            self.assertEqual(result["generation_target"], 8)

    def test_native_arch_and_dominant_roles_never_fill_ordinary_generated_slots(self):
        native = [
            {"ref": 123, "name": "regular", "min_level": 1, "max_level": 10},
            {
                "ref": 124,
                "name": "arch",
                "min_level": 1,
                "max_level": 10,
                "raw_visual_arrays": {"csc": [45]},
            },
            {
                "ref": 125,
                "name": "dominant",
                "min_level": 1,
                "max_level": 10,
                "raw_visual_arrays": {"csc": [115]},
            },
        ]
        result = draft(
            self.plan,
            {**self.definition, "type": "DUNGEON_2_ROOMS", "raw_cno": [123, 124, 125]},
            native,
        )
        self.assertEqual(result["boss_references"], [])
        self.assertTrue(
            all(
                row["ref_id"] == 123
                for room in result["rooms"]
                for row in room["monsters"]
            )
        )
        with self.assertRaisesRegex(ValueError, "non-boss species"):
            draft(
                self.plan,
                {**self.definition, "type": "DUNGEON_2_ROOMS", "raw_cno": [124, 125]},
                native,
            )

    def test_per_room_generation_targets_preserve_unequal_room_counts(self):
        result = draft(
            self.plan,
            {**self.definition, "type": "DUNGEON_3_ROOMS"},
            self.native,
            generation_targets={1: 2, 2: 5, 3: 7},
        )
        self.assertEqual(
            [sum(row["count"] for row in room["monsters"]) for room in result["rooms"]],
            [2, 5, 7],
        )
        for invalid in ({True: 2}, {1: True}, {4: 2}, {1: 0}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                draft(
                    self.plan,
                    {**self.definition, "type": "DUNGEON_3_ROOMS"},
                    self.native,
                    generation_targets=invalid,
                )

    def test_multiple_native_bosses_infer_only_unique_ordinary_family_match(self):
        native = [
            {
                "ref": 123,
                "name": "regular",
                "family_id": 1,
                "min_level": 1,
                "max_level": 10,
                "raw_visual_arrays": {"csc": []},
            },
            {
                "ref": 124,
                "name": "matching boss",
                "family_id": 1,
                "min_level": 1,
                "max_level": 10,
                "raw_visual_arrays": {"csc": [43]},
            },
            {
                "ref": 125,
                "name": "guest boss",
                "family_id": 2,
                "min_level": 1,
                "max_level": 10,
                "raw_visual_arrays": {"csc": [43]},
            },
        ]
        definition = {
            **self.definition,
            "type": "DUNGEON_2_ROOMS",
            "raw_cno": [123, 124, 125],
        }
        result = draft(self.plan, definition, native)
        self.assertEqual(result["boss_references"], [124])
        self.assertNotIn(
            125, [row["ref_id"] for room in result["rooms"] for row in room["monsters"]]
        )
        with self.assertRaisesRegex(ValueError, "Multiple native bosses"):
            draft(
                self.plan,
                definition,
                [native[0], native[1], {**native[2], "family_id": 1}],
            )
        with self.assertRaisesRegex(ValueError, "Multiple native bosses"):
            draft(
                self.plan,
                definition,
                [
                    {**native[0], "family_id": None},
                    native[1],
                    {**native[2], "family_id": 3},
                ],
            )
