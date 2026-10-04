from copy import deepcopy
import unittest
from test_combat_effect_runtime import NativeRuntimeFactoryTests
from wakfu_server.combat_effect_dispatch import EffectInvocation


class DecurseRuntimeTests(NativeRuntimeFactoryTests):
    def test_native321_reduces_real3442_reapplies_owned_child_and_new_caster(self):
        preview = deepcopy(self.fight)
        effect = deepcopy(
            next(
                e
                for e in self.effects.values()
                if e["effect_class"] == 321 and e["parameter_count"] == 2
            )
        )
        effect.update(
            parameters=[3442, 0, 10, 0],
            criteria="",
            target_masks=[None] * 7,
            probability_base=100,
            probability_per_level=0,
            native_target_selector={"class": "fcE", "mask": 1},
        )
        self.effects["990321"] = effect
        dispatcher, packets = self.factory()(preview, {})
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
            [op for op, b in packets], [13497, 13497, 13560, 13560, 13497, 13497]
        )
