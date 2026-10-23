"""Point faY declaration/codec boundaries without loading native catalogs."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_encounter_glyph_bootstrap import (
    point_glyph_row,
    point_glyph_section,
    prepare_declared_glyphs,
)


class EncounterGlyphBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.definition = dict(
            type="GLYPH",
            native_class="bcT",
            native_shape_class="anD",
            shape_parameters=[],
            raw_bdh=[],
            raw_bdf=0,
            raw_bdg=[],
            native_type_id=0,
            native_container_type=3,
            native_hour_contract=False,
            native_area_properties=[8],
            maximum_level=0,
            raw_bde=-1,
        )
        self.definitions = {"1837": self.definition, "1838": self.definition}
        self.fight = SimpleNamespace(
            actors={7: SimpleNamespace(position=(0, 0, 0), physical_radius=0, hp=100)},
            walkable={(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)},
            native_effect_areas={},
            native_border_cells={(3, 0, 0)},
        )
        self.arena = dict(
            native_initial_glyphs=[
                dict(reference=1837, cell=[1, 0, 0]),
                dict(reference=1838, cell=[2, 0, 0]),
            ],
            native_initial_glyph_policy="wakemu.test.original-markers.v1",
            native_initial_glyph_authority="explicit_reconstructed_null_owner",
        )

    def prepare(self, arena=None, definitions=None):
        return prepare_declared_glyphs(
            self.fight,
            self.arena if arena is None else arena,
            100,
            self.definitions if definitions is None else definitions,
        )

    def test_declares_original_references_with_distinct_pv_ids_before_commit(self):
        result = self.prepare()
        self.assertEqual([row["uid"] for row in result], [99, 98])
        self.assertEqual([row["reference"] for row in result], [1837, 1838])
        self.assertEqual(self.fight.native_effect_areas, {})
        self.assertFalse(hasattr(self.fight, "native_environment_glyph_constructors"))

    def test_rejects_occupied_duplicate_border_and_unavailable_cells_atomically(self):
        for cell in ([0, 0, 0], [1, 0, 0], [3, 0, 0], [99, 0, 0]):
            with self.subTest(cell=cell):
                arena = deepcopy(self.arena)
                arena["native_initial_glyphs"][1]["cell"] = cell
                with self.assertRaises(ValueError):
                    self.prepare(arena)
                self.assertEqual(self.fight.native_effect_areas, {})

    def test_rejects_other_constructor_shapes_and_effect_overrides(self):
        for key, value in (
            ("native_shape_class", "anG"),
            ("raw_bdh", [1]),
            ("native_area_properties", [12]),
        ):
            with self.subTest(key=key):
                definitions = deepcopy(self.definitions)
                definitions["1838"][key] = value
                with self.assertRaises(ValueError):
                    self.prepare(definitions=definitions)
        arena = deepcopy(self.arena)
        arena["native_initial_glyphs"][0]["effect_reference"] = 378794
        with self.assertRaises(ValueError):
            self.prepare(arena)

    def test_pre_snapshot_uses_declared_footprint_without_defaulting_radius(self):
        actor = self.fight.actors[7]
        actor.physical_radius, actor.team = None, 0
        with self.assertRaisesRegex(ValueError, "footprint authority"):
            self.prepare()
        self.arena["native_encounter_scene_layout"] = dict(
            party_placement_cells=[[0, 0, 0]],
            boss_footprint=[],
        )
        self.assertEqual(len(self.prepare()), 2)
        self.arena["native_encounter_scene_layout"]["party_placement_cells"].append(
            [1, 0, 0]
        )
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.prepare()

    def test_pre_snapshot_reads_frozen_nox_roles_instead_of_fixed_team_zero(self):
        from wakfu_server.combat_encounter_roles import role_assignment
        from encounter_role_fixture import role_database_fixture

        with role_database_fixture():
            self.fight.native_encounter_roles = role_assignment(1435, (5664,)).record()
        actor = self.fight.actors[7]
        actor.physical_radius, actor.team = None, 1
        self.arena["native_encounter_scene_layout"] = dict(
            party_placement_cells=[[0, 0, 0]],
            boss_footprint=[[3, 0, 0]],
        )
        with role_database_fixture():
            self.assertEqual(len(self.prepare()), 2)

    def test_row_and_myk_codec_keep_null_owner_and_original_level(self):
        source = self.prepare()[0]
        row = point_glyph_row(source, self.definition)
        self.assertIsNone(row["owner_id"])
        self.assertFalse(row["native_qq_bhi"])
        self.assertEqual(row["native_fight_affiliation"], -1)
        self.assertEqual(row["native_cells_xy"], ((1, 0),))
        self.assertEqual(row["child_effect_uids"], {})
        data = point_glyph_section(source, cell=row["cell"], visual_owner=0)
        self.assertEqual(
            data,
            struct.pack(
                ">qqiihqhib",
                1837,
                99,
                1,
                0,
                0,
                0,
                0,
                -1,
                -1,
            )
            + struct.pack(">Biihb", 0, 0, 0, 0, -1),
        )

    def test_shared_install_projection_and_removed_constructor_do_not_respawn(self):
        from wakfu_server.combat_environment_glyphs import (
            environment_sections,
            ensure_environment_glyphs,
            prepare_environment_glyphs,
            verify_environment_glyph,
        )

        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=self.definitions,
        ), patch(
            "wakfu_server.combat_global_pv_collections.register_global_area"
        ) as register:
            prepare_environment_glyphs(self.fight, self.arena, 100)
            before = environment_sections(self.fight, viewer_id=7)
            ensure_environment_glyphs(self.fight)
            self.assertEqual(register.call_count, 2)
            self.assertEqual(environment_sections(self.fight, viewer_id=7), before)
            self.assertEqual(struct.unpack_from(">q", before[0], 26), (0,))
            row = self.fight.native_effect_areas[99]
            verify_environment_glyph(self.fight, row)
            del self.fight.native_effect_areas[99]
            ensure_environment_glyphs(self.fight)
            self.assertNotIn(99, self.fight.native_effect_areas)
            self.assertEqual(len(environment_sections(self.fight)), 1)
            self.assertEqual(register.call_count, 2)


if __name__ == "__main__":
    unittest.main()
