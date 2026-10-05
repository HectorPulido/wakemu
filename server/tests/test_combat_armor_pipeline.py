"""Actual owned armor cast with a legal passive and atomic failure boundary."""
import random
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_active_spells as native
from wakfu_server.combat_armor import NativeArmorHandler
from wakfu_server.combat_event_replay import NativeEventReplay
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class NativeArmorPipelineTests(unittest.TestCase):
    def test_armor_real_lifecycle_passive_and_post_application_failure_rollback(self):
        origin, enemy = (-8, -7, -1), (-7, -7, -1)
        terrain = native.bounded_arena(
            native.map_geometry(1134), origin, [enemy], radius=12
        )
        character, monster, source = native.fixture(
            11, 60, enemy, terrain, origin, monster_reference=3646, monster_level=12
        )
        # Native Pacto de Sangre unlocks25; no granted spell or rank is invented.
        deck = encode_deck([5033], [5053])
        rng = random.Random(0)
        initialized, _ = prepare_server_initialization(
            character,
            {-7: monster},
            source,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        while initialized.current.id != 7:
            initialized.end_server_turn(initialized.current.id, initialized.turn_id)
        before = snapshot(initialized)
        body = struct.pack(
            ">qqiih", 7, (7 << 32) | 5033, *initialized.actors[-7].position
        )

        def los(a, b, preview):
            return authoritative_visible(
                1134,
                a,
                b,
                preview,
                blocking_footprints={
                    identity: {actor.position[:2]}
                    for identity, actor in preview.actors.items()
                    if actor.hp > 0
                },
            )

        seen = []
        replay = NativeEventReplay.__call__

        def capture(instance, event, **kwargs):
            if getattr(event, "effect_action_id", None) == 1013:
                seen.append((event.channel, event.value, event.uid, event.event_ids))
            return replay(instance, event, **kwargs)

        with patch.object(NativeEventReplay, "__call__", capture):
            result = prepare_server_spell(
                body,
                character,
                {-7: monster},
                initialized,
                3,
                deck,
                action_id=2,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(initialized), before)
        self.assertGreater(
            result.fight.actors[7].effect_stats[97],
            initialized.actors[7].effect_stats[97],
        )
        self.assertTrue(seen)
        self.assertEqual([row[0] for row in seen], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertEqual(len({row[2] for row in seen}), 1)
        self.assertTrue(all(0 in row[3] for row in seen))
        self.assertIn(13497, [opcode for opcode, _ in result.packets])

        # Source controller wiring is exercised through actual emitted replay.
        # This injects the audited mutation API; it does not claim family430
        # listener selection before that central handler is registered.
        baseline_armor = result.fight.actors[7].effect_stats[97]
        baseline_rows = [
            row
            for row in result.fight.owned_stat_effects.values()
            if row.get("effect_class") == 1013
        ]
        baseline_delta = baseline_armor - initialized.actors[7].effect_stats[97]
        for phase_to_change in (2, 3):
            controllers = []

            def mutate_at_phase(instance, event, **kwargs):
                outcome = replay(instance, event, **kwargs)
                if (
                    getattr(event, "effect_action_id", None) == 1013
                    and event.channel == phase_to_change
                ):
                    self.assertIsNotNone(event.runner_modifier)
                    event.runner_modifier.mutate(1, 25, False)
                    controllers.append(event.runner_modifier)
                return outcome

            with patch.object(NativeEventReplay, "__call__", mutate_at_phase):
                mutated = prepare_server_spell(
                    body,
                    character,
                    {-7: monster},
                    initialized,
                    3,
                    deck,
                    action_id=4 + phase_to_change,
                    line_of_sight=los,
                    critical=False,
                    rng=rng,
                )
            self.assertEqual(len(controllers), 1)
            self.assertEqual(
                mutated.fight.actors[7].effect_stats[97],
                baseline_armor + (25 if phase_to_change == 2 else 0),
            )
            rows = [
                row
                for row in mutated.fight.owned_stat_effects.values()
                if row.get("effect_class") == 1013
            ]
            self.assertEqual(len(rows), len(baseline_rows))
            self.assertEqual(controllers[0].value, baseline_delta + 25)
            for row, baseline_row in zip(rows, baseline_rows):
                self.assertEqual(row["actual"], baseline_row["actual"] + 25)
            self.assertEqual(snapshot(initialized), before)

        # Original eZL350672 is -20 percent. Invoke the real dispatcher while
        # the actual armor replay source is scoped; selection is deliberately
        # injected, not claimed to be a native armor-event subscription.
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_final_modifier import final_modifier_source

        native_430 = []

        def dispatch_native_430(instance, event, **kwargs):
            outcome = replay(instance, event, **kwargs)
            if getattr(event, "effect_action_id", None) == 1013 and event.channel == 2:
                invocation = EffectInvocation(
                    350672,
                    60,
                    7,
                    7,
                    instance.retention.fight.actors[7].position,
                    native_trigger_context={
                        "uid": event.uid,
                        "value": event.value,
                        "effect_action_id": 1013,
                        "caster_id": 7,
                        "target_id": 7,
                    },
                )
                with final_modifier_source(event):
                    self.assertTrue(instance.dispatcher.execute(invocation))
                native_430.append((event.value, event.runner_modifier.value))
            return outcome

        with patch.object(NativeEventReplay, "__call__", dispatch_native_430):
            original_modifier = prepare_server_spell(
                body,
                character,
                {-7: monster},
                initialized,
                3,
                deck,
                action_id=7,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )
        self.assertEqual(len(native_430), 1)
        initial_amount, changed_amount = native_430[0]
        self.assertLess(changed_amount, initial_amount)
        self.assertEqual(
            original_modifier.fight.actors[7].effect_stats[97],
            initialized.actors[7].effect_stats[97] + changed_amount,
        )
        self.assertEqual(snapshot(initialized), before)

        original_apply = NativeArmorHandler.__call__

        def fail_after_apply(handler, effect, values, invocation):
            self.assertTrue(original_apply(handler, effect, values, invocation))
            raise ValueError("Injected post-armor lifecycle fault")

        random_before = rng.getstate()
        with patch.object(NativeArmorHandler, "__call__", fail_after_apply):
            with self.assertRaisesRegex(ValueError, "post-armor"):
                prepare_server_spell(
                    body,
                    character,
                    {-7: monster},
                    initialized,
                    3,
                    deck,
                    action_id=3,
                    line_of_sight=los,
                    critical=False,
                    rng=rng,
                )
        self.assertEqual(snapshot(initialized), before)
        self.assertEqual(rng.getstate(), random_before)


if __name__ == "__main__":
    unittest.main()
