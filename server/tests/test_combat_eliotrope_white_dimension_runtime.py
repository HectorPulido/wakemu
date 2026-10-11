"""White Dimension consumes an actual occupied owned portal at turn start."""
import os
import unittest

import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeWhiteDimensionRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    place_portal = runtime.EliotropeRuntimeTests.place_portal
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn

    def walk_to_portal(self, data, cell):
        fight = data[2]
        actor = fight.actors[7]
        queue = [(actor.position, ())]
        seen = {actor.position}
        occupied = {a.position for a in fight.actors.values() if a.hp > 0 and a.id != 7}
        while queue:
            current, path = queue.pop(0)
            if current == cell:
                fight.move(3, 7, list(path))
                self.assertEqual(actor.position, cell)
                return
            if len(path) >= actor.mp:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (current[0] + dx, current[1] + dy, current[2])
                if nxt in fight.walkable and nxt not in seen and nxt not in occupied:
                    seen.add(nxt)
                    queue.append((nxt, (*path, nxt)))
        self.fail("No actual movement path to the created portal")

    def test_actual_portal_start_selects_calm_gain_and_exalted_loss(self):
        observed = {}
        for exalted in (False, True):
            for equipped in (False, True):
                with self.subTest(exalted=exalted, equipped=equipped):
                    data = self.fixture(passives=(7203,) if equipped else ())
                    if exalted:
                        tx = self.cast(data, 4682, target=data[2].actors[7].position)
                        data = (*data[:2], tx.fight, *data[3:])
                    tx = self.place_portal(
                        data, near=data[2].actors[7].position, action_id=12
                    )
                    data = (*data[:2], tx.fight, *data[3:])
                    portal = next(
                        a
                        for a in data[2].native_effect_areas.values()
                        if a.get("reference") == 823
                    )
                    self.walk_to_portal(data, tuple(portal["cell"]))
                    self.next_owned_turn(data)
                    actor = data[2].actors[7]
                    observed[(exalted, equipped)] = actor.effect_stats.get(9, 0)
        self.assertEqual(
            observed[(False, True)] - observed[(False, False)], 40, observed
        )
        self.assertEqual(
            observed[(True, True)] - observed[(True, False)], -40, observed
        )
