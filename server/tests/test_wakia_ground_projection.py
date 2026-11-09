"""Focused checks for per-snapshot native ground projection."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_ground as subject


class GroundProjectionTests(unittest.TestCase):
    def setUp(self):
        self.release = "release-r1"
        self.provenance = {"map_id": 42, "source_sha256": "a" * 64}
        self.cells = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}

    def run_projection(self, fight, reader):
        # Preserve the native policy's module identity so this tests the
        # qualified one-read path rather than the explicit replacement path.
        reader.__module__ = subject._ground.__name__
        with patch.object(
            subject._native_catalog, "release", return_value=self.release
        ), patch.object(subject._ground, "_map", reader), patch.object(
            subject, "_MAP", reader
        ):
            return subject.unsupported_ground(fight, catalog_revision=self.release)

    def test_projection_matches_per_cell_policy_and_recomputes_changed_snapshot(self):
        supported_by_identity = {
            (42, "a" * 64): {(0, 0, 0), (2, 0, 0)},
            (42, "b" * 64): {(0, 0, 0), (3, 0, 0)},
            (43, "b" * 64): {(1, 0, 0), (3, 0, 0)},
        }
        calls = []

        def reader(map_id, source_sha256, revision):
            calls.append((map_id, source_sha256, revision))
            return supported_by_identity.get((map_id, source_sha256))

        fight = NS(
            walkable=set(self.cells), native_qi_surface_provenance=dict(self.provenance)
        )
        projected = self.run_projection(fight, reader)
        expected = {
            cell
            for cell in fight.walkable
            if cell not in supported_by_identity[(42, "a" * 64)]
        }
        self.assertEqual(projected, expected)

        # The projection is not cached by fight or map across snapshots.
        fight.walkable.remove((1, 0, 0))
        fight.walkable.add((3, 0, 0))
        same_publication = self.run_projection(fight, reader)
        self.assertEqual(same_publication, {(3, 0, 0)})

        # Content provenance and map identity each select their own result.
        fight.native_qi_surface_provenance = {"map_id": 42, "source_sha256": "b" * 64}
        changed_content = self.run_projection(fight, reader)
        self.assertEqual(changed_content, {(2, 0, 0)})
        fight.native_qi_surface_provenance = {"map_id": 43, "source_sha256": "b" * 64}
        changed_map = self.run_projection(fight, reader)
        self.assertEqual(changed_map, {(0, 0, 0), (2, 0, 0)})
        self.assertEqual(
            calls,
            [
                (42, "a" * 64, self.release),
                (42, "a" * 64, self.release),
                (42, "b" * 64, self.release),
                (43, "b" * 64, self.release),
            ],
        )

    def test_missing_provenance_and_unknown_map_preserve_existing_floor(self):
        fight = NS(walkable=set(self.cells), native_qi_surface_provenance=None)
        reader = unittest.mock.Mock(side_effect=AssertionError("must not read map"))
        self.assertEqual(self.run_projection(fight, reader), set())
        reader.assert_not_called()

        fight.native_qi_surface_provenance = dict(self.provenance)
        self.assertEqual(self.run_projection(fight, lambda *_args: None), set())

        fight.native_qi_surface_provenance = {"map_id": True, "source_sha256": "a" * 64}
        with self.assertRaisesRegex(
            ValueError, "Missing ordinary combat floor provenance"
        ):
            self.run_projection(fight, lambda *_args: set())

    def test_release_change_and_content_hash_mismatch_fail_closed(self):
        fight = NS(
            walkable=set(self.cells), native_qi_surface_provenance=dict(self.provenance)
        )
        with patch.object(
            subject._native_catalog, "release", side_effect=[self.release, "release-r2"]
        ), patch.object(
            subject._ground,
            "_catalog",
            return_value={
                "qualified_native_release": self.release,
                "maps": {
                    "42": {
                        "map_id": 42,
                        "status": "exported",
                        "source_sha256": "a" * 64,
                        "supported_cells": [[0, 0, 0]],
                        "unknown_material_cells": [],
                    }
                },
            },
        ):
            subject._MAP.cache_clear()
            try:
                with self.assertRaisesRegex(ValueError, "Native catalog changed"):
                    subject.unsupported_ground(fight, catalog_revision=self.release)
            finally:
                subject._MAP.cache_clear()

        fight.native_qi_surface_provenance["source_sha256"] = "c" * 64
        with patch.object(
            subject._native_catalog, "release", return_value=self.release
        ), patch.object(
            subject._ground,
            "_catalog",
            return_value={
                "qualified_native_release": self.release,
                "maps": {
                    "42": {
                        "map_id": 42,
                        "status": "exported",
                        "source_sha256": "a" * 64,
                        "supported_cells": [[0, 0, 0]],
                        "unknown_material_cells": [],
                    }
                },
            },
        ):
            subject._MAP.cache_clear()
            try:
                with self.assertRaisesRegex(ValueError, "physical source changed"):
                    subject.unsupported_ground(fight, catalog_revision=self.release)
            finally:
                subject._MAP.cache_clear()

    def test_custom_ground_reader_keeps_per_cell_fallback(self):
        fight = NS(
            walkable=set(self.cells), native_qi_surface_provenance=dict(self.provenance)
        )
        calls = []

        def custom_policy(current, cell):
            calls.append(cell)
            return cell != (1, 0, 0)

        with patch.object(subject._ground, "fight_supported", custom_policy):
            self.assertEqual(
                subject.unsupported_ground(fight, catalog_revision=self.release),
                {(1, 0, 0)},
            )
        self.assertEqual(set(calls), self.cells)


if __name__ == "__main__":
    unittest.main()
