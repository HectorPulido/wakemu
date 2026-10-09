"""Offline safety and tactical selection checks for the dungeon TLS driver."""
import unittest
import struct
from unittest.mock import patch

from tools.dungeon_combat_harness import (
    current_actor,
    checkpoint_turn_ready,
    acknowledged_turn_for_boundary,
    ordinary_action_checkpoint_ready,
    legal_melee_plan,
    living_enemies,
    placement_event,
    _peer_map,
    decode_turn_boundary,
    validate_post_ack_transitions,
)


class DungeonCombatHarnessSelectionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "order": [101, -7, 202],
            "turn_index": 0,
            "actors": {
                "101": {
                    "team": 0,
                    "hp": 100,
                    "ap": 6,
                    "mp": 2,
                    "position": [0, 0, 0],
                    "controlled": True,
                },
                "202": {
                    "team": 0,
                    "hp": 100,
                    "ap": 6,
                    "mp": 2,
                    "position": [0, 2, 0],
                    "controlled": True,
                },
                "-7": {"team": 1, "hp": 40, "position": [3, 0, 0]},
                "-8": {"team": 1, "hp": 0, "position": [0, 3, 0]},
            },
        }
        self.graph = {
            (0, 0, 0): ((1, 0, 0), (0, 1, 0)),
            (1, 0, 0): ((0, 0, 0), (2, 0, 0)),
            (2, 0, 0): ((1, 0, 0), (3, 0, 0)),
            (3, 0, 0): ((2, 0, 0),),
            (0, 1, 0): ((0, 0, 0), (0, 2, 0), (1, 1, 0)),
            (1, 1, 0): ((0, 1, 0), (2, 1, 0)),
            (2, 1, 0): ((1, 1, 0), (2, 0, 0)),
            (0, 2, 0): ((0, 1, 0), (0, 3, 0)),
            (0, 3, 0): ((0, 2, 0),),
        }

    def test_reads_current_actor_from_native_order_and_index(self):
        self.assertEqual(current_actor(self.snapshot), 101)
        self.snapshot["turn_index"] = 2
        self.assertEqual(current_actor(self.snapshot), 202)
        self.snapshot["turn_index"] = 3
        with self.assertRaisesRegex(AssertionError, "current turn"):
            current_actor(self.snapshot)

    def test_actual_checkpoint_shape_waits_for_shared_ack_release(self):
        # Sanitized actor/order/runtime fields from the failed candidate fight.
        active = {
            "phase": "active",
            "order": [-1001, 501, -1002, 502],
            "turn_index": 1,
            "runtime": {"awaiting_ack": 1, "action_id": 10},
        }
        self.assertFalse(checkpoint_turn_ready(active, 501))
        active["runtime"]["awaiting_ack"] = None
        self.assertTrue(checkpoint_turn_ready(active, 501))
        self.assertFalse(checkpoint_turn_ready(active, -1001))
        active["turn_index"] = 4
        self.assertFalse(checkpoint_turn_ready(active, 501))

    def test_action_checkpoint_tracks_logical_commit_without_requiring_turn_change(
        self,
    ):
        before = {
            "phase": "active",
            "turn_id": 106,
            "order": [85, 86],
            "turn_index": 1,
            "runtime": {"action_id": 606, "awaiting_ack": None},
        }
        self.assertFalse(ordinary_action_checkpoint_ready(before, 606))
        committed = {
            **before,
            "runtime": {"action_id": 607, "awaiting_ack": None},
        }
        self.assertTrue(ordinary_action_checkpoint_ready(committed, 606))
        self.assertTrue(ordinary_action_checkpoint_ready({"phase": "finished"}, 606))

    def test_only_living_opposing_team_members_are_targets(self):
        self.assertEqual(
            [identity for identity, _ in living_enemies(self.snapshot, 101)], [-7]
        )
        self.snapshot["actors"]["202"]["team"] = 1
        self.assertEqual(
            [identity for identity, _ in living_enemies(self.snapshot, 101)], [-7, 202]
        )

    def test_chooses_reachable_target_and_never_routes_through_occupied_cell(self):
        self.snapshot["actors"]["-7"]["position"] = [2, 0, 0]
        self.snapshot["actors"]["202"]["position"] = [1, 0, 0]
        with patch("tools.dungeon_combat_harness.static_visible", return_value=True):
            plan = legal_melee_plan(self.snapshot, 101, 999, graph=self.graph)
        self.assertEqual(plan["target_id"], -7)
        self.assertEqual(plan["route"], [(0, 1, 0), (1, 1, 0)])
        self.assertFalse(plan["adjacent"])

    def test_adjacent_attack_requires_visible_native_cell(self):
        self.snapshot["actors"]["-7"]["position"] = [1, 0, 0]
        with patch("tools.dungeon_combat_harness.static_visible", return_value=True):
            visible = legal_melee_plan(self.snapshot, 101, 999, graph=self.graph)
        self.assertEqual(visible["route"], [])
        self.assertTrue(visible["adjacent"])
        with patch("tools.dungeon_combat_harness.static_visible", return_value=False):
            blocked = legal_melee_plan(self.snapshot, 101, 999, graph=self.graph)
        self.assertFalse(blocked["adjacent"])

    def test_mp_bounds_movement_and_no_enemy_yields_no_plan(self):
        self.snapshot["actors"]["101"]["mp"] = 1
        self.snapshot["actors"]["-7"]["position"] = [3, 0, 0]
        with patch("tools.dungeon_combat_harness.static_visible", return_value=True):
            plan = legal_melee_plan(self.snapshot, 101, 999, graph=self.graph)
        self.assertLessEqual(len(plan["route"]), 1)
        self.snapshot["actors"]["-7"]["hp"] = 0
        self.assertIsNone(legal_melee_plan(self.snapshot, 101, 999, graph=self.graph))

    def test_post_ack_turns_must_match_but_private_reports_may_differ(self):
        turn = b"same native turn"
        self.assertEqual(
            validate_post_ack_transitions([(13482, turn), (13482, turn)]), 13482
        )
        self.assertEqual(
            validate_post_ack_transitions([(12755, b"owner-a"), (12755, b"owner-b")]),
            12755,
        )
        with self.assertRaisesRegex(AssertionError, "turn packets"):
            validate_post_ack_transitions([(13482, b"a"), (13482, b"b")])
        with self.assertRaisesRegex(AssertionError, "different post-ACK"):
            validate_post_ack_transitions([(13482, turn), (12755, b"owner-b")])

    def test_decodes_native_boundary_identity_for_stale_event_diagnostics(self):
        body = struct.pack(">iii", 44, 9, -1) + struct.pack(">qii", -7001, -1, 0)
        self.assertEqual(
            decode_turn_boundary(body, 44),
            {"fight_id": 44, "action_id": 9, "actor_id": -7001},
        )
        with self.assertRaisesRegex(AssertionError, "wrong fight"):
            decode_turn_boundary(body, 45)
        malformed = body[:-1] + b"\x01"
        with self.assertRaisesRegex(AssertionError, "invalid native fields"):
            decode_turn_boundary(malformed, 44)

    def test_resolves_ack_from_exact_pre_ai_turn_checkpoint(self):
        # AI-owned turn end is broadcast before a socket checkpoint persists
        # the transition. The boundary actor and next native action prove the
        # checkpoint is immediately before that transition.
        snapshot = {
            "phase": "active",
            "turn_id": 3,
            "order": [-801, 501, -802, 502, -803],
            "turn_index": 2,
            "runtime": {"awaiting_ack": None, "native_action_id": 90},
        }
        boundary = {"action_id": 91, "actor_id": -802}
        self.assertEqual(acknowledged_turn_for_boundary(snapshot, boundary), 3)

    def test_resolves_persisted_ack_and_rejects_stale_boundary(self):
        snapshot = {
            "phase": "active",
            "turn_id": 4,
            "order": [-801, 501, -802, 502, -803],
            "turn_index": 3,
            "runtime": {"awaiting_ack": 3, "native_action_id": 91},
        }
        self.assertEqual(
            acknowledged_turn_for_boundary(
                snapshot, {"action_id": 91, "actor_id": -802}
            ),
            3,
        )
        with self.assertRaisesRegex(AssertionError, "stale relative"):
            acknowledged_turn_for_boundary(
                {
                    "phase": "active",
                    "turn_id": 4,
                    "order": [-801, 501, -802, 502, -803],
                    "turn_index": 2,
                    "runtime": {"awaiting_ack": None, "native_action_id": 91},
                },
                {"action_id": 91, "actor_id": -802},
            )
        with self.assertRaisesRegex(AssertionError, "current actor"):
            acknowledged_turn_for_boundary(
                {
                    "phase": "active",
                    "turn_id": 3,
                    "order": [-801, 501, -802, 502, -803],
                    "turn_index": 1,
                    "runtime": {"awaiting_ack": None, "native_action_id": 90},
                },
                {"action_id": 91, "actor_id": -802},
            )

    def test_peer_sequences_are_bound_by_supplied_character_ids(self):
        peers = [object(), object()]
        self.assertEqual(_peer_map(peers, [501, 502]), {501: peers[0], 502: peers[1]})
        with self.assertRaisesRegex(ValueError, "match"):
            _peer_map(peers[:1], [501, 502])

    def test_native_group_attack_rejection_is_reported_without_placement_timeout(self):
        self.assertEqual(placement_event((13652, b"placement")), b"placement")
        reason = "You cannot start this fight"
        name = b"Server"
        body = bytes([len(name)]) + name + b"\x00" * 11
        body += struct.pack(">H", len(reason)) + reason.encode()
        with self.assertRaisesRegex(AssertionError, reason):
            placement_event((674, body))


if __name__ == "__main__":
    unittest.main()
