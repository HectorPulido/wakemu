"""Original instant987 child45980 creates a real retained981 carrier."""
import unittest

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_handler import StateCarrierContext


class NativeExternalRetainedStateTests(unittest.TestCase):
    def test_original_987_child_creates_timed_981_and_additive_replacement(self):
        from test_combat_consumable_outcome import CombatConsumableOutcomeTests

        (
            character,
            _monsters,
            _deck,
            fight,
            factory,
        ) = CombatConsumableOutcomeTests()._fixture(10657)
        actor = fight.actors[character["id"]]
        dispatcher, _packets = factory(action_id=2)(
            fight, {"native_retained_container": {"present": False}}
        )
        context = StateCarrierContext(
            0,
            0,
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=0),
        )
        last_uid = None
        for level in (1, 2):
            with fight.effect_resolution():
                self.assertTrue(
                    dispatcher.native_retention.apply_state_reference(
                        dispatcher.native_state_handler,
                        EffectInvocation(2226, 1, actor.id, actor.id, actor.position),
                        987,
                        1,
                        carrier_context=context,
                    )
                )
            entries = [
                row for row in actor.state_ledger.entries if row.reference == 981
            ]
            self.assertEqual(1, len(entries))
            entry = entries[0]
            self.assertEqual(level, entry.level)
            self.assertEqual(240000, entry.realtime_duration)
            self.assertIsNone(entry.timer)
            self.assertTrue(entry.realtime_in_combat)
            self.assertIsInstance(entry.realtime_deadline_ms, int)
            self.assertNotEqual(last_uid, entry.uid)
            self.assertIn(entry.uid, fight.state_wire_payloads)
            origin = fight.native_external_state_origins[entry.uid]
            self.assertEqual(
                (45980, 987, entry.uid, actor.id, fight.id),
                tuple(
                    origin[key]
                    for key in (
                        "effect_id",
                        "parent_state_id",
                        "combat_uid",
                        "character_id",
                        "fight_id",
                    )
                ),
            )
            self.assertGreater(origin["source_uid"], 0)
            self.assertGreater(origin["parent_uid"], 0)
            last_uid = entry.uid
        self.assertFalse(
            any(row.reference == 987 for row in actor.state_ledger.entries)
        )


if __name__ == "__main__":
    unittest.main()
