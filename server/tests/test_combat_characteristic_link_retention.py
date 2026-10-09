import struct
import unittest
from types import SimpleNamespace

import test_combat_characteristic_link as link_fixtures
from wakfu_server.combat_retained_runtime import (
    NativeRetainedRuntime,
    native_retained_metadata,
)
from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    RetainedEffect,
    register_owned_removals,
)
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class NativeCharacteristicLinkRetentionTests(unittest.TestCase):
    def test_real_definition_wrap_registers_source_listener_and_removes_owned_link(
        self,
    ):
        (
            fight,
            handler,
            packets,
            _,
        ) = link_fixtures.NativeCharacteristicLinkTests().fixture()
        for actor in fight.actors.values():
            actor.state_ledger = SimpleNamespace(entries=())
        fight.state_wire_payloads = {}
        fight.native_owned_group_effects = {}
        fight.native_owned_area_effects = {}
        fight.native_retained_records = {}
        fight.native_retained_order = []
        fight.native_retained_tracking = True
        # The installed native definition supplies manager ownership; listener
        # direction must never substitute for the actual owner_on_caster flag.
        reference = 308162
        metadata = native_retained_metadata()["effects"][str(reference)]
        self.assertIs(metadata["owner_on_caster"], False)
        effect = {
            key: metadata[key]
            for key in (
                "effect_class",
                "variant",
                "minimum_level",
                "maximum_level",
                "parameters",
            )
        }
        effect.update(
            native_execution_mode=metadata["definition_type"],
            native_definition_class="eVy",
            native_timing_definition=dict(ryE=-1, ryF=0, ryH=0, ryI=0),
        )
        invocation = EffectInvocation(reference, 200, 7, 9, (0, 0, 0))
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={"effects": {str(reference): metadata}},
        )
        stat_handler = SimpleNamespace(
            fight=fight, packets=packets, action_id=1, registry={}
        )
        stat_handler.remove = NativeStatHandler.remove.__get__(stat_handler)
        retention.stat_handler = stat_handler

        self.assertTrue(retention.wrap(handler)(effect, [], invocation))
        self.assertEqual(fight.native_retained_order, [101])
        record = fight.native_retained_records[101]
        self.assertEqual(record["manager_id"], 9)
        self.assertEqual(record["generic_effect"], reference)
        self.assertEqual(record["effect_class"], 1038)
        self.assertEqual(fight.actors[7].effect_stats[103], 40)
        fight.actors[9].effect_stats[7] = 80
        self.assertEqual(fight.actors[7].effect_stats[103], 50)
        view = NativeRetainedEffectView(
            fight, [RetainedEffect(**record)], population_verified_complete=True
        )
        removal = NativeRetainedRemoval(view)
        register_owned_removals(
            removal, stat_handler=stat_handler, packets=packets, action_id=1
        )
        removal.remove([101])
        retention.synchronize()

        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        self.assertEqual(fight.native_characteristic_links, {})
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(fight.native_retained_records, {})
        self.assertEqual(fight.native_retained_order, [])
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(struct.unpack(">qq", packets[-1][1][-16:]), (9, 101))
        fight.actors[9].effect_stats[7] = 90
        self.assertEqual(fight.actors[7].effect_stats[103], 10)


if __name__ == "__main__":
    unittest.main()
