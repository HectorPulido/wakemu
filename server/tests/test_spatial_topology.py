"""Attested graphs stay immutable while native policies observe live changes."""

import copy
import json
import unittest

from wakfu_server.spatial_native import NativeSpatial
from wakfu_server.spatial_topology import directed_path, freeze_geometry


class SpatialTopologyTests(unittest.TestCase):
    def geometry(self):
        return {"cells": [[0, 0, 0], [1, 0, 0]], "edges": [[[0, 0, 0], [1, 0, 0]]]}

    def request(self):
        return dict(
            start_position=dict(x=0, y=0, z=0),
            end_position=dict(x=1, y=0, z=0),
            steps=[dict(dx=1, dy=0, dz=0)],
        )

    def test_snapshot_preserves_json_and_deepcopy_but_rejects_nested_mutation(self):
        source = self.geometry()
        frozen = freeze_geometry(source, "test-generation:map:sourcehash")
        self.assertEqual(source, frozen)
        self.assertEqual(json.dumps(source), json.dumps(frozen))
        self.assertIs(copy.deepcopy(frozen), frozen)
        source["cells"][1][0] = 9
        self.assertEqual(frozen["cells"][1][0], 1)
        for mutate in (
            lambda: frozen.update(cells=[]),
            lambda: frozen["cells"].append([2, 0, 0]),
            lambda: frozen["edges"][0][1].__setitem__(0, 9),
            lambda: setattr(frozen, "authority", "forged"),
        ):
            with self.assertRaises(TypeError):
                mutate()

    def test_cached_graph_observes_changed_live_gate_and_allowed_policy(self):
        frozen = freeze_geometry(self.geometry(), "test-generation:map:live-policy")
        with NativeSpatial("spatial-topology-policy") as native:
            self.assertEqual(
                directed_path(native, frozen, self.request(), []), [1, 0, 0]
            )
            with self.assertRaises(ValueError):
                directed_path(native, frozen, self.request(), [[1, 0, 0]])
            with self.assertRaises(ValueError):
                directed_path(
                    native, frozen, self.request(), [], allowed_cells={(0, 0, 0)}
                )
            self.assertEqual(
                directed_path(native, frozen, self.request(), []), [1, 0, 0]
            )

    def test_mutable_synthetic_graph_is_revalidated_after_edit(self):
        geometry = self.geometry()
        with NativeSpatial("spatial-topology-mutable") as native:
            self.assertEqual(
                directed_path(native, geometry, self.request(), []), [1, 0, 0]
            )
            geometry["edges"].clear()
            with self.assertRaises(ValueError):
                directed_path(native, geometry, self.request(), [])
