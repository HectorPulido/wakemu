import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_states_contract as lesson


class StatesContractTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(id=7, team=0, hp=100, position=(6, 0, 0))
        self.target = SimpleNamespace(id=-3, team=1, hp=100, position=(0, 0, 0))
        self.fight = SimpleNamespace(
            id=11,
            phase="active",
            actors={7: self.owner, -3: self.target},
            walkable={(x, y, 0) for x in range(-2, 8) for y in range(2)},
            edges=None,
            allocate_effect_uid=lambda: 1,
            rii_states_lesson_contract={"owner": 7, "target": -3, "hits": 0},
            native_active_spell_id=7967,
            apply_effect_damage=Mock(),
        )

    def test_owned_contract_four_actions_and_wrong_damage_are_isolated(self):
        packets = []
        with patch.object(lesson, "_marker_los", return_value=True), patch(
            "wakfu_server.rii_lesson_grants.install", return_value=[101]
        ) as grant, patch(
            "wakfu_server.achievements.rii_lesson_state.install", return_value=102
        ):
            self.assertTrue(lesson.initialize(self.fight, packets, action_id=3))
        grant.assert_called_once()
        contract = self.fight.rii_states_lesson_contract
        self.assertEqual(contract["visible_state"], 8015)
        self.assertEqual(contract["hits"], 0)
        self.assertFalse(lesson.turn_end(self.fight, 8))
        self.owner.position = tuple(contract["green"])
        self.fight.native_active_spell_id = 7968
        self.assertEqual(
            lesson.hit(
                self.fight,
                source_id=7,
                target_id=-3,
                effect_reference=lesson.SPELL_EFFECT,
                damage=1,
            ),
            0,
        )
        self.assertEqual(contract["hits"], 0)
        self.fight.native_active_spell_id = 7967
        self.assertEqual(
            lesson.hit(
                self.fight,
                source_id=8,
                target_id=-3,
                effect_reference=lesson.SPELL_EFFECT,
                damage=1,
            ),
            0,
        )
        self.assertEqual(
            lesson.hit(
                self.fight,
                source_id=7,
                target_id=-3,
                effect_reference=lesson.SPELL_EFFECT,
                damage=1,
            ),
            25,
        )
        self.owner.position = tuple(contract["red"])
        self.assertEqual(
            lesson.hit(
                self.fight,
                source_id=7,
                target_id=-3,
                effect_reference=lesson.SPELL_EFFECT,
                damage=1,
            ),
            25,
        )
        self.owner.position = (1, 0, 0)
        self.assertTrue(lesson.turn_end(self.fight, 7))
        self.owner.position = (6, 0, 0)
        self.assertTrue(lesson.turn_end(self.fight, 7))
        self.assertEqual(self.fight.apply_effect_damage.call_count, 2)
        self.assertEqual(contract["hits"], 4)
        self.assertIsNone(
            lesson.hit(
                self.fight,
                source_id=7,
                target_id=-4,
                effect_reference=lesson.SPELL_EFFECT,
                damage=1,
            )
        )

    def test_invalid_or_missing_geometry_never_grants_spells(self):
        self.fight.walkable = {(0, 0, 0), (1, 0, 0)}
        with patch("wakfu_server.rii_lesson_grants.install") as grant:
            with self.assertRaises(ValueError):
                lesson.initialize(self.fight, [], action_id=3)
        grant.assert_not_called()

    def test_markers_require_walkable_route_and_native_line_of_sight(self):
        self.fight.walkable = {cell for cell in self.fight.walkable if cell[0] >= 0}
        with patch.object(
            lesson,
            "_marker_los",
            side_effect=lambda _fight, _owner, _target, cell: cell != (0, 1, 0),
        ):
            with self.assertRaises(ValueError):
                lesson.choose_markers(self.fight, self.target, owner_id=7)
        with patch.object(lesson, "_marker_los", return_value=True):
            self.assertEqual(
                lesson.choose_markers(self.fight, self.target, owner_id=7),
                ((0, 1, 0), (1, 0, 0)),
            )
            self.fight.walkable.remove((1, 1, 0))
            with self.assertRaises(ValueError):
                lesson.choose_markers(self.fight, self.target, owner_id=7)

    def test_marker_los_moves_a_clone_and_uses_native_ray(self):
        with patch(
            "wakfu_server.combat_qi_fight.move_registered_actor",
            side_effect=lambda _fight, actor, cell: setattr(actor, "position", cell),
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ) as ray:
            self.assertTrue(lesson._marker_los(self.fight, 7, -3, (2, 0, 0)))
        preview, authority, owner_id, cell, target = ray.call_args.args
        self.assertEqual(preview.actors[7].position, (2, 0, 0))
        self.assertEqual(self.owner.position, (6, 0, 0))
        self.assertEqual((owner_id, cell, target.id), (7, (0, 0, 0), -3))
        self.assertEqual(authority(preview, target).native_instance_id, 1388)

    def test_visible_native_state_is_replaced_and_not_duplicated(self):
        contract = self.fight.rii_states_lesson_contract
        contract.update(initialized=True, green=[2, 0, 0], red=[3, 0, 0])
        packets = []
        with patch(
            "wakfu_server.achievements.rii_lesson_state.install", side_effect=[101, 102]
        ) as install, patch(
            "wakfu_server.achievements.rii_lesson_state.remove"
        ) as remove:
            lesson.announce(self.fight, packets, action_id=1)
            lesson.announce(self.fight, packets, action_id=2)
            self.assertEqual(install.call_count, 1)
            contract["hits"] = 1
            lesson.announce(self.fight, packets, action_id=3)
        self.assertEqual(contract["visible_state"], 8016)
        self.assertEqual(contract["state_uid"], 102)
        remove.assert_called_once_with(
            self.fight, target_id=-3, uid=101, action_id=3, packets=packets
        )
        self.assertEqual(
            [call.kwargs["reference"] for call in install.call_args_list], [8015, 8016]
        )

    def test_real_fight_turn_boundary_damages_only_for_owner_position(self):
        from wakfu_server.combat_state import Actor, Fight

        owner = Actor(7, 0, (6, 0, 0), 100, 6, 3, 100, 1, 2, True)
        sack = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 10, 1)
        fight = Fight(
            11,
            [owner, sack],
            {(x, 0, 0) for x in range(8)},
            {0: {owner.position}, 1: {sack.position}},
        )
        fight.ready(2)
        fight.rii_states_lesson_contract = {
            "owner": 7,
            "target": -3,
            "hits": 3,
            "green": [2, 0, 0],
            "red": [3, 0, 0],
            "initialized": True,
        }
        fight.end_turn(2, 7, owner.turn_count)
        self.assertEqual(sack.hp, 75)
        self.assertEqual(fight.rii_states_lesson_contract["hits"], 4)
        self.assertTrue(
            any(
                event["kind"] == "damage"
                and event["target_id"] == -3
                and event["amount"] == 25
                for event in fight.events
            )
        )

    def test_runtime_turn_publishes_target_health_after_state_reaction(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        owner = Actor(7, 0, (6, 0, 0), 100, 6, 3, 100, 1, 2, True)
        sack = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 10, 1)
        fight = Fight(
            11,
            [owner, sack],
            {(x, 0, 0) for x in range(8)},
            {0: {owner.position}, 1: {sack.position}},
        )
        fight.ready(2)
        fight.rii_states_lesson_contract = {
            "owner": 7,
            "target": -3,
            "hits": 3,
            "green": [2, 0, 0],
            "red": [3, 0, 0],
            "initialized": True,
        }
        runtime = RuntimeMessages(
            fight, stats_serializer=lambda actor: bytes([actor.hp])
        )
        with patch.object(runtime, "_end_owned", return_value=[]), patch.object(
            runtime, "_flush", return_value=(13510, b"")
        ), patch.object(runtime, "turn_started", return_value=[]):
            packets = runtime.end_turn(2, 7, current_wire_turn(fight))
        self.assertEqual(sack.hp, 75)
        self.assertIn(12873, [opcode for opcode, _ in packets])


if __name__ == "__main__":
    unittest.main()
