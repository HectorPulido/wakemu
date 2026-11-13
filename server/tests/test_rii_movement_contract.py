import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_movement_contract as movement


class MovementLessonTests(unittest.TestCase):
    def setUp(self):
        self.plan = patch.object(movement, "_native_plan_valid", return_value=True)
        self.native_plan = self.plan.start()
        self.addCleanup(self.plan.stop)

    def fight(self):
        actors = {
            1: SimpleNamespace(id=1, position=(0, 0, 0), team=0, hp=100),
            -2: SimpleNamespace(id=-2, position=(1, 0, 0), team=1, hp=100),
        }
        walkable = {(x, y, 0) for x in range(-5, 6) for y in range(-5, 6)}
        return SimpleNamespace(
            id=55,
            phase="active",
            actors=actors,
            walkable=walkable,
            rii_movement_lesson_contract={
                "owner": 1,
                "target": -2,
                "hits": 0,
                "initialized": True,
                "marker": [2, 0, 0],
                "state_uid": 99,
            },
            events=[],
            _event=lambda *a, **kw: None,
        )

    def test_authoritative_effect_owner_and_actual_movement_are_required(self):
        fight = self.fight()
        sack = fight.actors[-2]
        sack.position = (2, 0, 0)
        for caster, effect, before in (
            (2, 367262, (1, 0, 0)),
            (1, 1, (1, 0, 0)),
            (1, 367262, (2, 0, 0)),
        ):
            self.assertFalse(
                movement.observe(
                    fight,
                    caster_id=caster,
                    effect_reference=effect,
                    before=before,
                    packets=[],
                )
            )
        self.assertEqual(fight.rii_movement_lesson_contract["hits"], 0)
        self.assertTrue(
            movement.observe(
                fight,
                caster_id=1,
                effect_reference=367262,
                before=(1, 0, 0),
                packets=[],
            )
        )
        self.assertEqual(fight.rii_movement_lesson_contract["hits"], 1)
        self.assertNotEqual(fight.rii_movement_lesson_contract["marker"], [2, 0, 0])

    def test_four_moves_finish_without_faking_death_and_preview_isolated(self):
        original = self.fight()
        fight = copy.deepcopy(original)
        with patch("wakfu_server.achievements.rii_lesson_state.remove"), patch(
            "wakfu_server.achievements.rii_lesson_state.install", return_value=100
        ):
            for _ in range(4):
                before = fight.actors[-2].position
                fight.actors[-2].position = tuple(
                    fight.rii_movement_lesson_contract["marker"]
                )
                self.assertTrue(
                    movement.observe(
                        fight,
                        caster_id=1,
                        effect_reference=367263,
                        before=before,
                        packets=[],
                    )
                )
        self.assertTrue(movement.finish_if_qualified(fight))
        self.assertEqual(
            (fight.phase, fight.winner, fight.actors[-2].hp), ("finished", 0, 100)
        )
        self.assertEqual(original.rii_movement_lesson_contract["hits"], 0)

    def test_selection_rejects_blocked_edges_and_obstacles(self):
        fight = self.fight()
        sack = fight.actors[-2]
        fight.edges = {(sack.position, (2, 0, 0))}
        fight.native_obstacle_cells = {(2, 0, 0)}
        with self.assertRaises(ValueError):
            movement.choose_cell(fight, sack, fight.actors[1])
        fight.native_obstacle_cells = set()
        self.native_plan.return_value = False
        with self.assertRaises(ValueError):
            movement.choose_cell(fight, sack, fight.actors[1])

    def test_last_marker_follows_owner_reposition_without_counting(self):
        fight = self.fight()
        fight.rii_movement_lesson_contract.update(hits=3, marker=[0, 0, 0])
        fight.actors[1].position = (-1, 0, 0)
        packets = []
        self.assertFalse(
            movement.observe(
                fight,
                caster_id=1,
                effect_reference=367264,
                before=fight.actors[-2].position,
                packets=packets,
            )
        )
        self.assertEqual(fight.rii_movement_lesson_contract["hits"], 3)
        self.assertEqual(fight.rii_movement_lesson_contract["marker"], [-1, 0, 0])

    def test_terminal_cleanup_removes_both_state_carriers_for_owner_only(self):
        from wakfu_server import rii_lesson_grants

        fight = self.fight()
        contract = fight.rii_movement_lesson_contract
        contract.update(grant_uids=[1, 2, 3, 4], state_uid=99, owner_state_uid=100)
        fight.state_wire_payloads = {99: "00", 100: "00"}
        with patch.object(rii_lesson_grants, "remove") as remove_grants, patch(
            "wakfu_server.achievements.rii_lesson_state.remove"
        ) as remove_state:
            self.assertFalse(
                rii_lesson_grants.remove_movement_if_present(
                    fight, [], action_id=8, owner_ids={2}
                )
            )
            remove_grants.assert_not_called()
            packets = []
            self.assertTrue(
                rii_lesson_grants.remove_movement_if_present(
                    fight, packets, action_id=8, owner_ids={1}
                )
            )
        remove_grants.assert_called_once_with(
            fight, 1, [1, 2, 3, 4], packets, action_id=8, lesson="movement"
        )
        self.assertEqual(
            [
                (call.kwargs["target_id"], call.kwargs["uid"])
                for call in remove_state.call_args_list
            ],
            [(-2, 99), (1, 100)],
        )

    def test_selected_markers_offer_a_teleport_and_push_or_pull_plan(self):
        fight = self.fight()
        owner, sack = fight.actors[1], fight.actors[-2]
        # Inspect every cell from several caster/sack configurations; each
        # returned marker must have an unoccupied aligned caster position
        # within the native four-cell teleport range.
        for owner_pos, target_pos in (
            ((0, 0, 0), (2, 0, 0)),
            ((-3, 0, 0), (0, 2, 0)),
            ((2, -2, 0), (0, 0, 0)),
        ):
            owner.position, sack.position = owner_pos, target_pos
            marker = movement.choose_cell(fight, sack, owner)
            dx, dy = marker[0] - target_pos[0], marker[1] - target_pos[1]
            stands = (
                (target_pos[0] - dx, target_pos[1] - dy, 0),
                (target_pos[0] + 2 * dx, target_pos[1] + 2 * dy, 0),
            )
            self.assertTrue(
                any(
                    pos in fight.walkable
                    and pos != sack.position
                    and abs(pos[0] - owner_pos[0]) + abs(pos[1] - owner_pos[1]) <= 4
                    for pos in stands
                )
            )


if __name__ == "__main__":
    unittest.main()
