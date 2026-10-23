"""Reconstructed perimeter authority without loading combat catalogs."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_arena_selection import cardinal_border_cells
from wakfu_server.combat_battleground_border import (
    POLICY,
    RECONSTRUCTED_POLICY,
    install_battleground_border,
    ensure_battleground_border,
    verify_battleground_border,
)
from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections

# Original378/faP fields consumed by this constructor; execution callbacks are
# irrelevant to this shape/registration test and remain native elsewhere.
BORDER = dict(
    type="BATTLEGROUND_BORDER",
    native_class="bcF",
    raw_bdh=[],
    native_type_id=5,
    raw_bde=-1,
)


class ReconstructedBattlegroundBorderTests(unittest.TestCase):
    def fixture(self):
        cells = {(x, y, 0) for x in range(4) for y in range(4)}
        border = cardinal_border_cells(cells)
        actor = SimpleNamespace(id=7, position=(1, 1, 0), physical_radius=0, team=0)
        fight = SimpleNamespace(
            actors={7: actor},
            walkable=cells,
            native_effect_areas={},
            native_retained_records={},
            phase="active",
            current=actor,
            native_qi_snapshot=dict(
                x=0,
                y=0,
                width=4,
                height=4,
                cell_masks=[
                    128 | 4 if (x, y, 0) in border else 4
                    for y in range(4)
                    for x in range(4)
                ],
            ),
        )
        initialize_global_pv_collections(fight, (7,))
        arena = dict(
            native_border_policy=RECONSTRUCTED_POLICY,
            native_border_cells=border,
            min_z=0,
        )
        return fight, arena

    def test_native_fap_uses_actual_qi_perimeter_and_replays_one_identity(self):
        fight, arena = self.fixture()
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"378": BORDER},
        ):
            row = install_battleground_border(
                fight, arena, reference=378, identity=-100
            )
            self.assertEqual(row["reference"], 378)
            self.assertEqual(row["native_border_policy"], RECONSTRUCTED_POLICY)
            self.assertEqual(
                {tuple(c) for c in row["native_cells_xy"]},
                {c[:2] for c in arena["native_border_cells"]},
            )
            self.assertEqual(
                (row["owner_id"], row["level"], row["direction"]), (None, 0, -1)
            )
            verify_battleground_border(fight, row)
            fight.native_border_constructor = dict(
                reference=378, identity=-100, arena=arena
            )
            ensure_battleground_border(fight)
            self.assertIs(fight.native_effect_areas[-100], row)
            drift = dict(arena, native_border_policy=POLICY)
            fight.native_border_constructor["arena"] = drift
            with self.assertRaisesRegex(ValueError, "identity collision"):
                ensure_battleground_border(fight)

    def test_reconstructed_perimeter_rejects_subset_before_registration(self):
        fight, arena = self.fixture()
        arena["native_border_cells"] = set(arena["native_border_cells"]) - {(0, 0, 0)}
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"378": BORDER},
        ):
            with self.assertRaisesRegex(ValueError, "cardinal perimeter"):
                install_battleground_border(fight, arena, reference=378, identity=-100)
        self.assertEqual(fight.native_effect_areas, {})

    def test_reconstructed_scene_omits_generic910_but_compact_default_keeps_it(self):
        fight, arena = self.fixture()
        prepare_environment_glyphs(fight, arena, -100)
        self.assertEqual(fight.native_environment_glyph_constructors, [])
        compact, compact_arena = self.fixture()
        compact_arena["native_border_policy"] = POLICY
        prepare_environment_glyphs(compact, compact_arena, -100)
        self.assertEqual(len(compact.native_environment_glyph_constructors), 1)
        self.assertEqual(
            compact.native_environment_glyph_constructors[0]["reference"], 910
        )
