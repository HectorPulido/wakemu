import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from wakfu_server.combat_forced_terrain import next_surface, transitions, compact_index


class NativeForcedTerrainTests(unittest.TestCase):
    def test_original_sm_first_surface_crosses_attraction_stair(self):
        for height in (3, 4, 6):
            self.assertEqual(
                next_surface(1134, height, (-15, -5, -1), (-15, -4)), (-15, -4, 0)
            )

    def test_unknown_policy_and_source_are_not_clear_terrain(self):
        with self.assertRaisesRegex(ValueError, "Missing native"):
            next_surface(999999, 6, (0, 0, 0), (1, 0))
        with self.assertRaisesRegex(ValueError, "not exported"):
            next_surface(1134, 6, (999999, 0, 0), (999999, 1))

    def test_native_blocked_query_is_explicit_none(self):
        table = transitions(1134, 6)
        source, xy = next(key for key, value in table.items() if value is None)
        self.assertIsNone(next_surface(1134, 6, source, xy))


class CompactForcedTerrainTests(unittest.TestCase):
    def fixture(self, directory, variants=None):
        root = Path(directory)
        folder = root / "forced-transitions"
        folder.mkdir(exist_ok=True)
        full = (1 << 25) - 1
        data = dict(
            schema_version=1,
            map_id=123,
            radius=0,
            jump=4,
            heights=[1, 25],
            rows=[[1, 2, -1, 0, 1, variants or [[1, 4], [full ^ 1, None]]]],
        )
        (folder / "123.json").write_bytes(json.dumps(data).encode())
        return root

    def tearDown(self):
        transitions.cache_clear()
        compact_index.cache_clear()

    def test_mask_priority_blocked_and_shared_immutable_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            with patch("wakfu_server.combat_forced_terrain.DATA_ROOT", root):
                self.assertEqual(next_surface(123, 1, (1, 2, -1), (1, 3)), (1, 3, 4))
                self.assertIsNone(next_surface(123, 2, (1, 2, -1), (1, 3)))
                self.assertIs(transitions(123, 1)._index, transitions(123, 2)._index)
                with self.assertRaises(TypeError):
                    transitions(123, 1)._index[((1, 2, -1), (1, 3))] = ()
                with self.assertRaisesRegex(ValueError, "physical height"):
                    next_surface(123, 26, (1, 2, -1), (1, 3))

    def test_overlapping_and_missing_masks_reject_before_destination(self):
        for variants in ([[1, 0], [1, None]], [[1, None]]):
            with tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory, variants)
                with patch("wakfu_server.combat_forced_terrain.DATA_ROOT", root):
                    with self.assertRaises(ValueError):
                        next_surface(123, 1, (1, 2, -1), (1, 3))
            compact_index.cache_clear()

    def test_old_table_remains_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "forced-transitions"
            folder.mkdir()
            data = dict(
                map_id=123,
                height=4,
                radius=0,
                jump=4,
                rows=[[[1, 2, -1], [1, 3], [1, 3, 0]]],
            )
            (folder / "123-h4-r0-j4.json").write_bytes(json.dumps(data).encode())
            with patch("wakfu_server.combat_forced_terrain.DATA_ROOT", root):
                self.assertEqual(next_surface(123, 4, (1, 2, -1), (1, 3)), (1, 3, 0))
