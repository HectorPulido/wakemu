"""Prepared terrain preserves live LOS blockers, heights and strict fallback."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_los_geometry import (
    PreparedLosGeometry,
    prepare_los_geometry,
    prepared_permitted_xy,
)


class PreparedLosGeometryTests(unittest.TestCase):
    def setUp(self):
        self.cells = {(x, 0, 0) for x in range(4)}
        self.token = prepare_los_geometry(1134, self.cells)

    def read(self, token=None, *, cells=None, map_id=1134):
        return prepared_permitted_xy(
            self.token if token is None else token,
            map_id=map_id,
            walkable=self.cells if cells is None else cells,
        )

    def test_proof_is_immutable_scoped_and_cannot_be_supplied_by_callers(self):
        self.assertEqual(self.read(), frozenset((x, 0) for x in range(4)))
        with self.assertRaises(TypeError):
            PreparedLosGeometry()
        with self.assertRaises(AttributeError):
            self.token.permitted_xy = frozenset()
        self.assertIsNone(self.read(object.__new__(PreparedLosGeometry)))
        self.assertIsNone(self.read(SimpleNamespace(permitted_xy={(99, 99)})))
        self.assertIsNone(self.read(cells=set(self.cells)))
        self.assertIsNone(self.read(map_id=1135))
        self.assertIsNone(self.read(map_id=1134.0))

    def test_changed_terrain_falls_back_and_initial_invalid_dtypes_never_mint_proof(
        self,
    ):
        self.cells.remove((1, 0, 0))
        self.assertIsNone(self.read())
        for cell in ((False, 0, 0), (1.0, 0, 0), (1, 2), "123"):
            self.assertIsNone(prepare_los_geometry(1134, {cell}))
        self.assertIsNone(prepare_los_geometry(True, self.cells))
        self.assertIsNone(prepare_los_geometry(1134, list(self.cells)))

    def test_prepared_reader_keeps_blockers_heights_and_mutation_fallback_live(self):
        source, target = (0, 0, 0), (3, 0, 0)
        actors = {
            i: SimpleNamespace(
                id=i,
                hp=10,
                native_obstacle_id=None,
                native_los_height=6,
                position=position,
            )
            for i, position in ((1, source), (2, target), (3, (1, 1, 0)))
        }
        fight = SimpleNamespace(actors=actors, walkable=self.cells)
        footprints = {1: set(), 2: set(), 3: set()}

        def visible(token):
            return authoritative_visible(
                1134,
                source,
                target,
                fight,
                blocking_footprints=footprints,
                prepared_geometry=token,
            )

        with patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=[(True, {(1, 0), (2, 0)})],
        ) as rays:
            self.assertTrue(visible(self.token))
            self.assertEqual(visible(self.token), visible(None))
            actors[2].native_los_height = 20
            self.assertTrue(visible(self.token))
            self.assertEqual(rays.call_args.kwargs["target_height"], 20)
            footprints[3] = {(1, 0)}
            self.assertFalse(visible(self.token))
            self.assertEqual(visible(self.token), visible(None))
            footprints[3] = set()
            self.cells.remove((2, 0, 0))
            self.assertFalse(visible(self.token))
            self.assertEqual(visible(self.token), visible(None))
            del footprints[3]
            with self.assertRaises(ValueError):
                visible(self.token)

    def test_numeric_alias_replacement_retains_exact_legacy_membership_semantics(self):
        self.cells.remove((1, 0, 0))
        self.cells.add((1.0, 0, 0))
        self.assertEqual(self.read(), {(cell[0], cell[1]) for cell in self.cells})


if __name__ == "__main__":
    unittest.main()
