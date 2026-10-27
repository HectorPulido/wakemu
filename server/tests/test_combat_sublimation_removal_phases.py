"""Bounded original scalar-removal consumers and owned external boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeExternalEvent
from wakfu_server.combat_external_event_removal import (
    has_removal_subscription,
    removal_recipients,
)


class SublimationRemovalPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_event_replay import NativeEventReplayTests

        NativeEventReplayTests.setUpClass()
        cls.replay_fixture = NativeEventReplayTests
        cls.original = json.loads(
            (
                Path(__file__).parent / "fixtures/native_sublimation_removal.json"
            ).read_text()
        )

    def applied(self, reference):
        from wakfu_server.combat_stat_handler import (
            NativeStatHandler,
            StatExecutionContext,
        )

        fixture = self.replay_fixture()
        fixture.setUp()
        effect = deepcopy(self.original["effects"][str(reference)])
        fixture.effects[str(reference)] = effect
        fixture.retention.metadata["effects"][str(reference)] = deepcopy(
            self.original["retained_metadata"]["effects"][str(reference)]
        )
        for actor in fixture.fight.actors.values():
            actor.effect_stats = {9: 10, 86: 10}
            actor.effect_minima = {9: 0, 86: 0}
            actor.effect_maxima = {9: 100, 86: 100}
            actor.effect_frozen = frozenset()
        handler = NativeStatHandler(
            fixture.fight,
            fixture.packets,
            self.original["registry"],
            action_id=1,
            allocate_uid=fixture.fight.allocate_effect_uid,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        fixture.retention.stat_handler = handler
        fixture.dispatcher.handlers[effect["effect_class"]] = fixture.retention.wrap(
            handler
        )
        level = 10 if reference == 269274 else 1
        fixture.dispatcher.execute(EffectInvocation(reference, level, 7, 7, (0, 0, 0)))
        owned = [
            uid
            for uid, row in fixture.fight.owned_stat_effects.items()
            if row["effect_class"] == effect["effect_class"]
        ]
        self.assertEqual(len(owned), 1)
        return fixture, effect, owned[0]

    def test_original_scalar_removals_preserve_roles_inverse_and_definition_authority(
        self,
    ):
        from wakfu_server.fight_checkpoint_store import snapshot

        for reference, event, stat, expected in (
            (383314, 1016, 9, 12),
            (382293, 1001, 86, 6),
            (269274, 500, None, None),
            (241198, 1024, None, None),
        ):
            with self.subTest(reference=reference):
                fixture, effect, uid = self.applied(reference)
                fixture.dispatcher.native_retention = fixture.retention
                self.assertTrue(has_removal_subscription(fixture.dispatcher, event))
                self.assertIn(
                    str(uid),
                    json.loads(json.dumps(snapshot(fixture.fight)))[
                        "owned_stat_effects"
                    ],
                )
                if stat is not None:
                    self.assertEqual(
                        fixture.fight.actors[7].effect_stats[stat], expected
                    )
                for channel in (6, 4):
                    fixture.replay(
                        NativeExternalEvent(7, (event,), channel),
                        authority=fixture.authority,
                    )
                    self.assertIn(uid, fixture.fight.owned_stat_effects)
                # Every original native leaf above is reverse-subscribed.
                fixture.replay(
                    NativeExternalEvent(7, (event,), 40), authority=fixture.authority
                )
                self.assertNotIn(uid, fixture.fight.owned_stat_effects)
                self.assertNotIn(uid, fixture.fight.native_retained_records)
                if stat is not None:
                    self.assertEqual(fixture.fight.actors[7].effect_stats[stat], 10)
                self.assertEqual(fixture.packets[-1][0], 13560)

        fixture, effect, uid = self.applied(383314)
        del fixture.dispatcher.effects["383314"]
        before = snapshot(fixture.fight)
        with self.assertRaisesRegex(ValueError, "original effect definition"):
            fixture.replay(
                NativeExternalEvent(7, (1016,), 40), authority=fixture.authority
            )
        self.assertEqual(snapshot(fixture.fight), before)

    def test_turn_and_cast_close_only_real_boundaries_and_keep_native_roles(self):
        from test_combat_turn_events import OwnedTurnEndTests
        from test_combat_cast_events import CastEventsTests
        from wakfu_server.combat_turn_events import (
            deliver_turn_start,
            deliver_turn_regeneration,
        )
        from wakfu_server.combat_active_spell import active_spell_scope
        from wakfu_server.combat_cast_events import cast_event_scope
        from wakfu_server.combat_attack_preparation import deliver_attack_preparation

        fight, dispatcher, events = OwnedTurnEndTests().fixture()
        fight.native_owned_group_effects[99] = {
            "native_subscription_masks": [
                None,
                None,
                [1001, 1037],
                None,
                None,
                None,
                None,
            ]
        }
        for callback in (deliver_turn_start, deliver_turn_regeneration):
            start = len(events)
            callback(dispatcher, actor_id=7)
            actual = events[start:]
            self.assertEqual(
                [row.channel for row in actual], [6, 60, 61, 61, 4, 40, 41, 41]
            )
            self.assertTrue(
                all(row.turn_boundary_context is not None for row in actual)
            )
        with self.assertRaises(ValueError):
            deliver_turn_start(dispatcher, actor_id=7)
        self.assertEqual(
            removal_recipients(((7, 6), (7, 60), (-7, 61))), ((7, 4), (7, 40), (-7, 41))
        )
        with self.assertRaises(ValueError):
            removal_recipients(((7, 3),))

        for actual_attack in (False, True):
            fight, dispatcher, plan, events = CastEventsTests().fixture()
            fight.native_owned_group_effects[99] = {
                "native_subscription_masks": [
                    None,
                    None,
                    [500, 1024],
                    None,
                    None,
                    None,
                    None,
                ]
            }
            with active_spell_scope(fight, 4820, level=200), cast_event_scope(
                dispatcher, plan
            ):
                if actual_attack:
                    with patch(
                        "wakfu_server.combat_ordinary_authority.ordinary_container_type",
                        return_value=11,
                    ), patch(
                        "wakfu_server.combat_ordinary_events.OrdinaryHealingEvents.phase"
                    ):
                        invocation = SimpleNamespace(
                            caster_id=7, state_uid=None, native_trigger_context=None
                        )
                        self.assertTrue(
                            deliver_attack_preparation(
                                SimpleNamespace(preview=fight, plan=plan),
                                {},
                                invocation,
                                uid=123,
                                final_modifier=None,
                                runner_modifier=None,
                            )
                        )
                # Cast roots still see the marker; consumed only on successful close.
                self.assertFalse(any(row[0] == 500 for row in events))
            removals = [row for row in events if row[1] in (4, 40, 41)]
            self.assertEqual(any(row[0] == 500 for row in removals), actual_attack)
            self.assertEqual(
                [row[1] for row in removals if row[0] == 1024], [4, 40, 41, 41]
            )

    def test_critical_boundary_removes_real_scalar_without_fabricating_damage(self):
        from wakfu_server.combat_critical_hit_events import (
            deliver_completed_critical_hit,
        )
        from wakfu_server.combat_damage_handler import (
            NativeDamageHandler,
            DamageExecutionContext,
        )
        from wakfu_server.combat_ordinary_events import OrdinaryDamageEvents

        fixture, effect, uid = self.applied(383314)
        fixture.dispatcher.native_retention = fixture.retention
        fixture.dispatcher.native_clone_authority = fixture.authority
        fixture.dispatcher.replay_event = fixture.replay
        lifecycle = object.__new__(OrdinaryDamageEvents)
        lifecycle.preview = fixture.fight
        lifecycle.plan = fixture.retention.plan
        lifecycle.replay = fixture.replay
        lifecycle.retention = fixture.retention
        handler = object.__new__(NativeDamageHandler)
        handler.fight = fixture.fight
        handler.retention = fixture.retention
        handler.event_lifecycle = lifecycle
        invocation = EffectInvocation(900001, 1, 7, -7, (1, 0, 0))
        context = DamageExecutionContext(True, True, False, True, 11, False)
        before_hp = fixture.fight.actors[-7].hp
        self.assertEqual(
            deliver_completed_critical_hit(
                handler,
                {"effect_class": 1},
                invocation,
                uid=999,
                context=replace(context, critical=False),
                result={"value": 0},
            ),
            (),
        )
        self.assertIn(uid, fixture.fight.owned_stat_effects)
        deliver_completed_critical_hit(
            handler,
            {"effect_class": 1},
            invocation,
            uid=999,
            context=context,
            result={"value": 0},
        )
        self.assertNotIn(uid, fixture.fight.owned_stat_effects)
        self.assertEqual(fixture.fight.actors[7].effect_stats[9], 10)
        self.assertEqual(fixture.fight.actors[-7].hp, before_hp)
