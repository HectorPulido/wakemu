"""Normalized placement authority and original native marker prerequisites."""
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxNativeMarkerPlacementTests(PostgresCase):
    def test_normalized_scene_has_original_cube_and_battery_markers(self):
        from wakfu_server import combat_encounter_marker_placements as placements
        from wakfu_server import native_catalog
        from wakfu_server.combat_nox_scene_layout import reconstructed_nox_scene
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            validate_point_prototype,
        )
        from wakfu_server.paths import DATA_ROOT

        placements._version.cache_clear()
        self.addCleanup(placements._version.cache_clear)
        geometry = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / ".runtime/ultimate-scenes-20261021/map-1435.json"
            ).read_text()
        )
        with patch.object(placements, "_database", return_value=self.store):
            layout = reconstructed_nox_scene(geometry)
            declarations = layout["native_initial_glyphs"]
            self.assertEqual(len(declarations), 17)
            self.assertEqual(sum(row["reference"] == 2050 for row in declarations), 5)
            self.assertEqual(sum(row["reference"] == 2051 for row in declarations), 1)
            self.assertEqual(
                {
                    row["reference"]
                    for row in declarations
                    if row["reference"] not in (2050, 2051)
                },
                set(range(2057, 2068)),
            )
            for reference in (2050, 2051):
                prototype = native_catalog.record(
                    DATA_ROOT / "native-effect-areas.json", "areas", reference
                )
                validate_point_prototype(prototype, level=0)
                self.assertEqual(prototype["effect_ids"], [])
            # The markers select original producer roots; no NPC/state is seeded.
            for root, marker, producer in (
                (401565, 2050, 401566),
                (401567, 2051, 401568),
            ):
                effect = native_catalog.record(
                    DATA_ROOT / "native-npc-spell-effect-trees.json", "effects", root
                )
                if effect is None:
                    effect = native_catalog.record(
                        DATA_ROOT / "combat-state-definitions.json", "effects", root
                    )
                self.assertEqual(effect["criteria"], f"IsSpecificArea({marker})")
                self.assertIn(producer, effect["children"])
            with self.assertRaisesRegex(ValueError, "no published"):
                placements.active_marker_placements(1435, (5306,))

    def test_immutable_placements_reject_mutation_and_extra_rows_fail_closed(self):
        from wakfu_server import combat_encounter_marker_placements as placements

        placements._version.cache_clear()
        self.addCleanup(placements._version.cache_clear)
        with patch.object(placements, "_database", return_value=self.store):
            original = placements.active_marker_placements(1435, (5664,))
            with self.assertRaises(TypeError):
                original.placements[0]["x"] = 999
            with self.assertRaises(Exception):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE encounter_marker_placements SET x=999 WHERE policy=%s",
                        (original.policy,),
                    )
            with self.assertRaisesRegex(ValueError, "placement data changed"):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO encounter_marker_placements VALUES(%s,17,2050,0,999,999,0)",
                        (original.policy,),
                    )
                    placements._version.cache_clear()
                    with patch.object(placements, "_database") as authority:
                        from contextlib import contextmanager

                        @contextmanager
                        def same_transaction():
                            yield db

                        authority.return_value.connection = same_transaction
                        placements._version(original.policy)
            placements._version.cache_clear()
            self.assertEqual(
                len(placements.active_marker_placements(1435, (5664,)).placements), 17
            )
