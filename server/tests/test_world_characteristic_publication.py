"""A same-build selection flushes derived bounds without changing snapshots."""

import struct
import unittest

from wakfu_server.characters import world_characteristic_publication as publication


class WorldCharacteristicPublicationTests(unittest.TestCase):
    def test_same_snapshot_brackets_build_selection_for_owned_indices(self):
        snapshot = (12436, b"authoritative-hp-ap-mp-wp")
        for index in (0, 127):
            character = {
                "id": 29,
                "level": 200,
                "active_build_index": index,
                "builds": {127: {}} if index == 127 else {},
            }
            first, selection, last = publication.packets(character, snapshot)
            self.assertIs(first, snapshot)
            self.assertIs(last, snapshot)
            self.assertEqual(selection, (13811, struct.pack(">qb", 29, index)))
            self.assertEqual(first, last)

            # Re-selecting the same owned book must remain a pure UI flush.
            repeated = publication.packets(character, snapshot)
            self.assertEqual(repeated[1], selection)
            self.assertIs(repeated[0], snapshot)
            self.assertIs(repeated[2], snapshot)

    def test_missing_actor_or_malformed_snapshot_is_rejected_before_selection(self):
        valid_character = {
            "id": 29,
            "level": 200,
            "active_build_index": 0,
            "builds": {},
        }
        invalid_snapshots = (None, (12436,), (True, b"snapshot"), (12436, bytearray()))
        for character, snapshot in (
            (dict(valid_character, level=None), (12436, b"snapshot")),
            *((valid_character, snapshot) for snapshot in invalid_snapshots),
        ):
            with self.subTest(character=character, snapshot=snapshot):
                with self.assertRaises(ValueError):
                    publication.packets(character, snapshot)

    def test_unknown_build_selection_is_rejected(self):
        character = {
            "id": 29,
            "level": 200,
            "active_build_index": 128,
            "builds": {128: {}},
        }
        with self.assertRaisesRegex(ValueError, "selection"):
            publication.packets(character, (12436, b"snapshot"))
