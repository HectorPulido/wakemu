"""Actual factory eYH retained insertion precedes the complete L3/L4 view."""
import unittest
from copy import deepcopy
from dataclasses import replace
from random import Random

import test_combat_effect_runtime as runtime_fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents


class AIControlRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_fixture.NativeRuntimeFactoryTests.setUpClass()

    def test_actual_factory_retained_view_is_complete_during_both_post_phases(self):
        fx = runtime_fixture.NativeRuntimeFactoryTests()
        fx.setUp()
        preview = deepcopy(fx.fight)
        for actor in preview.actors.values():
            actor.native_controlled_by_ai = False
        timing = NativeEffectTimingProvider(fx.states)
        actors = OrdinaryActorAuthority(
            characters={
                7: dict(id=7, breed=3, level=1),
                8: dict(id=8, breed=3, level=1),
            },
            monsters={-7: dict(id=-7, ref=5525)},
            decks={7: [6266], 8: []},
            excluded_decks={7: [], 8: []},
        )
        adapter = NativeServerRuntimeAdapter(
            actor_authority=actors,
            cast=ordinary_cast_authority(
                actors=actors, timing=timing, rng=Random(7), critical=False
            ),
        )
        phases = []

        def events(p, plan, replay, retention):
            lifecycle = OrdinaryHealingEvents(
                adapter=adapter,
                preview=p,
                plan=plan,
                replay=replay,
                retention=retention,
            )
            original = lifecycle.phase

            def phase(e, i, **kwargs):
                # Exercise the exact guard which failed in real class3 casts.
                view = retention.view()
                phases.append((kwargs["channel"], tuple(x.uid for x in view.entries)))
                return original(e, i, **kwargs)

            lifecycle.phase = phase
            return lifecycle

        contexts = replace(fx.contexts, stat=timing.stat, healing_events=events)
        factory = fx.factory(contexts=contexts, displacement_authority=actors)
        dispatcher, packets = factory(preview, dict(spell_id=6266, evaluation_level=1))
        # Original eYH definition; no criteria, parameters or flags are changed.
        invocation = EffectInvocation(
            66821,
            1,
            7,
            7,
            (0, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertTrue(dispatcher.execute(invocation))
        self.assertEqual(phases, [(1, ()), (2, ()), (3, (200,)), (4, (200,))])
        record = preview.native_retained_records[200]
        self.assertEqual((record["effect_class"], record["manager_id"]), (325, 7))
        view = dispatcher.native_retention.view()
        dispatcher.native_retention.removal(view).remove((200,))
        dispatcher.native_retention.synchronize()
        self.assertEqual(preview.native_retained_records, {})
        self.assertFalse(preview.actors[7].native_controlled_by_ai)
        self.assertEqual(packets[-1][0], 13560)
