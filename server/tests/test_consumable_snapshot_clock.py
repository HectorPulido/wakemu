"""Snapshot timing preserves the imported native consumable carrier."""
from test_combat_consumable_states import CombatConsumableStateProjectionTests


class ConsumableSnapshotClockTests(CombatConsumableStateProjectionTests):
    # Reuse setup only; inherited gameplay cases belong to their original suite.
    def test_partial_import_serializes_actual_active_snapshot(self):
        from wakfu_server.combat_consumable_states import install
        from wakfu_server.combat_remote_effects import (
            active_actor_effects,
            decode_remote_effects,
        )

        fight = self.fixture.fight
        install(
            fight,
            {"id": 7, "consumable_states": [self.state_row()]},
            self.fixture.factory(),
            owner_id=3,
            now_ms=1_000,
        )
        before = tuple(fight.actors[7].state_ledger.entries)
        encoded = active_actor_effects(fight, 7, now_milliseconds=101_000)
        self.assertTrue(encoded)
        carriers = tuple(
            row for row in decode_remote_effects(encoded) if row.effect_class == 310
        )
        self.assertEqual(
            tuple(row.remaining_milliseconds for row in carriers), (400_000,)
        )
        self.assertEqual(tuple(fight.actors[7].state_ledger.entries), before)

    def test_partial_clock_requires_exact_consumable_uid_binding(self):
        from wakfu_server.combat_consumable_states import install
        from wakfu_server.combat_remote_effects import active_actor_effects

        fight = self.fixture.fight
        install(
            fight,
            {"id": 7, "consumable_states": [self.state_row()]},
            self.fixture.factory(),
            owner_id=3,
            now_ms=1_000,
        )
        binding = fight.native_consumable_initializations[7][0]
        for change in (
            {"combat_uid": binding["combat_uid"] + 1},
            {"state_id": binding["state_id"] + 1},
            {"world_uid": 0},
            {"clock": "event"},
        ):
            fight.native_consumable_initializations[7] = (dict(binding, **change),)
            with self.assertRaisesRegex(ValueError, "state310 clock context"):
                active_actor_effects(fight, 7, now_milliseconds=101_000)
