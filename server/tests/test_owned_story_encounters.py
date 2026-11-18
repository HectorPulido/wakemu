"""Four story battles preserve original native species and bounded terrain."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.owned_story_encounters import can_spawn, compile_rooms
from wakfu_server import owned_story_controller


class StoryEncounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1]
        cls.document = json.loads(
            (
                root
                / "wakfu_server/maps/owned_story_profiles/astrub-temple-887-encounters.json"
            ).read_text()
        )
        cls.terrain = json.loads(
            (root / "tests/fixtures/native_astrub_temple_arenas.json").read_text()
        )
        cls.monsters = {
            row["ref"]: row
            for row in json.loads(
                (root / "tests/fixtures/native_astrub_temple_monsters.json").read_text()
            )
        }

    def compile(self, document=None, terrain=None, monsters=None):
        data = terrain or self.terrain
        return compile_rooms(
            document or self.document,
            geometry=prepare_geometry(data),
            exploration=data,
            monster=(monsters or self.monsters).__getitem__,
        )

    def test_four_original_grade_formations_have_disjoint_native_arenas(self):
        rooms, topology = self.compile()
        self.assertEqual([room["order"] for room in rooms], [1, 2, 3, 4])
        self.assertEqual(
            [row["physical_room"] for row in self.document["rooms"]], [1, 2, 4, 5]
        )
        seen = set()
        for room, place in zip(rooms, topology):
            cells = {tuple(point) for point in place["cells"]}
            self.assertFalse(seen & cells)
            seen.update(cells)
            for actor in room["monsters"]:
                native = self.monsters[actor["ref_id"]]
                self.assertEqual(actor["native_min_level"], native["min_level"])
                self.assertEqual(actor["native_max_level"], native["max_level"])
                self.assertNotIn("hp", actor)
                self.assertNotIn("spells", actor)
        self.assertEqual(rooms[-1]["monsters"][0]["ref_id"], 3234)

    def test_fake_anchor_duplicate_room_or_species_override_is_rejected(self):
        for change in ("seed", "room", "stats"):
            document = deepcopy(self.document)
            if change == "seed":
                document["rooms"][0]["arena_seed"] = [900, 900, 0]
            elif change == "room":
                document["rooms"][1]["order"] = 1
            else:
                document["rooms"][0]["monsters"][0]["hp"] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.compile(document)

    def test_visual_only_monster_without_native_abilities_cannot_spawn(self):
        monsters = deepcopy(self.monsters)
        monsters[3236]["native_abilities"] = []
        with self.assertRaisesRegex(ValueError, "native combat definition"):
            self.compile(monsters=monsters)

    def test_boss_role_is_explicit_and_independent_of_physical_room_number(self):
        document = deepcopy(self.document)
        document["rooms"][-1]["physical_room"] = 3
        rooms, _ = self.compile(document)
        self.assertEqual(rooms[-1]["monsters"][0]["role"], "boss")
        document["rooms"][-1]["physical_room"] = 5
        del document["rooms"][-1]["monsters"][0]["role"]
        rooms, _ = self.compile(document)
        self.assertEqual(rooms[-1]["monsters"][0]["role"], "monster")
        document["rooms"][0]["monsters"][0]["role"] = "invented-role"
        with self.assertRaisesRegex(ValueError, "species/count"):
            self.compile(document)


class StorySpawnGateTests(unittest.TestCase):
    def test_future_boss_waits_for_the_actual_owned_intro_receipt(self):
        selected = dict(steps=[dict(id="boss-intro-done")])
        db, store = Mock(), Mock()
        db.execute.return_value.fetchall.return_value = [dict(id=7, account_id=2)]
        groups = SimpleNamespace(store=store)
        room = dict(requires=["boss-intro-done"])
        with patch.object(
            owned_story_controller, "policy", return_value=selected
        ), patch.object(
            owned_story_controller,
            "_scope",
            side_effect=[(selected, set()), (selected, {"boss-intro-done"})],
        ):
            self.assertFalse(can_spawn(db, groups, 99, {}, room))
            self.assertTrue(can_spawn(db, groups, 99, {}, room))
        store.character.assert_called_with(2, 7, db)

    def test_ordinary_routes_do_not_require_story_owner_or_receipts(self):
        db = Mock()
        with patch.object(owned_story_controller, "policy", return_value=None):
            self.assertTrue(can_spawn(db, object(), 99, {}, {}))
        db.execute.assert_not_called()

    def test_unknown_required_step_cannot_silently_unlock_a_room(self):
        db = Mock()
        with patch.object(
            owned_story_controller, "policy", return_value=dict(steps=[])
        ):
            with self.assertRaisesRegex(ValueError, "spawn prerequisites"):
                can_spawn(db, object(), 99, {}, dict(requires=["invented-done"]))
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
