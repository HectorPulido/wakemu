"""Shared recovery keeps native usage rules for non-Hupper spell references.

Iop 4776 and Pandawa 8591 are exercised in their class-specific runtime
fixtures. This module uses their native limit records with the shared recovery
engine, without rebuilding the large character-state catalog.
"""
import copy
import struct
import unittest

from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_spell_usage import consume_usage, limits, validate_usage
import test_combat_shared_timeline_recovery as recovery_fixture


class OtherBreedRecoveryUsageTests(unittest.TestCase):
    IOP_JUDGMENT = 4776
    PANDAWA_DRUNKENNESS = 8591

    def state(self, *, pending):
        (
            registry,
            shared,
            sessions,
            _,
            _,
        ) = recovery_fixture.SharedTimelineRecoveryTests().state(pending=pending)
        fight = shared.fight
        for actor in fight.actors.values():
            if actor.physical_radius is None:
                # The shared-recovery fixture uses point actors; keep its
                # existing positions and register that geometry explicitly.
                actor.physical_radius = 0
        if not hasattr(fight, "native_global_pv_collections"):
            initialize_global_pv_collections(fight, tuple(fight.actors))
        return registry, shared, sessions

    def recover(self, registry, shared, session):
        registry.recover_timeline(
            shared.fight.id,
            session,
            struct.pack(">i", shared.fight.id),
            now_ms=20000,
        )

    def test_same_turn_recovery_preserves_iop_target_and_turn_caps_and_pandawa_cap(
        self,
    ):
        registry, shared, sessions = self.state(pending=False)
        fight = shared.fight
        actor = fight.current
        self.assertEqual(actor.id, 65)
        self.assertEqual(
            limits(self.IOP_JUDGMENT, 20),
            dict(per_target=2, per_turn=4, interval=0),
        )
        self.assertEqual(
            limits(self.PANDAWA_DRUNKENNESS, 200),
            dict(per_target=0, per_turn=2, interval=0),
        )
        fight.native_spell_usage[str(actor.id)] = {
            "turn": actor.turn_count,
            "casts": {str(self.IOP_JUDGMENT): 3, str(self.PANDAWA_DRUNKENNESS): 2},
            "targets": {str(self.IOP_JUDGMENT): {"-200": 2}},
            "last": {},
        }
        before = copy.deepcopy(fight.native_spell_usage)

        self.recover(registry, shared, sessions[2])
        packets = registry.drain(fight.id, sessions[0])[0].packets
        opcodes = [opcode for opcode, _ in packets]
        self.assertNotIn(13482, opcodes)
        fight = shared.fight
        actor = fight.current
        self.assertEqual(fight.native_spell_usage, before)
        with self.assertRaisesRegex(ValueError, "maximum casts per target"):
            validate_usage(fight, actor, self.IOP_JUDGMENT, 20, (5, 0, 0))
        with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
            validate_usage(fight, actor, self.PANDAWA_DRUNKENNESS, 200, (5, 0, 0))

        fight.native_spell_usage[str(actor.id)]["casts"][str(self.IOP_JUDGMENT)] = 4
        fight.native_spell_usage[str(actor.id)]["targets"][str(self.IOP_JUDGMENT)] = {}
        with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
            validate_usage(fight, actor, self.IOP_JUDGMENT, 20, (5, 0, 0))

    def test_new_turn_recovery_keeps_native_records_until_successful_cast(self):
        registry, shared, sessions = self.state(pending=True)
        fight = shared.fight
        actor = fight.current
        self.assertEqual(actor.id, 65)
        fight.native_spell_usage[str(actor.id)] = {
            "turn": actor.turn_count - 1,
            "casts": {str(self.IOP_JUDGMENT): 4, str(self.PANDAWA_DRUNKENNESS): 2},
            "targets": {str(self.IOP_JUDGMENT): {"-200": 2}},
            "last": {},
        }
        before = copy.deepcopy(fight.native_spell_usage)

        self.recover(registry, shared, sessions[2])
        batches = [registry.drain(fight.id, peer)[0].packets for peer in sessions]
        self.assertTrue(all(batch == batches[0] for batch in batches))
        opcodes = [opcode for opcode, _ in batches[0]]
        self.assertEqual(opcodes.count(13482), 1)
        self.assertEqual(opcodes.count(13337), 1)
        self.assertNotIn(12514, opcodes)
        self.assertLess(opcodes.index(12053), opcodes.index(13337))
        self.assertLess(opcodes.index(13337), opcodes.index(13482))
        timeline = recovery_fixture.decoded_timeline(
            next(body for opcode, body in batches[0] if opcode == 12053)
        )
        self.assertEqual(timeline["phase"], 2)
        self.assertEqual(timeline["turn"], fight.turn_id - 1)
        self.assertEqual(timeline["current"], fight.current.id)
        self.assertEqual(fight.native_spell_usage, before)
        fight = shared.fight
        actor = fight.current

        for spell, level, cell in (
            (self.IOP_JUDGMENT, 20, (5, 0, 0)),
            (self.PANDAWA_DRUNKENNESS, 200, (5, 0, 0)),
        ):
            plan = validate_usage(fight, actor, spell, level, cell)
            consume_usage(
                fight,
                dict(actor_id=actor.id, spell_id=spell, native_usage=plan),
            )
            usage = fight.native_spell_usage[str(actor.id)]
            self.assertEqual(usage["turn"], actor.turn_count)
            self.assertEqual(usage["casts"][str(spell)], 1)
        self.assertEqual(
            fight.native_spell_usage[str(actor.id)]["targets"][str(self.IOP_JUDGMENT)][
                "-200"
            ],
            1,
        )
