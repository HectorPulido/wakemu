import struct
import unittest
from types import SimpleNamespace

from wakfu_server.combat_environment_glyphs import (
    prepare_environment_glyphs,
    environment_sections,
    ensure_environment_glyphs,
)
from wakfu_server.combat_battleground_border import POLICY
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections


class EnvironmentalGlyphPolicyTests(unittest.TestCase):
    def fixture(self):
        cells = {(x, y, 3) for x in range(5) for y in range(5)}
        border = {c for c in cells if c[0] in (0, 4) or c[1] in (0, 4)}
        actor = SimpleNamespace(id=7, position=(1, 1, 3))
        fight = SimpleNamespace(
            actors={7: actor}, walkable=cells, native_effect_areas={}
        )
        initialize_global_pv_collections(fight, (7,))
        return fight, dict(native_border_policy=POLICY, native_border_cells=border)

    def test_selected_interior_and_actual_native_myK_fields(self):
        fight, arena = self.fixture()
        prepare_environment_glyphs(fight, arena, -100)
        (section,) = environment_sections(fight)
        self.assertEqual(
            struct.unpack_from(">qqiihqhib", section),
            (910, -101, 2, 2, 3, 0, 0, -1, -1),
        )
        self.assertEqual(
            struct.unpack_from(">Biihb", section, struct.calcsize(">qqiihqhib")),
            (0, 0, 0, 0, -1),
        )
        ensure_environment_glyphs(fight)
        row = fight.native_effect_areas[-101]
        self.assertIsNone(row["owner_id"])
        self.assertEqual(row["native_cells_xy"], ((2, 2),))
        ensure_environment_glyphs(fight)
        self.assertEqual(environment_sections(fight), [section])
        # JSON checkpoint containers may restore tuples as lists.
        row["cell"] = list(row["cell"])
        row["native_cells_xy"] = [list(cell) for cell in row["native_cells_xy"]]
        self.assertEqual(environment_sections(fight), [section])

    def test_no_free_interior_emits_no_glyph(self):
        fight, arena = self.fixture()
        arena["native_border_cells"] = set(fight.walkable)
        prepare_environment_glyphs(fight, arena, -100)
        self.assertEqual(environment_sections(fight), [])
        ensure_environment_glyphs(fight)
        self.assertEqual(fight.native_effect_areas, {})
