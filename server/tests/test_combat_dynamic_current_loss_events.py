"""Bounded real eWR40 producer, source controls and private-preview rollback."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest

import test_combat_stat_handler as stat_fixture
import test_combat_current_stat_area as area_fixture
from wakfu_server.combat_dynamic_current_loss_events import (
    resolved_current_loss_events,
)
from wakfu_server.combat_entry_executor import private_entry_preview
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext


class DynamicCurrentLossEventTests(unittest.TestCase):
    def fixture(self, stat, *, family=40, amount=50, executable=True):
        fixture = stat_fixture.StatHandlerTests()
        fixture.setUp()
        actor = fixture.fight.actors[7]
        actor.effect_stats[stat] = 12
        actor.effect_minima[stat] = 0
        actor.effect_maxima[stat] = 20
        fixture.handler.rng = lambda: 0.5
        fixture.handler.context = lambda *args: StatExecutionContext(
            executable, True, None, True, None
        )
        seen = []
        fixture.handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kwargs: seen.append(
                (
                    kwargs["channel"],
                    kwargs["_event_ids"],
                    invocation.caster_id,
                    invocation.target_id,
                    kwargs["value"],
                )
            )
        )
        effect = dict(
            effect_class=family,
            parameters=[amount, 0, 0, 0, stat, 0],
            target_masks=[None] * 7,
        )
        return fixture, actor, effect, seen

    def test_resolved_loss_sources_controls_absent_pa_and_rollback(self):
        for stat, event in ((90, 166), (109, 168)):
            with self.subTest(stat=stat):
                fixture, actor, effect, seen = self.fixture(stat)
                source_id = 7 if stat == 90 else -7
                invocation = fixture.handler.prepare(
                    effect, {}, replace(fixture.invocation, caster_id=source_id)
                )
                self.assertTrue(fixture.handler(effect, {}, invocation))
                self.assertEqual(actor.effect_stats[stat], 0)
                self.assertEqual(fixture.fight.owned_stat_effects[100]["actual"], 12)
                self.assertEqual(
                    seen,
                    [(1, (0,), source_id, 7, 0)]
                    + [
                        (channel, (0, event), source_id, 7, 50 if channel == 2 else 12)
                        for channel in (2, 3, 4)
                    ],
                )
                fixture.handler.remove(100)
                self.assertEqual(actor.effect_stats[stat], 12)

                # The same runner math remains frozen, and another PC/gain
                # cannot borrow these two current-loss declarations.
                frozen, frozen_actor, frozen_effect, frozen_seen = self.fixture(stat)
                frozen_actor.effect_frozen = frozenset({stat})
                prepared = frozen.handler.prepare(frozen_effect, {}, frozen.invocation)
                self.assertTrue(frozen.handler(frozen_effect, {}, prepared))
                self.assertEqual(frozen_actor.effect_stats[stat], 12)
                self.assertEqual(frozen.fight.owned_stat_effects[100]["actual"], 0)
                self.assertEqual([row[0] for row in frozen_seen], [1, 2, 3, 4])

                for family, selected in ((39, stat), (40, 20)):
                    other, _, other_effect, observed = self.fixture(
                        selected, family=family
                    )
                    prepared = other.handler.prepare(other_effect, {}, other.invocation)
                    self.assertTrue(other.handler(other_effect, {}, prepared))
                    self.assertTrue(all(event not in row[1] for row in observed))

                for executable, amount in ((False, 50), (True, 0)):
                    skipped, skipped_actor, skipped_effect, observed = self.fixture(
                        stat, amount=amount, executable=executable
                    )
                    prepared = skipped.handler.prepare(
                        skipped_effect, {}, skipped.invocation
                    )
                    self.assertFalse(skipped.handler(skipped_effect, {}, prepared))
                    self.assertEqual(skipped_actor.effect_stats[stat], 12)
                    self.assertEqual([row[0] for row in observed], [1])

                area = area_fixture.CurrentStatAreaTests()
                _, fight, handler, invocation, _, packets, _ = area.create()
                observed = []
                handler.event_lifecycle = SimpleNamespace(
                    phase=lambda *args, **kwargs: observed.append(kwargs["_event_ids"])
                )
                prepared = handler.prepare(effect, {}, invocation)
                self.assertTrue(handler(effect, {}, prepared))
                self.assertEqual(observed, [(0,)] * 4)
                self.assertFalse(packets)
                self.assertTrue(
                    fight.owned_stat_effects[prepared.native_running_uid][
                        "native_absent_characteristic"
                    ]
                )

                with self.assertRaisesRegex(
                    ValueError, "differs from actual runner plan"
                ):
                    resolved_current_loss_events(
                        effect,
                        fixture.registry["effects"]["40"],
                        level=1,
                        stat_id=109 if stat == 90 else 90,
                        target_has_characteristic=True,
                    )

                # Use the production private-entry boundary, fail after the
                # real PA application, and retain the original source/outbox.
                original, _, original_effect, _ = self.fixture(stat)
                before, preview = private_entry_preview(
                    original.fight, snapshot=source_snapshot, clone=deepcopy
                )
                private_packets = []
                private = NativeStatHandler(
                    preview,
                    private_packets,
                    original.registry,
                    action_id=2,
                    allocate_uid=lambda: 500,
                    context=original.handler.context,
                    rng=lambda: 0.5,
                )

                def fail_after_application(effect, invocation, **kwargs):
                    if kwargs["channel"] == 3:
                        self.assertEqual(preview.actors[7].effect_stats[stat], 0)
                        raise ValueError("Injected native listener failure")

                private.event_lifecycle = SimpleNamespace(phase=fail_after_application)
                prepared = private.prepare(original_effect, {}, original.invocation)
                with self.assertRaisesRegex(
                    ValueError, "Injected native listener failure"
                ):
                    private(original_effect, {}, prepared)
                self.assertEqual(source_snapshot(original.fight), before)
                self.assertFalse(original.packets)
                self.assertFalse(original.fight.owned_stat_effects)
