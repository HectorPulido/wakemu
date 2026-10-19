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
        from wakfu_server.combat_microbot_rails import SOURCE as RAIL_SOURCE, rail_cells
        from wakfu_server.combat_effect_removal import _identity_fields
        import struct

        rail_areas = [
            row
            for row in fight.native_effect_areas.values()
            if row.get("native_microbot_rail_source") == RAIL_SOURCE
            and row.get("owner_id") == 7
        ]
        expected_rails = set(rail_cells(network))
        actual_rails = {(*tuple(row["cell"]), row["direction"]) for row in rail_areas}
        self.assertEqual(actual_rails, expected_rails)
        self.assertTrue(
            {tuple(cell) for cell in network["cells"]}
            <= {tuple(row["cell"]) for row in rail_areas}
        )
        rail_creations = []
        for opcode, body in second.packets:
            if opcode != 12613 or len(body) < 19:
                continue
            fight_id, _action, reference, immediate, family, size = struct.unpack_from(
                ">iiiBih", body
            )
            if family != 339:
                continue
            payload = body[19 : 19 + size]
            messages = {}
            identities = _identity_fields(
                payload, integer_fields=(1, 2, 3, 4, 6), messages=messages
            )
            identities.update(
                _identity_fields(messages.get(8, b""), integer_fields=(14, 16, 17, 21))
            )
            if identities.get(4) == 385:
                rail_creations.append((fight_id, reference, immediate, identities))
        self.assertEqual(len(rail_creations), len(expected_rails))
        self.assertTrue(
            all(
                fight_id == fight.id
                and reference == -1
                and immediate == 1
                and fields.get(4) == 385
                and fields.get(6) == 7
                for fight_id, reference, immediate, fields in rail_creations
            ),
            rail_creations,
        )
        self.assertEqual(
            {fields.get(21) for _, _, _, fields in rail_creations},
            {row["uid"] for row in rail_areas},
        )
        self.assertEqual(
            {fields.get(1) for _, _, _, fields in rail_creations},
            {row["effect_uid"] for row in rail_areas},
        )
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
        self.assertFalse(
            [
                row
                for row in removed.fight.native_effect_areas.values()
                if row.get("native_microbot_rail_source") == RAIL_SOURCE
                and row.get("owner_id") == 7
            ]
        )
        removed_area_ids = {row["uid"] for row in rail_areas}
        rail_removals = {
            struct.unpack(">iiiq", body)[3]
            for opcode, body in removed.packets
            if opcode == 13726 and len(body) == struct.calcsize(">iiiq")
        }
        self.assertEqual(rail_removals, removed_area_ids)
        self.assertEqual(len(fight.native_microbot_networks[7]["microbot_ids"]), 2)
