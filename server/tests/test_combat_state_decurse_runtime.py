from copy import deepcopy
import unittest
import test_combat_effect_runtime as runtime_helpers
from wakfu_server.combat_effect_dispatch import EffectInvocation


class DecurseRuntimeTests(unittest.TestCase):
    # Reuse the fixture without rediscovering every unrelated factory test.
    setUpClass = classmethod(
        runtime_helpers.NativeRuntimeFactoryTests.setUpClass.__func__
    )

    def setUp(self):
        from wakfu_server.combat_static_catalogs import CompiledEffects

        self.compiled = CompiledEffects.from_published()
        runtime_helpers.NativeRuntimeFactoryTests.setUp(
            self, effects=self.compiled.source_effects
        )

    factory = runtime_helpers.NativeRuntimeFactoryTests.factory
    condition = runtime_helpers.NativeRuntimeFactoryTests.condition

    def test_native321_reduces_real3442_reapplies_owned_child_and_new_caster(self):
        preview = deepcopy(self.fight)
        # Select an actual two-parameter native321 reduction runner. Steamer
        # roots345157/345158 have one parameter and remove the entire state.
        reference, native_effect = next(
            (reference, effect)
            for reference, effect in self.compiled.source_effects.items()
            if effect["effect_class"] == 321 and effect["parameter_count"] == 2
        )
        effect = dict(native_effect)
        self.assertEqual((effect["effect_class"], effect["parameter_count"]), (321, 2))
        effect.update(
            parameters=[3442, 0, 10, 0],
            criteria="",
            target_masks=[None] * 7,
            probability_base=100,
            probability_per_level=0,
            native_target_selector={"class": "fcE", "mask": 1},
        )
        compiled = self.compiled.with_effect_sources({"990321": effect})
        # This isolated runner is not a spell cast. Explicitly prove the
        # native absent-container contract while retaining real ownership.
        dispatcher, packets = self.factory(
            effects=compiled.source_effects,
            states=compiled.source_states,
            compiled_effects=compiled,
        )(preview, {"native_retained_container": {"present": False}})
        self.assertIsNotNone(dispatcher.native_retention)
        from wakfu_server.combat_static_catalogs import DefinitionOverlay

        # Publish matching fixture metadata for the synthetic990321 delta.
        # Keep the original native runner's lifecycle/timing contract; only
        # its reduction parameters change, exactly as in the execution row.
        retention = dispatcher.native_retention
        metadata = dict(retention.metadata)
        original_metadata = metadata["effects"][reference]
        reduction_metadata = dict(original_metadata, parameters=effect["parameters"])
        metadata["effects"] = DefinitionOverlay(
            metadata["effects"], {"990321": reduction_metadata}
        )
        retention.metadata = metadata
        dispatcher.execute(EffectInvocation(159412, 20, 7, 7, (0, 0, 0)))
        old = preview.actors[7].state_ledger.entries[0]
        dispatcher.execute(EffectInvocation(990321, 1, 8, 7, (0, 0, 0)))
        entry = preview.actors[7].state_ledger.entries[0]
        self.assertEqual((entry.reference, entry.level, entry.caster_id), (3442, 10, 8))
        self.assertNotEqual(entry.uid, old.uid)
        self.assertNotIn(old.uid, preview.state_wire_payloads)
        self.assertTrue(
            all(
                c["state_uid"] == entry.uid for c in preview.owned_stat_effects.values()
            )
        )
        self.assertEqual(
            [op for op, b in packets], [12613, 12613, 13560, 13560, 12613, 12613]
        )
