import json
import struct
import unittest
from dataclasses import replace
from itertools import count
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_effect_timing import schedule_effect_timer
from wakfu_server.combat_state_ledger import StateTimeline
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_timed_expiration import prepare_timed_expiration
from wakfu_server.combat_runtime_messages import RuntimeMessages
import test_combat_state_child_removal as child_fixture


class TimedExpirationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = json.loads((DATA_ROOT / "spell-effect-trees.json").read_text())[
            "effects"
        ]
        cls.registry = json.loads(
            (DATA_ROOT / "effect-characteristic-registry.json").read_text()
        )
        child_fixture.StateChildRemovalTests.setUpClass()

    def make_stat(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        fight.ready(3)
        npc.effect_stats = {27: 80}
        npc.effect_minima = {27: 0}
        npc.effect_maxima = {27: 200}
        npc.effect_frozen = frozenset()
        packets = []
        provider = NativeEffectTimingProvider({})
        uid = count(200)
        handler = NativeStatHandler(
            fight,
            packets,
            self.registry,
            action_id=1,
            allocate_uid=lambda: next(uid),
            context=lambda e, i: provider.stat(fight, None, e, i),
        )
        handler(
            self.effects["317002"], {}, EffectInvocation(317002, 1, 7, -7, (1, 0, 0))
        )
        return fight, packets

    def test_real_positive_stat_expires_on_caster_start_not_target(self):
        fight, packets = self.make_stat()
        self.assertEqual(fight.actors[-7].effect_stats[27], 110)
        self.assertEqual(
            fight.owned_stat_effects[200]["timer"],
            dict(actor_id=7, expiration_round=2, phase="start"),
        )
        preview, outbox = prepare_timed_expiration(
            fight, actor_id=-7, round_number=2, phase="start", action_id=2
        )
        self.assertEqual(outbox, [])
        self.assertIn(200, preview.owned_stat_effects)
        preview, outbox = prepare_timed_expiration(
            fight, actor_id=7, round_number=2, phase="start", action_id=2
        )
        self.assertEqual(preview.actors[-7].effect_stats[27], 80)
        self.assertEqual(preview.owned_stat_effects, {})
        self.assertEqual(outbox[0][0], 13560)
        self.assertEqual(fight.actors[-7].effect_stats[27], 110)  # Atomic preview only.

    def test_tctimer_extension_end_and_already_passed_actor(self):
        clock = StateTimeline(3, 7, 1, 1, "active")

        def timer(**values):
            return schedule_effect_timer(
                duration=1,
                expire_at_end=values.get("end", False),
                extend_on_clock_turn=values.get("extend", False),
                clock_actor_id=7,
                timeline=clock,
            )

        self.assertEqual(timer(), StateTimer(7, 4, "start"))
        self.assertEqual(timer(extend=True), StateTimer(7, 5, "start"))
        self.assertEqual(timer(end=True), StateTimer(7, 3, "end"))
        clock = StateTimeline(3, -7, 1, 0, "active")
        self.assertEqual(timer(), StateTimer(7, 5, "start"))

    def test_state_expiration_removes_child_before_carrier_and_atomic_missing_payload(
        self,
    ):
        fixture = child_fixture.StateChildRemovalTests()
        fixture.setUp()
        fixture.apply()
        fight = fixture.fight
        actor = fight.actors[7]
        entry = actor.state_ledger.entries[0]
        actor.state_ledger._entries = (replace(entry, timer=StateTimer(7, 2, "start")),)
        preview, outbox = prepare_timed_expiration(
            fight, actor_id=7, round_number=2, phase="start", action_id=2
        )
        self.assertEqual(preview.actors[7].effect_stats[20], 80)
        self.assertEqual(preview.actors[7].state_ledger.entries, ())
        self.assertEqual(preview.owned_stat_effects, {})
        self.assertEqual(
            [struct.unpack(">i", body[12:16])[0] for opcode, body in outbox], [120, 310]
        )
        del fight.state_wire_payloads[entry.uid]
        with self.assertRaisesRegex(ValueError, "payload"):
            prepare_timed_expiration(
                fight, actor_id=7, round_number=2, phase="start", action_id=2
            )
        self.assertEqual(actor.effect_stats[20], 100)
        self.assertIn(201, fight.owned_stat_effects)

    def test_runtime_failed_expiry_preserves_action_counter_and_actor_identity(self):
        fixture = child_fixture.StateChildRemovalTests()
        fixture.setUp()
        fixture.apply()
        fight = fixture.fight
        actor = fight.actors[7]
        entry = actor.state_ledger.entries[0]
        actor.state_ledger._entries = (replace(entry, timer=StateTimer(7, 2, "start")),)
        del fight.state_wire_payloads[entry.uid]
        wire = RuntimeMessages(fight)
        wire.action_id = 8
        with self.assertRaisesRegex(ValueError, "payload"):
            wire._expire_owned(actor_id=7, round_number=2, phase="start")
        self.assertEqual(wire.action_id, 8)
        self.assertIs(fight.actors[7], actor)
        self.assertEqual(actor.effect_stats[20], 100)

    def test_runtime_expiry_before_stats_and_after_turn_ack_barrier(self):
        fight, _ = self.make_stat()
        original_actor = fight.actors[-7]
        wire = RuntimeMessages(fight, stats_serializer=lambda actor: b"known")
        wire.turn_started()
        wire.end_turn(3, 7, 1)
        wire.acknowledge_turn(struct.pack(">i", 1))
        outgoing = wire.end_server_turn(-7, 2)
        self.assertFalse(any(opcode == 13560 for opcode, body in outgoing))
        pending = wire.acknowledge_turn(struct.pack(">i", 2))
        opcodes = [opcode for opcode, body in pending]
        self.assertLess(opcodes.index(13560), opcodes.index(12873))
        self.assertEqual(fight.actors[-7].effect_stats[27], 80)
        self.assertIs(fight.actors[-7], original_actor)
