"""Private commit reuse preserves rollback, native death order and ACK allocation."""
from contextlib import nullcontext
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from test_combat_native_action_ids import NativeActionIdTests
from test_combat_pre_end_death import PreEndDeathTests
from wakfu_server import combat_native_action_ids as delivery
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_native_death_status import initialize_fresh_bje_death_status
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle


def oracle_for(runtime):
    return NativeOracle(
        runtime,
        characters={100: {"id": 100}},
        monsters={-200: {"id": -200}},
        decks={100: frozenset()},
        excluded_decks={100: frozenset()},
        viewer_id=100,
        flags={},
    )


def state(runtime):
    return (
        source_snapshot(runtime.fight),
        runtime.action_id,
        runtime.native_action_id,
        runtime.awaiting_ack,
        tuple(runtime.pending),
        tuple(runtime.last_native_delivery),
        getattr(runtime, "_reported_deaths", set()),
    )


class NativeDeliveryCloneCoalescingTests(unittest.TestCase):
    @patch("wakfu_server.combat_runtime_messages.wall_time", new=lambda _: 1700000000.0)
    def test_native_commit_and_owned_delivery_preserve_packets_deaths_ack_and_rollback(
        self,
    ):
        original_copy = RuntimeMessages.__deepcopy__
        rows = []
        for enabled in (False, True):
            runtime = NativeActionIdTests().runtime()
            oracle = oracle_for(runtime)
            copies = []

            def clone(value, memo):
                copies.append(True)
                return original_copy(value, memo)

            scope = (
                nullcontext()
                if enabled
                else patch.object(
                    delivery, "owned_native_delivery", new=lambda *_: nullcontext()
                )
            )
            with scope, patch.object(RuntimeMessages, "__deepcopy__", new=clone):
                packets = oracle.commit(
                    {"type": "end_turn"}, stats_serializer=lambda *_: ()
                )
            self.assertEqual(runtime.awaiting_ack, 1)
            before_ack = state(runtime)
            with self.assertRaises(ValueError):
                runtime.acknowledge_turn(struct.pack(">i", 99))
            self.assertEqual(state(runtime), before_ack)
            ack = runtime.acknowledge_turn(struct.pack(">i", 1))
            rows.append(
                (
                    tuple(packets),
                    before_ack[-2],
                    tuple(ack),
                    ack.native_actions,
                    state(runtime),
                    len(copies),
                )
            )
            self.assertNotIn("_native_delivery_depth", vars(runtime))
            self.assertNotIn("_area_atomic_depth", vars(runtime))
        self.assertEqual(rows[0][:-1], rows[1][:-1])
        self.assertEqual(rows[0][-1], rows[1][-1] + 1)

        # A custom service callback revokes the native ownership shortcut.
        runtime = NativeActionIdTests().runtime()
        runtime.clock = lambda: 0.0
        copies = []
        with patch.object(RuntimeMessages, "__deepcopy__", new=clone):
            oracle_for(runtime).commit(
                {"type": "end_turn"}, stats_serializer=lambda *_: ()
            )
        self.assertEqual(len(copies), rows[0][-1])

        # Native allocation failure must discard the outer commit's private
        # runtime even though delivery itself no longer creates another copy.
        runtime = NativeActionIdTests().runtime()
        runtime.native_action_id = delivery.MAX_NATIVE_ACTION_ID
        before = state(runtime)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            oracle_for(runtime).commit(
                {"type": "end_turn"}, stats_serializer=lambda *_: ()
            )
        self.assertEqual(state(runtime), before)
        self.assertIsNone(delivery._OWNED_DELIVERY.get())

        # Exercise the same owned-delivery mechanism with real reaction death
        # production. The caller owns/discards this preview, like _commit.
        death_rows = []
        for enabled in (False, True):
            fight = PreEndDeathTests().fixture(controlled=False)
            fight.actors[-200].native_world_properties = frozenset()
            initialize_fresh_bje_death_status(fight.actors[-200])

            def poison(candidate, *, actor_id, action_id):
                candidate = deepcopy(candidate)
                candidate.apply_effect_damage(101, -200, candidate.actors[-200].hp)
                return candidate, []

            runtime = RuntimeMessages(fight, turn_end_provider=poison)
            original = state(runtime)
            private = deepcopy(runtime)
            scope = (
                delivery.owned_native_delivery(private, RuntimeMessages.end_server_turn)
                if enabled
                else nullcontext()
            )
            with scope:
                packets = private.end_server_turn(100, fight.turn_id)
            self.assertEqual(state(runtime), original)
            deaths = [
                struct.unpack(">iiiqB", body)[3:] for op, body in packets if op == 12727
            ]
            self.assertEqual(deaths, [(-200, 0), (-200, 2)])
            close = next(i for i, (op, _) in enumerate(packets) if op == 12502)
            self.assertTrue(
                all(i < close for i, (op, _) in enumerate(packets) if op == 12727)
            )
            before_ack = state(private)
            ack = private.acknowledge_turn(struct.pack(">i", fight.turn_id))
            self.assertFalse(any(op == 12727 for op, _ in ack))
            death_rows.append(
                (
                    tuple(packets),
                    packets.native_actions,
                    before_ack,
                    tuple(ack),
                    ack.native_actions,
                    state(private),
                )
            )
        self.assertEqual(death_rows[0], death_rows[1])
        self.assertIsNone(delivery._OWNED_DELIVERY.get())
