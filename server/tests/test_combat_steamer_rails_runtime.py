"""Actual Steamer casts build rails consumed by the normal movement FSM."""
import os
import unittest
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerRailsRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_two_owned_microbot_casts_reduce_real_movement_and_recast_removes_network(
        self,
    ):
        fixture = self.fixture()
        actor = fixture[2].actors[7]
        candidates = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cells = [
                tuple(
                    (
                        actor.position[0] + dx * n,
                        actor.position[1] + dy * n,
                        actor.position[2],
                    )
                )
                for n in range(1, 5)
            ]
            if all(
                cell in fixture[2].walkable
                and not any(a.position == cell for a in fixture[2].actors.values())
                for cell in cells
            ):
                candidates.append(cells)
        self.assertTrue(
            candidates, "Actual arena has no unoccupied four-cell rail candidate"
        )
        selected, rejected = None, []
        for cells in candidates:
            try:
                first = self.cast(fixture, 7008, target=cells[0], action_id=2)
                second_fixture = self.adopt(fixture, first.fight)
                second = self.cast(second_fixture, 7008, target=cells[-1], action_id=3)
            except ValueError as error:
                rejected.append(str(error))
                continue
            selected = cells, second
            break
        self.assertIsNotNone(selected, rejected)
        cells, second = selected
        fight = second.fight
        network = fight.native_microbot_networks[7]
        self.assertEqual(len(network["microbot_ids"]), 2)
        self.assertTrue(network["segments"])
        self.assertTrue(set(cells) <= {tuple(cell) for cell in network["cells"]})
        before_mp = fight.actors[7].mp
        fight.move(3, 7, [cells[0]])
        self.assertEqual(fight.actors[7].mp, before_mp - 1)
        fight.move(3, 7, cells[1:])
        self.assertEqual(fight.actors[7].mp, before_mp - 2)
        self.assertEqual(fight.actors[7].position, cells[-1])
        # Native7008 permits only two casts per turn. Removal is exercised
        # after a real owner cycle, not by bypassing its usage guard.
        removal_fixture = self.next_owned_turn(self.adopt(fixture, fight))
        removed = self.cast(removal_fixture, 7008, target=cells[0], action_id=4)
        self.assertEqual(
            len(removed.fight.native_microbot_networks[7]["microbot_ids"]), 1
        )
        self.assertEqual(removed.fight.native_microbot_networks[7]["segments"], [])
        self.assertEqual(len(fight.native_microbot_networks[7]["microbot_ids"]), 2)
