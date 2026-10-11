"""Directional free-cell witnesses require a target beyond the empty centre."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import bounded_empty_targets, effect_search_envelope
from wakfu_server.combat_area_geometry import native_area_contains
from wakfu_server.combat_state import Actor


class DirectionalFreeCellWitnessTests(unittest.TestCase):
    # Installed spell4871 roots152781/343044/152783/343045 share this shape.
    effect = {"area_class": "anJ", "area_native": "t inv-barre:0-pied:4"}

    def fixture(self, enemy_cell):
        caster = Actor(-200, 1, (-8, -7, -1), 100, 8, 4, 1, 68)
        enemy = Actor(7, 0, enemy_cell, 100, 6, 3, 1, 68)
        caster.physical_radius = enemy.physical_radius = 0
        return SimpleNamespace(
            actors={-200: caster, 7: enemy},
            walkable={(x, y, -1) for x in range(-13, -2) for y in range(-12, -1)},
        )

    def test_existing_envelope_and_candidate_order_find_intervening_empty_cell(self):
        self.assertEqual(
            effect_search_envelope({"152781": self.effect}, [152781], 1), 5
        )
        fight = self.fixture((-10, -7, -1))
        source = fight.actors[-200].position
        target = bounded_empty_targets(fight, source, 1, 1)[0]
        self.assertEqual(target, (-9, -7, -1))
        self.assertTrue(
            native_area_contains(
                self.effect,
                origin=target,
                reference=source,
                point=fight.actors[7].position,
                radius=0,
            )
        )

    def test_adjacent_enemy_is_not_selected_by_orthogonal_empty_cast(self):
        fight = self.fixture((-9, -7, -1))
        source = fight.actors[-200].position
        for target in bounded_empty_targets(fight, source, 1, 1):
            self.assertFalse(
                native_area_contains(
                    self.effect,
                    origin=target,
                    reference=source,
                    point=fight.actors[7].position,
                    radius=0,
                )
            )
