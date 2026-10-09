"""Synthetic activation of real eWE metadata; cosmetic inventory is not attested."""
import unittest
from copy import deepcopy
from dataclasses import replace
from random import Random
import test_combat_effect_runtime as runtime_fixture
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_effect_removal import running_effect_removal


class DeathScriptRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_fixture.NativeRuntimeFactoryTests.setUpClass()

    def fixture(self, *, criterion="", probability=True):
        fx = runtime_fixture.NativeRuntimeFactoryTests()
        fx.setUp()
        preview = deepcopy(fx.fight)
        original = fx.states["effects"]["185395"]
        effect = deepcopy(original)
        # Original guard depends on account cosmetic data absent from current
        # server authority. This explicit synthetic unit does not prove it.
        effect["criteria"] = criterion
        timing = NativeEffectTimingProvider(fx.states)
        actors = OrdinaryActorAuthority(
            characters={
                7: dict(id=7, breed=15, level=1),
                8: dict(id=8, breed=15, level=1),
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
            native_phase = lifecycle.phase

            def phase(e, i, **kwargs):
                phases.append((kwargs["channel"], kwargs["uid"], kwargs["value"]))
                return native_phase(e, i, **kwargs)

            lifecycle.phase = phase
            return lifecycle

        contexts = replace(
            fx.contexts,
            stat=timing.stat,
            healing_events=events,
            probability=lambda p, plan, value, i: probability,
        )
        effects = dict(fx.effects)
        effects["185395"] = effect
        # Factory merges states first; matching synthetic state copy avoids an
        # intentional criteria override conflicting with the native record.
        states = dict(fx.states)
        states["effects"] = dict(fx.states["effects"])
        states["effects"]["185395"] = effect
        factory = fx.factory(effects=effects, states=states, contexts=contexts)
        dispatcher, packets = factory(preview, dict(spell_id=6266, evaluation_level=1))
        invocation = EffectInvocation(185395, 1, 7, 7, (0, 0, 0))
        return preview, dispatcher, packets, phases, invocation, original

    def test_factory_native_lifecycle_registers_exact_manager_then_removes_with_codec(
        self,
    ):
        preview, dispatcher, packets, phases, invocation, original = self.fixture()
        self.assertEqual(original["criteria"], "HasActiveCosmeticId(5, 20753)")
        dispatcher.execute(invocation)
        self.assertEqual([p[0] for p in phases], [1, 2, 3, 4])
        self.assertEqual({p[1] for p in phases}, {200})
        self.assertEqual(preview.native_retained_order, [200])
        record = preview.native_retained_records[200]
        self.assertEqual(
            (
                record["manager_id"],
                record["target_id"],
                record["effect_class"],
                record["generic_effect"],
            ),
            (7, 7, 1099, 185395),
        )
        row = preview.owned_stat_effects[200]
        self.assertEqual(preview.actors[7].native_death_script_id, row["actual"])
        self.assertTrue(any(opcode == 12613 for opcode, payload in packets))
        expected = running_effect_removal(
            preview.id,
            1,
            effect_class=1099,
            target_id=7,
            uid=200,
            running_effect_payload=bytes.fromhex(row["payload"]),
        )
        retention = dispatcher.native_retention
        from wakfu_server.combat_dispel import select_dispel

        view = retention.view()
        # Original eWE metadata is not generically dispellable and has an
        # infinite duration. Exact native dispel selectors precede protection.
        self.assertEqual(select_dispel(view.entries, []), ())
        selected = select_dispel(view.entries, [185395])
        self.assertEqual([entry.uid for entry in selected], [200])
        retention.removal(view).remove(entry.uid for entry in selected)
        retention.synchronize()
        self.assertEqual(packets[-1], (13560, expected))
        self.assertEqual(preview.actors[7].native_death_script_id, -1)
        self.assertEqual(preview.native_retained_records, {})
        self.assertEqual(preview.native_retained_order, [])

    def test_retained_wrapper_cleanup_survives_condition_probability_and_error_rejection(
        self,
    ):
        for criterion, probability, error in [
            ("False", True, False),
            ("", False, False),
            ("MissingNativeCriterion()", True, True),
        ]:
            with self.subTest(criterion=criterion, probability=probability):
                (
                    preview,
                    dispatcher,
                    packets,
                    phases,
                    invocation,
                    original,
                ) = self.fixture(criterion=criterion, probability=probability)
                if error:
                    with self.assertRaises((UnsupportedEffectExecution, ValueError)):
                        dispatcher.execute(invocation)
                else:
                    dispatcher.execute(invocation)
                cleanup = dispatcher.handlers[1099].cancel_prepared
                handler = cleanup.__self__
                self.assertEqual(handler.prepared, {})
                self.assertEqual(handler.runners, {})
                self.assertEqual(preview.owned_stat_effects, {})
                self.assertEqual(preview.native_retained_records, {})
                self.assertEqual([p[0] for p in phases], [1])


if __name__ == "__main__":
    unittest.main()
