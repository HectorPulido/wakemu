"""Native scenario1340 wire contracts and scoped presentation cleanup."""

import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import astrub_cat_presentation as presentation


class AstrubCatPresentationTests(unittest.TestCase):
    def test_bootstrap_and_boss_scene_keep_exact_native_argument_order(self):
        cats = tuple(-100 - index for index in range(12))
        self.assertEqual(
            presentation.bootstrap(cats),
            (13411, struct.pack(">BiiB12q", 0, 10021, 1340, 12, *cats)),
        )
        last_room = (-310, -311, -312)
        scene = presentation.scene(23924, 7, *last_room)
        self.assertEqual(scene["position"], (15, -8, 0))
        self.assertEqual(
            scene["packets"][-1],
            (13411, struct.pack(">BiiB3q", 0, 23924, 1340, 3, *last_room)),
        )
        for event, arguments in (
            (10021, cats[:-1]),
            (10021, cats[:-1] + (cats[0],)),
            (23924, (-1, -2)),
            (23928, (-1, -2, -3, -4)),
            (23920, (-1,)),
            (23920, (True,)),
            (1, ()),
        ):
            with self.subTest(event=event), self.assertRaises(ValueError):
                presentation.packet(event, *arguments)

    def test_nekark_reposition_precedes_five_noncombat_actors_then_original_scene(self):
        actors = tuple(-401 - index for index in range(5))
        catalog = SimpleNamespace(
            reference=lambda identity: {
                "name": "Nekark" if identity == 4135 else "Tentáculo",
                "sprite_id": 177904135 if identity == 4135 else 177904133,
            }
        )
        with patch.dict(sys.modules, {"wakfu_server.monsters": catalog}):
            scene = presentation.nekark_scene(7, actors)
            rows = presentation.visual_rows(presentation.NEKARK_LAYOUT, actors)
        self.assertEqual(scene["position"], (149, 125, 0))
        self.assertEqual(
            [opcode for opcode, _ in scene["packets"]], [13530, *([12608] * 5), 13411]
        )
        self.assertEqual(
            scene["packets"][0], (13530, struct.pack(">qiihBi", 7, 149, 125, 0, 3, -1))
        )
        self.assertEqual(
            scene["packets"][-1],
            (13411, struct.pack(">BiiB5q", 0, 23928, 1340, 5, *actors)),
        )
        self.assertEqual([row["actor_id"] for row in rows], list(actors))
        self.assertEqual(
            [row["reference_id"] for row in rows], [4135, 4133, 4133, 4133, 4133]
        )
        self.assertEqual(
            [tuple(row[k] for k in ("x", "y", "z")) for row in rows],
            [
                (154, 136, -4),
                (150, 132, -4),
                (155, 129, -4),
                (154, 140, -4),
                (157, 141, -4),
            ],
        )
        self.assertTrue(
            all(row["map_id"] == 312 and row["native_action_ids"] == [] for row in rows)
        )

    def test_visual_retirement_is_typed_and_does_not_remove_player(self):
        actors = (-401, -402, -403, -404, -405)
        self.assertEqual(
            presentation.remove_visuals(actors),
            (
                12304,
                b"\x00\x00\x05"
                + b"".join(struct.pack(">Bq", 1, identity) for identity in actors),
            ),
        )
        for malformed in ((7,), (-1, -1), (True,)):
            with self.subTest(actors=malformed), self.assertRaises(ValueError):
                presentation.remove_visuals(malformed)
        self.assertEqual(presentation.TRISTEPIN_COMBAT_REFERENCE, 4691)
        self.assertEqual(presentation.TRISTEPIN_COMBAT_LEVEL, 6)
        self.assertEqual(presentation.AFTER_SCENE_EVENTS[23928], 23929)


if __name__ == "__main__":
    unittest.main()
