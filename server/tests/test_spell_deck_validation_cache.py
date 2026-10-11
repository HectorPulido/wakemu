"""Reuse only static deck validation while preserving caller isolation."""
import unittest
from unittest.mock import patch
from wakfu_server import spells


class DeckValidationCacheTests(unittest.TestCase):
    def setUp(self):
        spells._validated_deck.cache_clear()
        self.addCleanup(spells._validated_deck.cache_clear)

    def test_same_exact_deck_reuses_validation_and_returns_fresh_lists(self):
        blob = spells.encode_deck([4778])
        with patch.object(
            spells, "_validate_deck", wraps=spells._validate_deck
        ) as validate:
            first = spells.validate_deck(blob, 8, 1)
            first["active"].append(999999)
            first["passive"].append(999999)
            second = spells.validate_deck(blob, 8, 1)
            self.assertEqual(validate.call_count, 1)
            self.assertEqual(second, {"active": [4778], "passive": [], "level_cap": -1})

    def test_owner_level_and_deck_changes_revalidate(self):
        blob = spells.encode_deck([4778])
        spells.validate_deck(blob, 8, 1)
        with self.assertRaises(ValueError):
            spells.validate_deck(blob, 2, 1)
        with self.assertRaises(ValueError):
            spells.validate_deck(spells.encode_deck([4778], [], 2), 8, 1)
        self.assertEqual(
            spells.validate_deck(spells.encode_deck([4778], [], 2), 8, 2)["level_cap"],
            2,
        )
        with self.assertRaises(ValueError):
            spells.validate_deck(blob + b"\x00", 8, 1)

    def test_mutable_input_is_snapshotted(self):
        blob = bytearray(spells.encode_deck([4778]))
        spells.validate_deck(blob, 8, 1)
        blob[:] = spells.encode_deck([7307])
        with self.assertRaises(ValueError):
            spells.validate_deck(blob, 8, 1)

    def test_failures_are_not_cached(self):
        blob = spells.encode_deck([7307])
        for _ in range(2):
            with self.assertRaises(ValueError):
                spells.validate_deck(blob, 8, 1)
        self.assertEqual(spells._validated_deck.cache_info().currsize, 0)

    def test_nonbyte_and_multidimensional_views_bypass_cache_normalization(self):
        views = (
            memoryview(bytearray(128)).cast("B", shape=(1, 128)),
            memoryview(bytearray(128)).cast("I"),
        )
        for view in views:
            with self.subTest(shape=view.shape), patch.object(
                spells, "_validate_deck", return_value="original-parser"
            ) as original, patch.object(spells, "_validated_deck") as cached:
                self.assertEqual(spells.validate_deck(view, 8, 1), "original-parser")
                original.assert_called_once_with(view, 8, 1)
                cached.assert_not_called()

    def test_cache_is_bounded(self):
        blob = spells.encode_deck()
        for level in range(1, 601):
            spells.validate_deck(blob, 8, level)
        self.assertEqual(spells._validated_deck.cache_info().currsize, 512)

    def test_distinct_catalog_identity_does_not_reuse_result(self):
        blob = spells.encode_deck([4778])
        spells.validate_deck(blob, 8, 1)
        with patch.object(spells, "SPELLS", {}), self.assertRaises(ValueError):
            spells.validate_deck(blob, 8, 1)
