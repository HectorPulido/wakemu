import struct
import unittest

from wakfu_server import native_boats


class NativeBoatTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7, account_id=9, map_id=504, instance_id=0, x=4, y=3, z=9, level=50
        )
        self.body = struct.pack(">qq", 18259, 21678)
        self.geometry = lambda map_id: {"edges": [((-3, -4, 6), (-3, -3, 6))]}

    def resolve(self, body=None, character=None, **kwargs):
        return native_boats.resolve(
            character or self.character,
            body or self.body,
            source_allowed=kwargs.get("source_allowed", lambda c, s: True),
            geometry=kwargs.get("geometry", self.geometry),
        )

    def test_original_link_resolves_original_xy_and_unique_native_height(self):
        route = self.resolve()
        self.assertEqual(route["native_link_id"], 550)
        self.assertEqual(
            route["destination"], dict(map_id=794, instance_id=0, x=-3, y=-4, z=6)
        )
        self.assertEqual(route["animation"]["duration_ms"], 4800)

    def test_original_link_is_bidirectional(self):
        route = self.resolve(
            struct.pack(">qq", 21678, 18259),
            dict(self.character, map_id=794),
            geometry=lambda m: {"edges": [((4, 2, 9), (4, 3, 9))]},
        )
        self.assertEqual(route["destination"]["map_id"], 504)
        self.assertEqual(route["native_link_id"], 550)

    def test_no_all_to_all_or_self_travel(self):
        for target in (18259, 999999):
            with self.assertRaises(ValueError):
                self.resolve(struct.pack(">qq", 18259, target))

    def test_private_scene_foreign_source_and_malformed_requests_rejected(self):
        for character, body in (
            (dict(self.character, instance_id=2), self.body),
            (dict(self.character, map_id=527), self.body),
            (self.character, b"x"),
        ):
            with self.assertRaises(ValueError):
                self.resolve(body, character)

    def test_source_authority_is_mandatory_and_receives_original_position(self):
        received = []

        def deny(character, source):
            received.append(source)
            return False

        with self.assertRaises(ValueError):
            self.resolve(source_allowed=deny)
        self.assertEqual(received[0]["source_position"], dict(x=4, y=3, z=9))

    def test_missing_or_ambiguous_native_altitudes_rejected(self):
        for edges in ([], [((-3, -4, 6), (-3, -4, 7))]):
            with self.assertRaises(ValueError):
                self.resolve(geometry=lambda m: {"edges": edges})

    def test_unknown_criteria_do_not_become_unconditional(self):
        for expression in (
            "False",
            "IsAchievementComplete(2192)",
            "IsBefore(03,03,2023,16,00,00)",
            "True",
            "",
        ):
            self.assertEqual(
                native_boats.criterion_allowed(expression, self.character),
                expression == "",
            )
        self.assertTrue(
            native_boats.criterion_allowed("GetRealLevel() >= 40", self.character)
        )
        self.assertFalse(
            native_boats.criterion_allowed("GetRealLevel() >= 51", self.character)
        )
        self.assertFalse(
            native_boats.criterion_allowed("GetRealLevel() >= 1", {"level": True})
        )

    def test_catalog_contains_all_original_boats_and_links(self):
        self.assertEqual(len(native_boats._ENDPOINTS), 87)
        self.assertEqual(sum(map(len, native_boats._LINKS.values())), 393)
        self.assertEqual(native_boats._ENDPOINTS[18259]["label_id"], 97)
        self.assertEqual(native_boats._ENDPOINTS[18259]["map_id"], 504)

    def test_returned_source_copy_cannot_modify_catalog(self):
        row = native_boats.source(self.character, self.body)
        row["source_position"]["z"] = 9999
        self.assertEqual(
            native_boats.source(self.character, self.body)["source_position"]["z"], 9
        )
