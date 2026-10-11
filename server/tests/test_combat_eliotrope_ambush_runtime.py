"""Ambush uses actual registered facing after voluntary movement."""
import os
import unittest
from types import SimpleNamespace

import test_combat_eliotrope_runtime as runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EliotropeAmbushRuntimeTests(unittest.TestCase):
    fixture = runtime.EliotropeRuntimeTests.fixture
    cast = runtime.EliotropeRuntimeTests.cast
    next_owned_turn = runtime.EliotropeRuntimeTests.next_owned_turn

    def approach(self, data, back):
        from wakfu_server.combat_ordinary_authority import native_facing

        fight = data[2]
        actor, target = fight.actors[7], fight.actors[-7]
        queue = [(actor.position, ())]
        seen = {actor.position}
        selected = None
        while queue:
            cell, path = queue.pop(0)
            distance = abs(cell[0] - target.position[0]) + abs(
                cell[1] - target.position[1]
            )
            facing = native_facing(SimpleNamespace(position=cell), target)
            if 1 <= distance <= 3 and facing == ("BACK" if back else "FRONT"):
                selected = path
                break
            if len(path) >= 6:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cell[0] + dx, cell[1] + dy, cell[2])
                if nxt in fight.walkable and nxt not in seen and nxt != target.position:
                    seen.add(nxt)
                    queue.append((nxt, (*path, nxt)))
        self.assertIsNotNone(
            selected, (back, actor.position, target.position, target.direction)
        )
        while selected:
            steps = selected[: actor.mp]
            self.assertTrue(steps, "Native movement has no payable MP")
            fight.move(3, 7, list(steps))
            selected = selected[len(steps) :]
            if selected:
                self.next_owned_turn(data)
        self.assertEqual(native_facing(actor, target), "BACK" if back else "FRONT")

    def test_actual_back_attack_selects_ambush_bonus_and_front_does_not(self):
        observed = {}
        for back in (False, True):
            for enabled in (False, True):
                with self.subTest(back=back, enabled=enabled):
                    data = self.fixture(
                        passives=(4687,) if enabled else (), target_distance=2
                    )
                    self.approach(data, back)
                    self.assertNotIn(
                        3671,
                        {
                            state.reference
                            for state in data[2].actors[7].state_ledger.entries
                        },
                    )
                    enemy = data[2].actors[-7]
                    hp = enemy.hp
                    tx = self.cast(data, 4692, target=enemy.position)
                    observed[(back, enabled)] = hp - tx.fight.actors[-7].hp
                    self.assertGreater(observed[(back, enabled)], 0)
        self.assertEqual(observed[(True, True)], observed[(True, False)], observed)
        self.assertGreater(observed[(True, True)], observed[(False, True)], observed)
        self.assertEqual(observed[(False, True)], observed[(False, False)], observed)
