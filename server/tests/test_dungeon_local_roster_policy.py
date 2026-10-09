import copy
import unittest

from wakfu_server.dungeon_local_roster_policy import draft


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
        )
        self.assertEqual(result["room_count_source"], "explicit_local_room_count")
        self.assertFalse(result["official"])

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
