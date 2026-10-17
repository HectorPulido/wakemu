"""Spectator births close before full native timeline recovery."""
import unittest

import test_combat_runtime_messages as runtime_fixture
from test_combat_reconnect_summon_timeline import timeline_fields
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_spectator_snapshot import current_snapshot
from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap


class SpectatorSummonTimelineTests(unittest.TestCase):
    def fixture(self, controlled, current_summon, properties):
        from types import SimpleNamespace
        from wakfu_server.combat_summon import SummonSpecification
        from wakfu_server.combat_summon_codec import summon_application

        (
            fight,
            summon,
            _,
        ) = runtime_fixture.RuntimeMessageTests._initial_restore_with_innate_summon(
            100, summon_controlled=controlled
        )
        fight.turn_id = 13
        if 114 in properties:
            slot = fight.order.index(summon.id)
            fight.order.pop(slot)
            if slot < fight.turn_index:
                fight.turn_index -= 1
            fight.native_timeline_member_counters.pop(str(summon.id))
            fight.native_summon_registrations[summon.id][
                "fight_properties"
            ] = properties
            creation = summon_application(
                fight.id,
                1,
                uid=901,
                base_uid=901,
                effect_reference=96363,
                caster_id=100,
                cell=summon.position,
                specification=SummonSpecification(
                    2382, 200, controlled, 0, 0, "caster", 0
                ),
                actor_id=summon.id,
                obstacle_index=5,
                properties=properties,
                timing_payload=b"",
                container_type=1,
                container_id=3799,
            )
            fight.native_summon_creation_deliveries[summon.id] = {
                "opcode": creation[0],
                "payload_hex": creation[1].hex(),
            }
        else:
            fight.native_timeline_member_counters[str(summon.id)] = 3
            if current_summon:
                fight.turn_index = fight.order.index(summon.id)
        shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            runtime=SimpleNamespace(native_action_id=41),
            join_context={
                "arena": dict(
                    map_id=1134,
                    instance_id=0,
                    x=0,
                    y=0,
                    width=4,
                    height=1,
                    min_z=0,
                    max_z=0,
                    cell_masks=[0] * 4,
                ),
                "terrain_effect_id": 99,
                "terrain_instance_id": 0,
                "leaders": {0: 100, 1: -200},
            },
        )
        return fight, summon, shared

    def test_controlled_and_ordinary_births_restore_exact_current_and_progress(self):
        for controlled in (False, True):
            for current_summon in (False, True):
                with self.subTest(controlled=controlled, current_summon=current_summon):
                    fight, summon, shared = self.fixture(controlled, current_summon, ())
                    before = source_snapshot(fight)
                    packets = current_snapshot(
                        fight,
                        shared,
                        actor_payload=lambda *args: (b"stats", b"\x00\x00"),
                        deadline_ms=123456,
                    )
                    bootstrap = decode_spectator_bootstrap(packets[0][1])
                    phase, orders, progress, index, turn = timeline_fields(
                        bootstrap["myG"]
                    )
                    self.assertEqual((phase, index), (0, -1))
                    self.assertNotIn(summon.id, orders[0])
                    birth = fight.native_summon_creation_deliveries[summon.id]
                    packet = (birth["opcode"], bytes.fromhex(birth["payload_hex"]))
                    self.assertEqual(packets.count(packet), 1)
                    birth_index = packets.index(packet)
                    self.assertEqual(packets[birth_index + 1][0], 13420)
                    recovery_index, recovery = next(
                        (
                            (i, body)
                            for i, (op, body) in enumerate(packets)
                            if op == 12053
                        )
                    )
                    self.assertLess(birth_index + 1, recovery_index)
                    phase, orders, progress, index, turn = timeline_fields(
                        recovery[15:]
                    )
                    self.assertEqual((phase, turn), (1, 13))
                    self.assertEqual(orders[0].count(summon.id), 1)
                    self.assertEqual(progress[summon.id], 3)
                    self.assertEqual(orders[0][index], fight.current.id)
                    self.assertEqual(packets[recovery_index + 1][0], 12514)
                    self.assertEqual(source_snapshot(fight), before)

    def test_property114_birth_remains_out_of_recovered_timeline(self):
        for controlled in (False, True):
            fight, summon, shared = self.fixture(controlled, False, (114,))
            before = source_snapshot(fight)
            packets = current_snapshot(
                fight,
                shared,
                actor_payload=lambda *args: (b"stats", b"\x00\x00"),
                deadline_ms=123456,
            )
            recovery = next((body for op, body in packets if op == 12053))
            _, orders, progress, index, _ = timeline_fields(recovery[15:])
            self.assertNotIn(summon.id, orders[0])
            self.assertNotIn(summon.id, progress)
            self.assertEqual(orders[0][index], fight.current.id)
            self.assertEqual(source_snapshot(fight), before)

    def test_extra_turn_current_slot_survives_both_recipient_recoveries(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from wakfu_server.combat_additional_turn import additional_turn_insertion
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot

        for controlled in (False, True):
            for properties in ((), (114,)):
                for current_summon in (False, True) if not properties else (False,):
                    with self.subTest(
                        controlled=controlled,
                        properties=properties,
                        current_summon=current_summon,
                    ):
                        fight, summon, shared = self.fixture(
                            controlled, current_summon, properties
                        )
                        fight.native_base_turn_order = list(fight.order)
                        target = fight.current.id
                        insertion = additional_turn_insertion(
                            fight.order,
                            fight.turn_index,
                            mode=0,
                            offset=1,
                            caster_id=100,
                            target_id=target,
                        )
                        self.assertTrue(insertion["applied"])
                        fight.order = insertion["order"]
                        fight.turn_index = insertion["insertion"]
                        self.assertEqual(fight.order.count(target), 2)
                        shared.runtime.turn_deadline = None
                        shared.runtime.awaiting_ack = None
                        before = source_snapshot(fight)
                        full = []
                        if target != summon.id:
                            with self.assertRaisesRegex(
                                ValueError, "Invalid initial timeline membership"
                            ):
                                from wakfu_server.combat_wire import initial_timeline

                                members = [
                                    identity
                                    for identity in fight.order
                                    if identity != summon.id
                                ]
                                initial_timeline(members, members)
                        with patch("time.time", return_value=1700000000):
                            role_packets = (
                                current_snapshot(
                                    fight,
                                    shared,
                                    actor_payload=lambda *args: (b"stats", b"\x00\x00"),
                                    deadline_ms=1700000000000,
                                ),
                                owned_snapshot(
                                    fight,
                                    shared,
                                    SimpleNamespace(account_id=1),
                                    actor_payload=lambda *args: (b"stats", b"\x00\x00"),
                                ),
                            )
                        for packets in role_packets:
                            recovery = next(
                                (body for op, body in packets if op == 12053)
                            )
                            phase, orders, progress, index, turn = timeline_fields(
                                recovery[15:]
                            )
                            self.assertEqual(orders[0], tuple(fight.order))
                            self.assertEqual(
                                orders[1], tuple(fight.native_base_turn_order)
                            )
                            self.assertEqual(index, fight.turn_index)
                            self.assertEqual(orders[0][index], target)
                            self.assertEqual(orders[0].count(target), 2)
                            self.assertEqual(
                                progress,
                                {
                                    int(key): value
                                    for key, value in fight.native_timeline_member_counters.items()
                                },
                            )
                            self.assertEqual((phase, turn), (1, 13))
                            if properties:
                                self.assertNotIn(summon.id, orders[0])
                            full.append(recovery)
                        self.assertEqual(full[0], full[1])
                        self.assertEqual(source_snapshot(fight), before)

    def test_birth_fence_precedes_full_timeline_and_preserves_bonus_snapshot(self):
        from wakfu_server.combat_spectator_wire import timeline_snapshot

        fight, summon, shared = self.fixture(True, True, ())
        before = source_snapshot(fight)
        packets = current_snapshot(
            fight,
            shared,
            actor_payload=lambda *args: (b"stats", b"\x00\x00"),
            deadline_ms=123456,
        )
        decoded = decode_spectator_bootstrap(packets[0][1])
        self.assertNotIn(summon.id, timeline_fields(decoded["myG"])[1][0])
        self.assertEqual(decoded["timeline_snapshot"], timeline_snapshot(3))
        birth = fight.native_summon_creation_deliveries[summon.id]
        birth_index = packets.index(
            (birth["opcode"], bytes.fromhex(birth["payload_hex"]))
        )
        recovery_index = next(i for i, (op, _) in enumerate(packets) if op == 12053)
        self.assertEqual(packets[birth_index + 1][0], 13420)
        self.assertLess(birth_index + 1, recovery_index)
        full = timeline_fields(packets[recovery_index][1][15:])
        self.assertEqual(full[1][0].count(summon.id), 1)
        self.assertEqual(full[1][0][full[3]], summon.id)
        self.assertEqual(source_snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
