"""Per-turn Hupper usage across same-turn and new-turn timeline recovery."""
import struct
import unittest
from copy import deepcopy
from unittest.mock import patch

from wakfu_server.combat_spell_usage import consume_usage, validate_usage
from wakfu_server.combat_usage_targets import NativeUsageTarget
import test_combat_shared_timeline_recovery as recovery_fixture


class HupperRecoveryUsageTests(unittest.TestCase):
    WATER_FOUR = 5564
    INTERVAL_SPELL = 5594

    def usage_state(self, actor, *, previous_turn=False):
        return {
            "turn": actor.turn_count - int(previous_turn),
            "casts": {str(self.WATER_FOUR): 2},
            "targets": {str(self.WATER_FOUR): {"-200": 2}},
            "last": {str(self.INTERVAL_SPELL): 1},
        }

    def usage_patches(self):
        from wakfu_server import combat_spell_usage
        from wakfu_server import combat_usage_targets

        def rules(reference, level, context=None):
            if reference == self.WATER_FOUR:
                return dict(per_target=2, per_turn=2, interval=0)
            if reference == self.INTERVAL_SPELL:
                return dict(per_target=0, per_turn=0, interval=2)
            raise AssertionError(f"Unexpected spell reference {reference}")

        return (
            patch.object(
                combat_spell_usage,
                "native_limits",
                return_value={
                    str(self.WATER_FOUR): {"conditional": []},
                    str(self.INTERVAL_SPELL): {"conditional": []},
                },
            ),
            patch.object(combat_spell_usage, "limits", side_effect=rules),
            patch.object(
                combat_usage_targets,
                "usage_targets",
                return_value=(NativeUsageTarget(-200, True),),
            ),
        )

    def validate(self, fight, actor, spell):
        return validate_usage(fight, actor, spell, 200, (5, 0, 0))

    def recover(self, registry, shared, session):
        return registry.recover_timeline(
            shared.fight.id,
            session,
            struct.pack(">i", shared.fight.id),
            now_ms=20000,
        )

    def test_same_turn_recovery_keeps_water_caps_and_5594_interval(self):
        (
            registry,
            shared,
            sessions,
            _,
            _,
        ) = recovery_fixture.SharedTimelineRecoveryTests().state()
        actor = shared.fight.current
        self.assertEqual(actor.id, 65)
        shared.fight.native_spell_usage[str(actor.id)] = self.usage_state(actor)
        before_usage = dict(shared.fight.native_spell_usage[str(actor.id)])
        before_turn = shared.fight.turn_id
        before_round = shared.fight.native_timeline_round
        before_members = deepcopy(shared.fight.native_timeline_member_counters)

        with self.usage_patches()[0], self.usage_patches()[1], self.usage_patches()[2]:
            with self.assertRaisesRegex(ValueError, "per turn"):
                self.validate(shared.fight, actor, self.WATER_FOUR)
            with self.assertRaisesRegex(ValueError, "interval"):
                self.validate(shared.fight, actor, self.INTERVAL_SPELL)

            self.recover(registry, shared, sessions[1])
            packet = next(
                body
                for opcode, body in registry.drain(377, sessions[1])[0].packets
                if opcode == 12053
            )
            decoded = recovery_fixture.decoded_timeline(packet)
            self.assertEqual(decoded["phase"], 1)
            self.assertEqual(decoded["turn"], shared.fight.turn_id)
            self.assertFalse(
                any(
                    opcode == 13482
                    for batch in shared.outboxes.values()
                    for entry in batch
                    for opcode, _ in entry.packets
                )
            )

            current = shared.fight.current
            self.assertEqual(
                shared.fight.native_spell_usage[str(current.id)], before_usage
            )
            self.assertEqual(shared.fight.turn_id, before_turn)
            self.assertEqual(shared.fight.native_timeline_round, before_round)
            self.assertEqual(
                shared.fight.native_timeline_member_counters, before_members
            )
            with self.assertRaisesRegex(ValueError, "per turn"):
                self.validate(shared.fight, current, self.WATER_FOUR)
            with self.assertRaisesRegex(ValueError, "interval"):
                self.validate(shared.fight, current, self.INTERVAL_SPELL)

    def test_pending_new_actor_begin_is_replayed_once_and_keeps_interval(self):
        (
            registry,
            shared,
            sessions,
            _,
            _,
        ) = recovery_fixture.SharedTimelineRecoveryTests().state(pending=True)
        actor = shared.fight.current
        self.assertEqual(actor.id, 65)
        before_turn = shared.fight.turn_id
        before_round = shared.fight.native_timeline_round
        before_members = deepcopy(shared.fight.native_timeline_member_counters)
        shared.fight.native_spell_usage[str(actor.id)] = self.usage_state(
            actor, previous_turn=True
        )

        patches = self.usage_patches()
        with patches[0], patches[1], patches[2]:
            old_turn_water = self.validate(shared.fight, actor, self.WATER_FOUR)
            self.assertEqual(old_turn_water["targets"], ["-200"])
            with self.assertRaisesRegex(ValueError, "interval"):
                self.validate(shared.fight, actor, self.INTERVAL_SPELL)

            self.recover(registry, shared, sessions[2])
            first_batches = [registry.drain(377, peer)[0].packets for peer in sessions]
            self.assertTrue(all(batch == first_batches[0] for batch in first_batches))
            first = first_batches[0]
            opcodes = [opcode for opcode, _ in first]
            self.assertEqual(opcodes.count(12053), 1)
            self.assertEqual(opcodes.count(13482), 1)
            self.assertEqual(opcodes.count(13337), 1)
            self.assertNotIn(12514, opcodes)
            self.assertLess(opcodes.index(12053), opcodes.index(13337))
            self.assertLess(opcodes.index(13337), opcodes.index(13482))
            timeline = recovery_fixture.decoded_timeline(
                next(body for opcode, body in first if opcode == 12053)
            )
            self.assertEqual(timeline["phase"], 2)
            self.assertEqual(timeline["turn"], shared.fight.turn_id - 1)
            self.assertEqual(timeline["current"], actor.id)
            self.assertEqual(shared.fight.turn_id, before_turn)
            self.assertEqual(shared.fight.native_timeline_round, before_round)
            self.assertEqual(
                shared.fight.native_timeline_member_counters, before_members
            )
            saved_usage = shared.fight.native_spell_usage[str(actor.id)]
            self.assertEqual(saved_usage["turn"], actor.turn_count - 1)
            self.assertEqual(saved_usage["casts"][str(self.WATER_FOUR)], 2)
            self.assertEqual(saved_usage["targets"][str(self.WATER_FOUR)]["-200"], 2)
            self.assertEqual(saved_usage["last"][str(self.INTERVAL_SPELL)], 1)

            # The new actor turn is admitted because the saved per-turn ledger
            # belongs to the prior turn. A successful cast lazily starts this
            # turn's counters; recovery itself does not erase history.
            accepted = self.validate(
                shared.fight, shared.fight.current, self.WATER_FOUR
            )
            consume_usage(
                shared.fight,
                dict(
                    actor_id=actor.id, spell_id=self.WATER_FOUR, native_usage=accepted
                ),
            )
            self.assertEqual(
                shared.fight.native_spell_usage[str(actor.id)]["casts"][
                    str(self.WATER_FOUR)
                ],
                1,
            )

            # No pending 13482 remains. A repeated coX is phase 1 and does not
            # grant a second turn begin or reset the cast just consumed.
            self.recover(registry, shared, sessions[1])
            second_batches = [registry.drain(377, peer)[0].packets for peer in sessions]
            self.assertTrue(all(batch == second_batches[0] for batch in second_batches))
            second = second_batches[0]
            self.assertEqual(sum(opcode == 13482 for opcode, _ in second), 0)
            second_timeline = recovery_fixture.decoded_timeline(
                next(body for opcode, body in second if opcode == 12053)
            )
            self.assertEqual(second_timeline["phase"], 1)
            self.assertEqual(
                shared.fight.native_spell_usage[str(actor.id)]["casts"][
                    str(self.WATER_FOUR)
                ],
                1,
            )
            with self.assertRaisesRegex(ValueError, "interval"):
                self.validate(shared.fight, shared.fight.current, self.INTERVAL_SPELL)

            second_cast = self.validate(
                shared.fight, shared.fight.current, self.WATER_FOUR
            )
            consume_usage(
                shared.fight,
                dict(
                    actor_id=actor.id,
                    spell_id=self.WATER_FOUR,
                    native_usage=second_cast,
                ),
            )
            turn_usage = shared.fight.native_spell_usage[str(actor.id)]
            self.assertEqual(turn_usage["casts"][str(self.WATER_FOUR)], 2)
            self.assertEqual(turn_usage["targets"][str(self.WATER_FOUR)]["-200"], 2)
            with self.assertRaisesRegex(ValueError, "per turn"):
                self.validate(shared.fight, shared.fight.current, self.WATER_FOUR)
            self.assertEqual(turn_usage["last"][str(self.INTERVAL_SPELL)], 1)


if __name__ == "__main__":
    unittest.main()
