import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_sn_path import NativeSnColumns
from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
    direct_linear_path_rule,
    native_linear_path_blocked_receipts,
)


class NativeLinearPathSnapshotTests(unittest.TestCase):
    SOURCE = (-6, -13, 88)
    TARGET = (-6, -17, 88)

    @classmethod
    def columns(cls, blocked, chunk_count=1):
        def surface_rows(y):
            if blocked and y == -14:
                return []  # Map 363's empty physical column in the Sn segment.
            return [[88, 0, 0, 0, 0, False]]

        chunks = [
            {
                "x": -15,
                "y": -20,
                "width": 18,
                "height": 18,
                "columns": [[-6, y, surface_rows(y)] for y in range(-17, -12)],
            }
        ]
        # Map 363 publishes 149 chunks. Empty off-route chunks keep this fixture
        # synthetic while guarding the production bound against rejecting it.
        for index in range(chunk_count - 1):
            chunks.append(
                {
                    "x": 100 + index * 20,
                    "y": 100,
                    "width": 18,
                    "height": 18,
                    "columns": [],
                }
            )
        data = {
            "schema": "native-Sn-Vy-columns-v1",
            "map_id": 363,
            "source_sha256": "a" * 64,
            "chunks": chunks,
        }
        return NativeSnColumns(data, map_id=363, source_sha256="a" * 64)

    def test_5777_target_invariant_linear_rule_receipt_and_fallbacks(self):
        self.assertTrue(
            direct_linear_path_rule(
                {
                    "linear": True,
                    "diagonal": False,
                    "linear_path": True,
                    "path_option": False,
                    "conditional": [],
                    "categories": [],
                }
            )
        )
        for changes in (
            {"diagonal": True},
            {"linear": False},
            {"path_option": True},
            {"conditional": [1]},
            {"categories": [1]},
        ):
            rule = {
                "linear": True,
                "diagonal": False,
                "linear_path": True,
                "path_option": False,
                "conditional": [],
                "categories": [],
            }
            rule.update(changes)
            self.assertFalse(direct_linear_path_rule(rule))

        actor = SimpleNamespace(
            id=10,
            position=self.SOURCE,
            native_physical_position=self.SOURCE,
            native_los_height=6,
            physical_radius=0,
            native_jump_height=1,
        )
        target = SimpleNamespace(id=20, position=self.TARGET, hp=100)
        indices = {self.SOURCE: 0, self.TARGET: 1}
        with patch.object(
            NativeSnColumns,
            "from_published",
            side_effect=AssertionError("unexpected catalog read"),
        ):
            blocked = native_linear_path_blocked_receipts(
                self.columns(True, chunk_count=149), actor, [target], indices, 363, 363
            )
            visible = native_linear_path_blocked_receipts(
                self.columns(False), actor, [target], indices, 363, 363
            )
            missing_provenance = native_linear_path_blocked_receipts(
                self.columns(True), actor, [target], indices, 364, 363
            )
            moved = SimpleNamespace(
                id=actor.id,
                position=actor.position,
                native_physical_position=(-5, -13, 88),
                native_los_height=6,
                physical_radius=0,
                native_jump_height=1,
            )
            stale_origin = native_linear_path_blocked_receipts(
                self.columns(True), moved, [target], indices, 363, 363
            )

        self.assertEqual([[0, 1, 20]], blocked)
        self.assertEqual([], visible)
        self.assertEqual([], missing_provenance)
        self.assertEqual([], stale_origin)


if __name__ == "__main__":
    unittest.main()
