"""The TLS QA runner drains automatic turn skips before issuing another action."""
from collections import deque
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import rift_tls_party_e2e as runner


def turn_event(actor_id):
    body = bytearray(20)
    struct.pack_into(">q", body, 12, actor_id)
    return bytes(body)


def movement_action(fight_id, actor_id):
    return struct.pack(">iiiqBB", fight_id, 0, 0, actor_id, 0, 0) + b"\x00" * 20


def movement_rejection(fight_id, actor_id, position=(0, 0, 0)):
    return struct.pack(">iqiih", fight_id, actor_id, *position)


def turn_marker(fight_id, action_id, actor_id):
    return struct.pack(">iiiqii", fight_id, action_id, -1, actor_id, -1, 0)


class FakePeer:
    def __init__(self):
        self.events = deque(
            [
                (12502, turn_marker(386, 101, 146), 110.0),
                (13482, turn_event(-1), 120.0),
                (12502, turn_marker(386, 102, -1), 130.0),
                (13482, turn_event(146), 140.0),
                (13624, movement_action(386, 146), 150.0),
                (12502, turn_marker(386, 104, 146), 155.0),
                (13482, turn_event(-2), 160.0),
            ]
        )
        self.pending = []
        self.sent = []
        self.seen = []
        self.wait_metrics = []
        self.waited = []
        self.last_received_at = 100.0
        self.clock = 100.0

    def send(self, opcode, body=b""):
        self.sent.append((opcode, body))
        self.clock += 1.0
        return self.clock

    def wait(self, opcodes, timeout=45, *, since=None, predicate=None):
        wanted = {opcodes} if isinstance(opcodes, int) else set(opcodes)
        self.waited.append((tuple(sorted(wanted)), since))
        while True:
            for index, (opcode, body, received_at) in enumerate(self.pending):
                if (
                    opcode in wanted
                    and (since is None or received_at >= since)
                    and (predicate is None or predicate(body))
                ):
                    del self.pending[index]
                    self.seen.append(opcode)
                    self.last_received_at = received_at
                    self.wait_metrics.append({"wait_ms": 0.0, "since_send_ms": 0.0})
                    return opcode, body
            if not self.events:
                raise TimeoutError(f"missing fake event {sorted(wanted)}")
            event = self.events.popleft()
            opcode, body, received_at = event
            if (
                opcode in wanted
                and (since is None or received_at >= since)
                and (predicate is None or predicate(body))
            ):
                self.seen.append(opcode)
                self.last_received_at = received_at
                self.wait_metrics.append({"wait_ms": 0.0, "since_send_ms": 0.0})
                return opcode, body
            self.pending.append(event)


