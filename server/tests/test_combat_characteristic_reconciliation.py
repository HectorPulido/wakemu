"""Changed lock/dodge and raw bounds reconcile after callback/retirement FIFO."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from test_combat_movement_runtime import MovementRuntimeTests
from wakfu_server.combat_characteristic_reconciliation import (
    characteristic_signatures,
    changed_characteristic_packets,
)
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_wire import decode_actor_state


class CharacteristicReconciliationTests(unittest.TestCase):
    def test_turn_start_reconciles_other_actor_after_callback_once(self):
        runtime, _, enemy = self.fixture()
        runtime.runtime_stats_serializer = lambda actor, state: struct.pack(
            ">ii", *((actor.effect_stats or {}).get(k, 0) for k in (7, 8))
        )

        def start(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[enemy.id].effect_stats.update({7: -88, 8: -94})
            packet = (
                struct.pack(">iii", preview.id, boundary["action_id"], -1)
                + b"native-delta"
            )
            return preview, [(12613, packet)]

        runtime.turn_start_provider = start
        packets = runtime.turn_started()
        callback_index = next(
            i for i, packet in enumerate(packets) if packet[0] == 12613
        )
        final_index, final = next(
            (i, decode_actor_state(op, body))
            for i, (op, body) in enumerate(packets)
            if op == 12873 and decode_actor_state(op, body)["actor_id"] == enemy.id
        )
        self.assertGreater(final_index, callback_index)
        self.assertEqual(struct.unpack(">ii", final["state"]), (-88, -94))
        self.assertEqual(runtime.turn_started(), [])

    def test_turn_end_reconciles_other_actor_after_callback(self):
        runtime, player, enemy = self.fixture()
        runtime.runtime_stats_serializer = self.serialize

        def end(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[enemy.id].effect_stats.update({7: -88, 8: -94})
            packet = (
                struct.pack(">iii", preview.id, boundary["action_id"], -1)
                + b"native-delta"
            )
            return preview, [(12613, packet)]

        runtime.turn_end_provider = end
        packets = runtime._end_owned(player)
        self.assertEqual([opcode for opcode, _ in packets], [12613, 12873, 13420])
        final = decode_actor_state(12873, packets[1][1])
        self.assertEqual(final["actor_id"], enemy.id)
        self.assertEqual(struct.unpack(">ii", final["state"]), (-88, -94))

    def test_signed_lock_dodge_round_trip_through_native_characteristics(self):
        from types import SimpleNamespace
        from test_combat_snapshot_wire import SnapshotWireTests
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics

        actor = SnapshotWireTests().actor(controlled=False)
        actor.effect_base_maxima[1] = 100
        definitions = native_actor_catalog()["characteristics"]
        for identity, current in ((7, 12), (8, 6)):
            row = definitions[str(identity)]
            actor.effect_stats[identity] = current
            actor.effect_minima[identity] = actor.effect_base_minima[identity] = row[
                "hard_minimum"
            ]
            actor.effect_maxima[identity] = actor.effect_base_maxima[identity] = row[
                "hard_maximum"
            ]
            actor.effect_percentages[identity] = 0
        fight = SimpleNamespace(id=208, actors={actor.id: actor})
        before = characteristic_signatures(fight)
        actor.effect_stats.update({7: -188, 8: -194})
        packets = changed_characteristic_packets(
            fight, before, lambda actor, state: snapshot_characteristics(actor)
        )
        final = decode_actor_state(12873, packets[0][1])
        values = SnapshotWireTests().decode(final["state"])
        self.assertEqual((values[7][0], values[8][0]), (-188, -194))
        self.assertEqual(final["actor_id"], actor.id)

    def test_expiration_snapshot_only_still_reserves_action_boundary(self):
        runtime, _, enemy = self.fixture()
        runtime.runtime_stats_serializer = self.serialize
        runtime.fight.owned_stat_effects[100] = {"timer": {"remaining": 1}}

        def expire(fight, **kwargs):
            fight.actors[-2].effect_stats[7] = 11
            return []

        before_action = runtime.action_id
        with patch(
            "wakfu_server.combat_timed_expiration.expire_timed_effects",
            side_effect=expire,
        ):
            packets = runtime._expire_owned(actor_id=1, round_number=1, phase="end")
        self.assertEqual(runtime.action_id, before_action + 1)
        self.assertEqual([opcode for opcode, _ in packets], [12873, 13420])

    def fixture(self):
        runtime, player = MovementRuntimeTests().setup_fight()
        enemy = runtime.fight.actors[-2]
        enemy.effect_stats = {7: 12, 8: 6}
        runtime.stats_serializer = lambda actor: struct.pack(
            ">ii", *((actor.effect_stats or {}).get(k, 0) for k in (7, 8))
        )
        return runtime, player, enemy

    @staticmethod
    def serialize(actor, fight):
        return struct.pack(">ii", *(actor.effect_stats.get(k, 0) for k in (7, 8)))

    def test_signature_copies_lock_dodge_and_raw_bound_values(self):
        runtime, _, enemy = self.fixture()
        enemy.effect_resource_raw_currents = {2: 6, 3: 3}
        before = characteristic_signatures(runtime.fight)
        enemy.effect_resource_raw_currents[3] = 4
        packets = changed_characteristic_packets(runtime.fight, before, self.serialize)
        self.assertEqual(
            [decode_actor_state(op, body)["actor_id"] for op, body in packets], [-2]
        )
        self.assertEqual(before[-2][7][6][1], ((2, 6), (3, 3)))

    def test_movement_reconciles_other_actor_lock_and_dodge_after_effect(self):
        runtime, player, enemy = self.fixture()
        runtime.runtime_stats_serializer = self.serialize

        def debuff(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[-2].effect_stats.update({7: -88, 8: -94})
            return preview, [(12613, b"evaluated-lock-dodge")]

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", player.id, 1, 0, 0),
            lambda actor: b"mover",
            area_provider=debuff,
        )
        rows = [
            (index, decode_actor_state(op, body))
            for index, (op, body) in enumerate(packets)
            if op == 12873
        ]
        final_index, final = next(row for row in rows if row[1]["actor_id"] == enemy.id)
        callback_index = next(
            i for i, packet in enumerate(packets) if packet[0] == 12613
        )
        self.assertGreater(final_index, callback_index)
        self.assertEqual(struct.unpack(">ii", final["state"]), (-88, -94))
        self.assertEqual(enemy.effect_stats, {7: -88, 8: -94})

    def test_expiration_reconciles_restored_lock_dodge_after_removal(self):
        runtime, _, enemy = self.fixture()
        enemy.effect_stats.update({7: -88, 8: -94})
        runtime.runtime_stats_serializer = self.serialize
        runtime.fight.owned_stat_effects[100] = {"timer": {"remaining": 1}}

        def expire(fight, **kwargs):
            fight.actors[-2].effect_stats.update({7: 12, 8: 6})
            return [(13560, b"same-owned-effect-retirement")]

        with patch(
            "wakfu_server.combat_timed_expiration.expire_timed_effects",
            side_effect=expire,
        ):
            packets = runtime._expire_owned(actor_id=1, round_number=1, phase="end")
        self.assertEqual([opcode for opcode, _ in packets], [13560, 12873, 13420])
        final = decode_actor_state(12873, packets[1][1])
        self.assertEqual(final["actor_id"], enemy.id)
        self.assertEqual(struct.unpack(">ii", final["state"]), (12, 6))

    def test_unchanged_characteristics_do_not_add_snapshots(self):
        runtime, _, _ = self.fixture()
        before = characteristic_signatures(runtime.fight)
        self.assertEqual(
            changed_characteristic_packets(runtime.fight, before, self.serialize), []
        )

    def test_movement_reconciles_silent_other_actor_mutation(self):
        runtime, player, enemy = self.fixture()
        runtime.runtime_stats_serializer = self.serialize

        def silent(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[-2].effect_stats[8] -= 100
            return preview, []

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", player.id, 1, 0, 0),
            lambda actor: b"mover",
            area_provider=silent,
        )
        self.assertEqual([op for op, _ in packets], [13624, 13420, 12873, 12873, 13420])
        final = decode_actor_state(12873, packets[-2][1])
        self.assertEqual(final["actor_id"], enemy.id)
        self.assertEqual(struct.unpack(">ii", final["state"]), (12, -94))

    def test_failed_other_actor_snapshot_rolls_back_entire_movement(self):
        runtime, player, enemy = self.fixture()
        position, mp = player.position, player.mp

        def debuff(preview, **boundary):
            preview = deepcopy(preview)
            preview.actors[-2].effect_stats[7] -= 100
            return preview, [(12613, b"evaluated-lock")]

        def reject(actor, fight):
            raise ValueError("changed-actor serialization failed")

        runtime.runtime_stats_serializer = reject
        with self.assertRaisesRegex(ValueError, "changed-actor serialization failed"):
            apply_client(
                runtime,
                7,
                struct.pack(">qiih", player.id, 1, 0, 0),
                lambda actor: b"mover",
                area_provider=debuff,
            )
        self.assertEqual((player.position, player.mp), (position, mp))
        self.assertEqual(enemy.effect_stats, {7: 12, 8: 6})


if __name__ == "__main__":
    unittest.main()
