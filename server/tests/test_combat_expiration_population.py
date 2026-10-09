"""Only actual registered native timers drive fighter/area/group expiration."""
import unittest
import struct
from dataclasses import asdict
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_carrier import state_carrier_payload


class ExpirationPopulationTests(unittest.TestCase):
    def fight(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        foe = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [actor, foe],
            {actor.position, foe.position},
            {0: {actor.position}, 1: {foe.position}},
        )
        fight.ready(3)
        return fight

    def test_group_only_clock_is_expired_by_runtime(self):
        fight = self.fight()
        payload = group_payload(
            uid=901,
            base_uid=901,
            generic_effect=101,
            caster_id=7,
            target_id=7,
            cell=(0, 0, 0),
            container_type=11,
            container_id=101,
            timing_payload=native_time_payload(),
        )
        fight.native_owned_group_effects[901] = dict(
            uid=901,
            target_id=7,
            effect_class=42,
            payload=payload.hex(),
            timer=dict(actor_id=7, expiration_round=2, phase="start"),
        )
        fight.native_retained_records[901] = asdict(
            RetainedEffect(
                uid=901, target_id=7, manager_id=7, effect_class=42, generic_effect=101
            )
        )
        fight.native_retained_order.append(901)
        wire = RuntimeMessages(fight)
        self.assertEqual(
            wire._expire_owned(actor_id=-7, round_number=2, phase="start"), []
        )
        out = wire._expire_owned(actor_id=7, round_number=2, phase="start")
        self.assertEqual([opcode for opcode, _ in out], [13560, 13420])
        self.assertEqual(fight.native_owned_group_effects, {})
        self.assertEqual(fight.native_retained_records, {})

    def area(self, fight, retired):
        ledger = StateLedger(91)
        ledger._entries = (
            RunningState(
                902,
                1304,
                1,
                7,
                91,
                1,
                "caster",
                False,
                (),
                -1,
                True,
                StateTimer(7, 2, "start"),
            ),
        )
        row = dict(
            uid=91,
            cell=(2, 0, 0),
            native_area_contract="faY",
            native_running_effect_manager=True,
            state_ledger=ledger,
        )
        target = (
            fight.native_retired_area_managers if retired else fight.native_effect_areas
        )
        target[91] = row
        fight.state_wire_payloads[902] = state_carrier_payload(
            uid=902,
            base_uid=902,
            caster_id=7,
            target_id=91,
            state_id=1304,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=-1,
        ).hex()
        return ledger

    def test_actual_area_clock_expires_on_caster_for_active_and_retired_manager(self):
        for retired in (False, True):
            with self.subTest(retired=retired):
                fight = self.fight()
                self.area(fight, retired)
                wire = RuntimeMessages(fight)
                self.assertEqual(
                    wire._expire_owned(actor_id=-7, round_number=2, phase="start"), []
                )
                out = wire._expire_owned(actor_id=7, round_number=2, phase="start")
                self.assertEqual([opcode for opcode, _ in out], [13560, 13420])
                pool = (
                    fight.native_retired_area_managers
                    if retired
                    else fight.native_effect_areas
                )
                self.assertEqual(pool[91]["state_ledger"].entries, ())
                self.assertNotIn(902, fight.state_wire_payloads)

    def test_missing_area_payload_rolls_back_expiration(self):
        fight = self.fight()
        ledger = self.area(fight, False)
        del fight.state_wire_payloads[902]
        wire = RuntimeMessages(fight)
        wire.action_id = 8
        with self.assertRaisesRegex(ValueError, "payload"):
            wire._expire_owned(actor_id=7, round_number=2, phase="start")
        self.assertEqual(wire.action_id, 8)
        self.assertEqual(len(ledger.entries), 1)

    def test_area_state_expiration_removes_649_child_before_carrier(self):
        from wakfu_server.combat_stat_effects import owned_effect_payload

        fight = self.fight()
        self.area(fight, False)
        payload = owned_effect_payload(
            uid=903, base_uid=903, generic_effect=101, caster_id=7, target_id=7, value=0
        )
        fight.owned_stat_effects[903] = dict(
            uid=903,
            target_id=7,
            caster_id=7,
            effect_class=649,
            family="eWn",
            spell_id=101,
            payload=payload.hex(),
            state_uid=902,
            timer=None,
        )
        fight.native_spell_grants = {7: {101: dict(uid=101, reference=101, level=1)}}
        wire = RuntimeMessages(fight)
        packets = wire._expire_owned(actor_id=7, round_number=2, phase="start")
        removed = [
            struct.unpack(">i", body[12:16])[0]
            for opcode, body in packets
            if opcode == 13560
        ]
        self.assertEqual(removed, [649, 310])
        self.assertEqual(fight.native_spell_grants[7], {})
        self.assertEqual(fight.native_removed_spell_uids[7], {101})
        self.assertEqual(fight.owned_stat_effects, {})