class RiftTlsBattleTurnReactionTests(unittest.TestCase):
    def test_durable_marker_waits_through_stale_snapshot_then_accepts_matching_ack(
        self,
    ):
        marker = turn_marker(391, 2604, 164)
        previous = {
            "turn_id": 299,
            "current_actor_id": 164,
            "runtime": {"awaiting_ack": None},
        }
        stale = {
            "id": 391,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 13999,
                "awaiting_ack": None,
            },
        }
        durable = {
            "id": 391,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14000,
                "awaiting_ack": 299,
            },
        }
        args = type("Args", (), {"wave": 3, "action_timeout": 1})()
        with patch.object(
            runner, "observe", side_effect=[stale, durable]
        ) as observe, patch.object(runner.time, "sleep"):
            result = runner.durable_turn_boundary(
                args, 391, [(12502, marker)], previous=previous
            )
        self.assertIs(result, durable)
        self.assertEqual(observe.call_count, 2)

    def test_durable_marker_rejects_stale_counter_until_matching_barrier(self):
        marker = turn_marker(391, 2605, 164)
        previous = {
            "turn_id": 299,
            "current_actor_id": 164,
            "runtime": {"awaiting_ack": None},
        }
        stale_counter = {
            "id": 391,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14001,
                "awaiting_ack": 298,
            },
        }
        durable = {
            "id": 391,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14002,
                "awaiting_ack": 299,
            },
        }
        args = type("Args", (), {"wave": 3, "action_timeout": 1})()
        with patch.object(
            runner, "observe", side_effect=[stale_counter, durable]
        ) as observe, patch.object(runner.time, "sleep"):
            result = runner.durable_turn_boundary(
                args, 391, [(12502, marker)], previous=previous
            )
        self.assertIs(result, durable)
        self.assertEqual(observe.call_count, 2)

    def test_durable_marker_rejects_foreign_marker_and_mismatched_checkpoint(self):
        args = type("Args", (), {"wave": 3, "action_timeout": 1})()
        marker = turn_marker(392, 2604, 164)
        with patch.object(runner, "observe") as observe, self.assertRaisesRegex(
            ValueError, "Invalid native turn marker identity"
        ):
            runner.durable_turn_boundary(args, 391, [(12502, marker)])
        observe.assert_not_called()

        marker = turn_marker(391, 2604, 164)
        wrong_fight = {
            "id": 392,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14000,
                "awaiting_ack": 299,
            },
        }
        with patch.object(
            runner, "observe", return_value=wrong_fight
        ), self.assertRaisesRegex(ValueError, "fight identity mismatch"):
            runner.durable_turn_boundary(args, 391, [(12502, marker)])

        wrong_actor = {
            "id": 391,
            "phase": "active",
            "turn_id": 300,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14000,
                "awaiting_ack": 299,
            },
        }
        previous = {
            "turn_id": 299,
            "current_actor_id": 165,
            "runtime": {"awaiting_ack": None},
        }
        with patch.object(
            runner, "observe", return_value=wrong_actor
        ), self.assertRaisesRegex(
            TimeoutError, "no matching durable ACK barrier"
        ), patch.object(
            runner.time, "sleep"
        ), patch.object(
            runner.time, "monotonic", side_effect=[0.0, 2.0]
        ):
            runner.durable_turn_boundary(
                args, 391, [(12502, marker)], previous=previous
            )

    def test_durable_marker_accepts_finished_checkpoint_and_terminal_report(self):
        marker = turn_marker(397, 14000, 190)
        finished = {
            "id": 397,
            "phase": "finished",
            "turn_id": 362,
            "current_actor_id": 190,
            "runtime": {
                "action_id": 2920,
                "native_action_id": 14001,
                "awaiting_ack": 361,
            },
        }
        previous = {
            "id": 397,
            "phase": "active",
            "turn_id": 361,
            "current_actor_id": 190,
            "runtime": {
                "action_id": 2919,
                "native_action_id": 13999,
                "awaiting_ack": 360,
            },
        }
        args = type("Args", (), {"wave": 3, "action_timeout": 1})()
        peers = [FakePeer() for _ in range(6)]
        calls = []
        actions = {"acks_sent": 0}

        def wait(actual_peers, expected, *, timeout, since=None):
            self.assertEqual(actual_peers, peers)
            calls.append(set(expected))
            if len(calls) == 1:
                return [(12502, marker)] * 6
            self.assertEqual(set(expected), {12502, 12755})
            for peer in peers:
                self.assertEqual(peer.sent, [(13510, struct.pack(">i", 361))])
            return [(12755, b"terminal")] * 6

        with patch.object(runner, "observe", return_value=finished), patch.object(
            runner, "wait_all", side_effect=wait
        ):
            events = runner.drain_turn_boundaries(
                args,
                peers,
                397,
                actions=actions,
                previous=previous,
                after_counter=360,
            )
        self.assertEqual(events, [(12755, b"terminal")] * 6)
        self.assertEqual(calls, [{13482, 12502, 12755}, {12502, 12755}])
        self.assertEqual(actions["acks_sent"], 6)
        self.assertEqual(
            [peer.sent for peer in peers],
            [[(13510, struct.pack(">i", 361))] for _ in peers],
        )

    def test_finished_marker_without_durable_counter_is_rejected(self):
        peers = [FakePeer() for _ in range(6)]
        with self.assertRaisesRegex(ValueError, "durable ACK counter"):
            runner.acknowledge_native_boundary(
                peers, {"phase": "finished", "runtime": {"awaiting_ack": None}}
            )
        self.assertTrue(all(not peer.sent for peer in peers))

    def test_durable_marker_tracks_native_allocator_not_logical_action_id(self):
        marker = turn_marker(391, 14000, 164)
        previous = {
            "turn_id": 2599,
            "current_actor_id": 164,
            "runtime": {
                "action_id": 2600,
                "native_action_id": 13998,
                "awaiting_ack": None,
            },
        }
        stale = {
            "id": 391,
            "phase": "active",
            "turn_id": 2600,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 13999,
                "awaiting_ack": 2599,
            },
        }
        matching = {
            "id": 391,
            "phase": "active",
            "turn_id": 2600,
            "current_actor_id": None,
            "runtime": {
                "action_id": 2601,
                "native_action_id": 14000,
                "awaiting_ack": 2599,
            },
        }
        args = type("Args", (), {"wave": 3, "action_timeout": 1})()
        with patch.object(
            runner, "observe", side_effect=[stale, matching]
        ) as observe, patch.object(runner.time, "sleep"):
            result = runner.durable_turn_boundary(
                args, 391, [(12502, marker)], previous=previous
            )
        self.assertIs(result, matching)
        self.assertEqual(observe.call_count, 2)

    def test_movement_wait_ignores_flush_and_decodes_accept_or_native_rejection(self):
        class Peer:
            def __init__(self, events):
                self.events = deque(events)
                self.seen = []

            def wait(self, opcodes, timeout=45, *, since=None, predicate=None):
                wanted = set(opcodes)
                while self.events:
                    opcode, body, received_at = self.events.popleft()
                    if opcode not in wanted or (
                        since is not None and received_at < since
                    ):
                        self.seen.append(opcode)
                        continue
                    if predicate is None or predicate(body):
                        self.seen.append(opcode)
                        return opcode, body
                raise TimeoutError("missing native movement result")

        reject = movement_rejection(391, 164, (2, 3, 0))
        peer = Peer([(13420, b"flush", 1.0), (13887, reject, 2.0)])
        result = runner.wait_movement_action(peer, 391, 164, 1.5, timeout=3)
        self.assertEqual(
            result, {"accepted": False, "opcode": 13887, "position": [2, 3, 0]}
        )
        self.assertEqual(peer.seen, [13420, 13887])

        peer = Peer([(13624, movement_action(391, 164), 2.0)])
        result = runner.wait_movement_action(peer, 391, 164, 1.0, timeout=3)
        self.assertEqual(result, {"accepted": True, "opcode": 13624})

    def test_movement_wait_rejects_malformed_or_foreign_corrections(self):
        cases = [
            (13887, b"short", 391, 164),
            (13887, movement_rejection(392, 164), 391, 164),
            (13887, movement_rejection(391, 165), 391, 164),
            (13624, movement_action(392, 164), 391, 164),
            (13624, movement_action(391, 165), 391, 164),
        ]
        for opcode, body, fight_id, actor_id in cases:
            with self.subTest(opcode=opcode, body_length=len(body)):
                peer = FakePeer()
                peer.events.clear()
                peer.events.append((opcode, body, 2.0))
                with self.assertRaises(ValueError):
                    runner.wait_movement_action(peer, fight_id, actor_id, 1.0)

    def test_healing_movement_rejection_reobserves_durable_state(self):
        class Peer:
            def __init__(self):
                self.sent = []

            def send(self, opcode, body):
                self.sent.append((opcode, body))
                return 1.0

            def wait(self, opcodes, timeout=45, *, since=None, predicate=None):
                return 13887, movement_rejection(391, 164, (4, 5, 0))

        before = {"actors": {"164": {"id": 164, "hp": 20}}}
        after = {"actors": {"164": {"id": 164, "hp": 19}}}
        peer = Peer()
        with patch.object(
            runner, "healing_orb_route", return_value=[(1, 0, 0)]
        ), patch.object(runner, "observe", return_value=after) as observe:
            checkpoint, sent, movement = runner.seek_healing_orb(
                type("Args", (), {"wave": 3, "action_timeout": 3})(),
                peer,
                before,
                {},
                391,
                164,
            )
        self.assertIs(checkpoint, after)
        self.assertEqual(sent, 1.0)
        self.assertFalse(movement["accepted"])
        self.assertEqual(peer.sent[0][0], 12161)
        observe.assert_called_once_with(
            unittest.mock.ANY,
            {"operation": "combat", "wave": 3, "fight_id": 391},
        )

    def test_battle_rejection_ends_turn_and_acks_without_counting_movement(self):
        player = dict(
            id=164,
            team=1,
            controlled=True,
            owner_id=77,
            hp=100,
            ap=6,
            mp=3,
            position=[0, 0, 0],
            native_obstacle_id=-1,
        )
        target = dict(
            id=-3,
            team=0,
            controlled=False,
            owner_id=None,
            hp=100,
            ap=0,
            mp=0,
            position=[2, 0, 0],
            native_obstacle_id=-1,
        )

        def checkpoint(current, awaiting_ack, wave=1):
            ack = type(awaiting_ack) is int
            return dict(
                id=391,
                phase="active",
                current_actor_id=current,
                runtime={
                    "awaiting_ack": awaiting_ack,
                    "action_id": 2604 if ack else 0,
                    "native_action_id": 2604 if ack else 0,
                },
                turn_id=awaiting_ack + 1 if ack else 16,
                native_timeline_round=1,
                rift_wave_state={"wave": wave, "pending_wave": None},
                durable_rift={
                    "completed_waves": wave - 1,
                    "defeated_monsters": (wave - 1) * 6,
                },
                actors={"164": dict(player), "-3": dict(target)},
                native_qi_occupied_count=2,
                native_timeline_removed_count=0,
                native_visibility={"0,0,0": {"-3": False}},
                walkable=[[0, 0, 0], [1, 0, 0], [2, 0, 0]],
                edges=[
                    [[0, 0, 0], [1, 0, 0]],
                    [[1, 0, 0], [0, 0, 0]],
                    [[1, 0, 0], [2, 0, 0]],
                    [[2, 0, 0], [1, 0, 0]],
                ],
            )

        states = deque(
            [
                checkpoint(164, None),
                checkpoint(164, 17),
                checkpoint(-1, None, wave=2),
                checkpoint(-1, None, wave=2),
            ]
        )

        class Peer:
            def __init__(self):
                self.sent = []
                self.wait_metrics = []
                self.last_received_at = 0.0

            def send(self, opcode, body=b""):
                self.sent.append((opcode, body))
                return float(len(self.sent))

            def wait(self, opcodes, timeout=45, *, since=None, predicate=None):
                wanted = {opcodes} if isinstance(opcodes, int) else set(opcodes)
                if 13887 in wanted:
                    return 13887, movement_rejection(391, 164)
                raise TimeoutError(f"missing peer events for {sorted(wanted)}")

        peer = Peer()
        args = runner.argparse.Namespace(
            phase="battle",
            wave=3,
            target_wave=1000,
            stop_after_wave=None,
            stop_after_defeats=None,
            max_turns=2,
            max_battle_seconds=10,
            observer_metrics=[],
            action_timeout=2,
        )
        with patch.object(
            runner, "observe", side_effect=lambda *_: states.popleft()
        ), patch.object(
            runner, "combat_view", return_value=checkpoint(164, None)
        ), patch.object(
            runner, "combat_route", return_value=[(1, 0, 0)]
        ), patch.object(
            runner, "stop_at_durable_boundary", side_effect=[False, True]
        ), patch.object(
            runner,
            "wait_all",
            side_effect=[
                [(12502, turn_marker(391, 2604, 164))],
                [(13482, turn_event(-1))],
            ],
        ):
            result = {}
            runner.battle(
                args,
                [peer],
                [{"account_id": 77, "weapon_uid": None}],
                {"cells": [[0, 0, 0], [1, 0, 0], [2, 0, 0]], "edges": []},
                391,
                turn_event(164),
                result,
            )

        opcodes = [opcode for opcode, _ in peer.sent]
        self.assertEqual(result["movement_rejections"][0]["opcode"], 13887)
        self.assertEqual(result["battle_metrics"]["actions"]["movement"], 0)
        self.assertIn(12403, opcodes)
        self.assertIn((13510, struct.pack(">i", 17)), peer.sent)

    def test_successor_boundaries_ack_each_durable_counter_before_turn_event(self):
        class AckPeer:
            def __init__(self):
                self.sent = []

            def send(self, opcode, body):
                self.sent.append((opcode, body))
                return float(len(self.sent))

        peers = [AckPeer() for _ in range(4)]
        args = type("Args", (), {"wave": 3})()
        actions = {"acks_sent": 0}
        events = [
            [(12502, turn_marker(388, 3, -2))] * 4,
            [(12502, turn_marker(388, 4, -2))] * 4,
            [(13482, b"turn")] * 4,
        ]
        checkpoints = [
            {
                "id": 388,
                "phase": "active",
                "turn_id": 4,
                "current_actor_id": -2,
                "runtime": {"action_id": 3, "native_action_id": 3, "awaiting_ack": 3},
            },
            {
                "id": 388,
                "phase": "active",
                "turn_id": 5,
                "current_actor_id": -2,
                "runtime": {"action_id": 4, "native_action_id": 4, "awaiting_ack": 4},
            },
        ]
        with patch.object(
            runner, "wait_all", side_effect=events
        ) as wait_all, patch.object(runner, "observe", side_effect=checkpoints):
            result = runner.drain_turn_boundaries(
                args, peers, 388, since=[0.0] * 4, actions=actions
            )
        self.assertEqual([opcode for opcode, _ in result], [13482] * 4)
        self.assertEqual(
            [
                [struct.unpack(">i", body)[0] for opcode, body in peer.sent]
                for peer in peers
            ],
            [[3, 4]] * 4,
        )
        self.assertEqual(actions["acks_sent"], 8)
        self.assertEqual(wait_all.call_count, 3)

    def test_successor_boundary_without_durable_counter_sends_no_ack(self):
        class AckPeer:
            def __init__(self):
                self.sent = []

            def send(self, opcode, body):
                self.sent.append((opcode, body))
                return 1.0

        peers = [AckPeer() for _ in range(4)]
        checkpoint = {
            "id": 388,
            "phase": "active",
            "turn_id": 4,
            "current_actor_id": -2,
            "runtime": {"action_id": 3, "native_action_id": 3, "awaiting_ack": None},
        }
        with patch.object(
            runner, "wait_all", return_value=[(12502, turn_marker(388, 3, -2))] * 4
        ), patch.object(
            runner, "observe", return_value=checkpoint
        ), self.assertRaisesRegex(
            TimeoutError, "no matching durable ACK barrier"
        ), patch.object(
            runner.time, "sleep"
        ), patch.object(
            runner.time, "monotonic", side_effect=[0.0, 2.0]
        ):
            runner.drain_turn_boundaries(
                type("Args", (), {"wave": 3, "action_timeout": 1})(), peers, 388
            )
        self.assertEqual([peer.sent for peer in peers], [[], [], [], []])

    def test_weapon_route_stops_at_visible_native_range_and_respects_mp(self):
        geometry = {
            "edges": [
                [[0, 0, 0], [1, 0, 0]],
                [[1, 0, 0], [0, 0, 0]],
                [[1, 0, 0], [2, 0, 0]],
                [[2, 0, 0], [1, 0, 0]],
                [[2, 0, 0], [3, 0, 0]],
                [[3, 0, 0], [2, 0, 0]],
                [[3, 0, 0], [4, 0, 0]],
                [[4, 0, 0], [3, 0, 0]],
                [[4, 0, 0], [5, 0, 0]],
                [[5, 0, 0], [4, 0, 0]],
            ]
        }
        visible = runner.visibility_for_target(
            {"native_visibility": {"2,0,0": {"9": True}}}, 9
        )
        self.assertTrue(visible((2, 0, 0)))
        self.assertTrue(visible((2, 0, 0), (5, 0, 0)))
        route = runner.combat_route(
            geometry,
            (0, 0, 0),
            (5, 0, 0),
            set(),
            2,
            minimum_range=3,
            maximum_range=5,
            visible=visible,
        )
        self.assertEqual(route, [(1, 0, 0), (2, 0, 0)])

    def test_target_choice_prefers_adjacent_current_wave_enemy_over_farther_one(self):
        farther_earlier = ((0, 0), [(1, 0, 0), (2, 0, 0), (3, 0, 0)], {"id": -20})
        adjacent_later = ((0, 1), [(1, 0, 0)], {"id": -21})

        selected = runner.choose_combat_target([farther_earlier, adjacent_later])

        self.assertEqual(selected, adjacent_later)

    def test_target_choice_keeps_current_wave_enemy_ahead_of_older_summon(self):
        older_summon = ((1, 0), [(1, 0, 0)], {"id": -30})
        current_wave_enemy = ((0, 1), [(1, 0, 0), (2, 0, 0), (3, 0, 0)], {"id": -31})

        selected = runner.choose_combat_target([older_summon, current_wave_enemy])

        self.assertEqual(selected, current_wave_enemy)

    def test_target_choice_uses_native_insertion_then_actor_id_for_ties(self):
        later_insertion_lower_id = ((0, 1), [(1, 0, 0)], {"id": -40})
        earlier_insertion_higher_id = ((0, 0), [(1, 0, 0)], {"id": -41})
        self.assertEqual(
            runner.choose_combat_target(
                [later_insertion_lower_id, earlier_insertion_higher_id]
            ),
            earlier_insertion_higher_id,
        )

        higher_id = ((0, 0), [(1, 0, 0)], {"id": -40})
        lower_id = ((0, 0), [(1, 0, 0)], {"id": -41})
        self.assertEqual(
            runner.choose_combat_target([higher_id, lower_id]),
            lower_id,
        )

    def test_route_eligibility_keeps_block_los_and_mp_checks_outside_target_order(self):
        geometry = {
            "edges": [
                [[0, 0, 0], [1, 0, 0]],
                [[1, 0, 0], [0, 0, 0]],
                [[1, 0, 0], [2, 0, 0]],
                [[2, 0, 0], [1, 0, 0]],
                [[2, 0, 0], [3, 0, 0]],
                [[3, 0, 0], [2, 0, 0]],
            ]
        }
        no_visibility = lambda *_: False

        self.assertEqual(
            runner.combat_route(
                geometry,
                (0, 0, 0),
                (3, 0, 0),
                {(1, 0, 0)},
                3,
                minimum_range=1,
                maximum_range=1,
            ),
            [],
        )
        self.assertEqual(
            runner.combat_route(
                geometry,
                (0, 0, 0),
                (3, 0, 0),
                set(),
                1,
                minimum_range=1,
                maximum_range=1,
            ),
            [(1, 0, 0)],
        )
        self.assertEqual(
            runner.combat_route(
                geometry,
                (0, 0, 0),
                (3, 0, 0),
                set(),
                3,
                minimum_range=1,
                maximum_range=1,
                visible=no_visibility,
            ),
            [],
        )

    def test_skipped_start_and_movement_reaction_drain_ack_before_player_action(self):
        player = dict(
            id=146,
            team=1,
            controlled=True,
            owner_id=77,
            hp=100,
            ap=6,
            mp=1,
            position=[0, 0, 0],
            native_obstacle_id=-1,
        )
        npc = dict(
            id=-1,
            team=0,
            controlled=False,
            owner_id=None,
            hp=100,
            ap=0,
            mp=0,
            position=[3, 0, 0],
            native_obstacle_id=-1,
        )
        skipped_npc = dict(npc, id=-2, position=[3, 1, 0])
        target = dict(npc, id=-3, position=[2, 0, 0])

        def checkpoint(current, awaiting_ack, wave=1):
            ack = type(awaiting_ack) is int
            return dict(
                id=386,
                phase="active",
                current_actor_id=current,
                runtime={
                    "awaiting_ack": awaiting_ack,
                    "action_id": awaiting_ack if ack else 0,
                    "native_action_id": 14100 if ack else 0,
                },
                turn_id=awaiting_ack + 1 if ack else 40,
                native_timeline_round=1,
                rift_wave_state={"wave": wave, "pending_wave": None},
                durable_rift={
                    "completed_waves": wave - 1,
                    "defeated_monsters": (wave - 1) * 6,
                },
                actors={
                    "146": dict(player),
                    "-1": dict(npc),
                    "-2": dict(skipped_npc),
                    "-3": dict(target),
                },
                native_qi_occupied_count=4,
                native_timeline_removed_count=0,
                order=[current],
                turn_index=0,
            )

        states = deque(
            [
                checkpoint(-1, 102),  # 13482 said 146; source already skipped to NPC.
                checkpoint(-1, 102),
                checkpoint(-1, None),
                checkpoint(-1, 103),
                checkpoint(146, None),
                checkpoint(146, None),
                checkpoint(-2, 104),  # Movement's native reaction skipped player 146.
                checkpoint(-2, 104),
                checkpoint(-2, 104),
                checkpoint(-2, None, wave=2),
                checkpoint(-2, None, wave=2),
            ]
        )

        peer = FakePeer()
        original_observe = runner.observe

        def fake_observe(_args, request):
            state = states.popleft()
            if request.get("visibility_actor_id") is not None:
                state["native_visibility"] = {
                    "0,0,0": {"-3": False},
                    "1,0,0": {"-3": True},
                    "2,0,0": {"-3": True},
                }
            return state

        runner.observe = fake_observe
        try:
            result = {}
            geometry = {
                "cells": [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
                "edges": [
                    [[0, 0, 0], [1, 0, 0]],
                    [[1, 0, 0], [0, 0, 0]],
                    [[1, 0, 0], [2, 0, 0]],
                    [[2, 0, 0], [1, 0, 0]],
                ],
            }
            with tempfile.TemporaryDirectory() as output_dir:
                args = runner.argparse.Namespace(
                    phase="battle",
                    wave=3,
                    target_wave=2,
                    stop_after_wave=2,
                    stop_after_defeats=None,
                    max_turns=10,
                    max_battle_seconds=30,
                    weapon_reference=27686,
                    observer_metrics=[],
                    output=Path(output_dir) / "progress.json",
                )
                runner.battle(
                    args,
                    [peer],
                    [{"account_id": 77, "weapon_uid": 555, "weapon_ap_cost": 6}],
                    geometry,
                    386,
                    turn_event(146),
                    result,
                )
        finally:
            runner.observe = original_observe

        sent_opcodes = [opcode for opcode, _ in peer.sent]
        ack_counters = [
            struct.unpack(">i", body)[0]
            for opcode, body in peer.sent
            if opcode == 13510
        ]
        self.assertEqual(ack_counters, [102, 103, 104])
        self.assertEqual(sent_opcodes.count(12161), 1)
        self.assertNotIn(12889, sent_opcodes)
        self.assertNotIn(12403, sent_opcodes)
        self.assertEqual(result["stop_receipt"]["wave"], 2)
        self.assertEqual(result["real_turn_boundaries"], 3)


if __name__ == "__main__":
    unittest.main()
