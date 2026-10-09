"""Cell groups use persisted surface authority, not incidental Fight attributes."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_cell_group import native_cell_group_population


class CellGroupMapContextTests(unittest.TestCase):
    def population(self, fight):
        return native_cell_group_population(
            fight,
            {"area_class": "anA"},
            {"parameters": [1]},
            SimpleNamespace(reference=1, caster_id=7, cell=(0, 0, 0)),
        )

    def test_owned_surface_map_without_raw_fight_map_attribute(self):
        provenance = {"map_id": 42, "source_sha256": "attested"}
        fight = SimpleNamespace(
            native_qi_surface_provenance=provenance,
            actors={7: SimpleNamespace(position=(0, 0, 3))},
        )
        qi = SimpleNamespace(x=0, y=0, width=1, masks=[0], aK=lambda x, y: True)
        surfaces = SimpleNamespace(
            chunks=[((0, 0, 1, 1), {(0, 0): [SimpleNamespace(z=3)]})]
        )
        with patch(
            "wakfu_server.combat_cell_group.native_cell_criterion_presence",
            return_value=False,
        ), patch(
            "wakfu_server.combat_qi_fight.current_registry",
            return_value=SimpleNamespace(snapshot=lambda: qi),
        ), patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
            return_value=dict(provenance),
        ), patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            return_value=surfaces,
        ) as load:
            self.assertEqual(self.population(fight), ((0, 0, 3),))
            load.assert_called_once_with(42)

    def test_missing_or_mismatching_provenance_rejects_before_loading(self):
        for provenance in (None, {"map_id": 42, "source_sha256": "stale"}):
            fight = SimpleNamespace(native_qi_surface_provenance=provenance, map_id=999)
            with patch(
                "wakfu_server.combat_cell_group.native_cell_criterion_presence",
                return_value=False,
            ), patch(
                "wakfu_server.combat_qi_fight.current_registry",
                return_value=SimpleNamespace(snapshot=lambda: None),
            ), patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
                return_value={"map_id": 42, "source_sha256": "attested"},
            ), patch(
                "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces"
            ) as load:
                with self.assertRaisesRegex(ValueError, "provenance"):
                    self.population(fight)
                load.assert_not_called()
