"""Advisory empty-cell search consumes actual registered QI footprints."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import (
    bounded_empty_targets,
    native_empty_target_predicate,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)


class RegisteredEmptyTargetTests(unittest.TestCase):
    def fight(self):
        caster = Actor(-200, 1, (-8, -7, -1), 100, 6, 3, 1, 53)
        enemy = Actor(7, 0, (-5, -7, -1), 100, 6, 3, 1, 53)
        caster.physical_radius = 1
        enemy.physical_radius = 0
        cells = {
            (x, y, z) for x in range(-10, -3) for y in range(-9, -4) for z in (-1, 2)
        }
        fight = Fight(
            99, [caster, enemy], cells, {0: {enemy.position}, 1: {caster.position}}
        )
        fight.native_qi_snapshot = dict(
            x=-10, y=-9, width=7, height=5, cell_masks=[256] * 35
        )
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={-200: 1, 7: 0})
        )
        return fight

    def test_actual_caster_radius_excludes_neighbor_and_all_floor_heights(self):
        fight = self.fight()
        empty = native_empty_target_predicate(fight)
        self.assertFalse(empty((-9, -7, -1)))
        self.assertFalse(empty((-9, -7, 2)))
        self.assertFalse(empty((-7, -6, 2)))
        self.assertFalse(empty((-5, -7, 2)))
        self.assertTrue(empty((-10, -7, -1)))
        targets = bounded_empty_targets(fight, (-8, -7, -1), 0, 6, limit=256)
        self.assertTrue(targets)
        self.assertTrue(all(empty(cell) for cell in targets))

    def test_stale_registered_actor_cannot_be_certified_empty(self):
        fight = self.fight()
        fight.actors[-200].position = (-7, -7, -1)
        with self.assertRaises(ValueError):
            native_empty_target_predicate(fight)
