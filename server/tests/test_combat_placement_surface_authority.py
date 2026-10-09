"""Placement reconstruction preserves selected native surfaces on first/retry."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_placement_policy import _arena
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


class PlacementSurfaceAuthorityTests(unittest.TestCase):
    def test_layout_reconstruction_preserves_nonzero_index_and_provenance(self):
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=527,
                source_sha256="a" * 64,
                chunks=[
                    dict(
                        x=0,
                        y=0,
                        width=2,
                        height=1,
                        columns=[[0, 0, [[-1, 0], [3, 0]]], [1, 0, [[3, 0]]]],
                    )
                ],
            ),
            map_id=527,
            source_sha256="a" * 64,
        )
        layout = dict(
            cells=[[0, 0, 3], [1, 0, 3]],
            edges=[],
            wire_instance_id=7,
            placement={"0": [[0, 0, 3]], "1": [[1, 0, 3]]},
        )
        provenance = dict(
            map_id=527,
            source_sha256="a" * 64,
            output_sha256="b" * 64,
            manifest_sha256="c" * 64,
        )
        with patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            return_value=surfaces,
        ), patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
            return_value=provenance,
        ):
            first = _arena(527, 0, layout)
            retry = _arena(527, 0, layout)
        self.assertEqual(first, retry)
        self.assertEqual(first["native_qi_surface_provenance"], provenance)
        self.assertEqual(first["cell_masks"][0] & 63, 1)

    def test_native_decode_failure_is_not_replaced_with_zero_index(self):
        layout = dict(
            cells=[[0, 0, 3], [1, 0, 3]],
            edges=[],
            wire_instance_id=7,
            placement={"0": [[0, 0, 3]], "1": [[1, 0, 3]]},
        )
        with patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            side_effect=ValueError("Native QI decoding failed"),
        ):
            with self.assertRaisesRegex(ValueError, "decoding failed"):
                _arena(527, 0, layout)
