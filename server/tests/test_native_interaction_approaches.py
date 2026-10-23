"""Original interaction height selection, orientation and authority regressions."""
import json
from pathlib import Path
import unittest

from wakfu_server.native_interaction_approaches import (
    native_approach_height,
    native_interaction_approaches,
)
from wakfu_server.combat_sn_path import NativePhysicalSurface, NativeSnColumns


def columns(map_id, rows, *, origin=(0, -216)):
    digest = "0" * 64
    data = dict(
        schema="native-Sn-Vy-columns-v1",
        map_id=map_id,
        source_sha256=digest,
        chunks=[
            dict(
                x=origin[0],
                y=origin[1],
                width=18,
                height=18,
                columns=[[x, y, surfaces] for (x, y), surfaces in rows.items()],
            )
        ],
    )
    return NativeSnColumns(data, map_id=map_id, source_sha256=digest)


class NativeInteractionApproachTests(unittest.TestCase):
    def test_height_selection_matches_original_jar_oracle(self):
        source = (
            Path(__file__).parent
            / "fixtures/native-interaction-approach-height-oracle.json"
        )
        for row in json.loads(source.read_text()):
            with self.subTest(row=row):
                surfaces = tuple(
                    NativePhysicalSurface(*r[:5], bool(r[5])) for r in row["surfaces"]
                )
                self.assertEqual(
                    native_approach_height(surfaces, row["object_z"]), row["expected"]
                )

    def test_elevated_object_uses_native_neighbor_floors_and_qv_order(self):
        # Map532/object20321 has no same-Z cardinal neighbor. Reuse its native
        # nearby floor heights without treating the object's Z as a walk floor.
        physical = columns(
            532,
            {
                (8, -213): [[4, 0, 0, 0, 0, False]],
                (8, -211): [[0, 0, 0, 0, 0, False], [6, 0, 0, 0, 0, False]],
            },
        )
        geometry = dict(
            map_id=532, cells=[[8, -213, 4], [8, -211, 0], [8, -211, 6]], edges=[]
        )
        result = native_interaction_approaches(
            geometry,
            (8, -212, 8),
            direction=1,
            approach_mask=15,
            physical_columns=physical,
        )
        self.assertEqual(result, ((8, -211, 6), (8, -213, 4)))
        # Geometry filtering cannot fall back to the lower floor when the
        # original selector's chosen upper floor is unavailable.
        geometry["cells"].remove([8, -211, 6])
        self.assertEqual(
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=1,
                approach_mask=15,
                physical_columns=physical,
            ),
            ((8, -213, 4),),
        )

    def test_orientation_mask_center_and_matching_map_authority(self):
        physical = columns(532, {(8, -213): [[4, 0, 0, 0, 0, False]]})
        geometry = dict(map_id=532, cells=[[8, -213, 4], [8, -212, 8]], edges=[])
        self.assertEqual(
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=7,
                approach_mask=1,
                physical_columns=physical,
            ),
            ((8, -213, 4),),
        )
        with self.assertRaisesRegex(ValueError, "center occupation"):
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=7,
                approach_mask=256,
                physical_columns=physical,
            )
        self.assertEqual(
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=7,
                approach_mask=256,
                physical_columns=physical,
                center_allowed=False,
            ),
            (),
        )
        with self.assertRaisesRegex(ValueError, "matching original"):
            native_interaction_approaches(
                dict(geometry, map_id=533),
                (8, -212, 8),
                direction=7,
                approach_mask=1,
                physical_columns=physical,
            )

    def test_missing_physical_authority_cannot_be_replaced_by_walk_cells(self):
        geometry = dict(map_id=532, cells=[[8, -213, 4]], edges=[])
        with self.assertRaisesRegex(ValueError, "physical columns"):
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=7,
                approach_mask=1,
                physical_columns={},
            )
        with self.assertRaisesRegex(ValueError, "topology chunk"):
            native_interaction_approaches(
                geometry,
                (8, -212, 8),
                direction=7,
                approach_mask=1,
                physical_columns=columns(532, {}, origin=(36, 36)),
            )
