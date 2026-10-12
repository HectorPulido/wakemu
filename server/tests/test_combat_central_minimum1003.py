"""Actual native minimum producer enters and leaves central ownership."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from test_combat_minimum_ko_resource import MinimumKOResourceTests
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_minimum_resource import remove_minimum_resource


class CentralMinimumTests(unittest.TestCase):
    def test_actual170720_records_pc14_and_releases_owned_identity(self):
        fight, actor, handler, packets = MinimumKOResourceTests().fixture()
        fight.native_retained_tracking = True
        data = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual170720.json"
            ).read_text()
        )
        effect = data["combat-state-definitions.json"]
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={
                "effects": {"170720": data["native-retained-effect-metadata.json"]}
            },
        )
        retention.stat_handler = SimpleNamespace(registry={})
        invocation = EffectInvocation(
            170720,
            1,
            7,
            -7,
            actor.position,
            native_retained_container={"present": False},
        )
        self.assertTrue(retention.wrap(handler)(effect, {}, invocation))
        self.assertEqual(actor.effect_minima[14], 1)
        self.assertEqual(fight.native_retained_order, [901])
        row = fight.native_retained_records[901]
        self.assertEqual(
            (row["effect_class"], row["generic_effect"], row["manager_id"]),
            (1003, 170720, -7),
        )
        remove_minimum_resource(handler, 901)
        retention.synchronize()
        self.assertEqual(actor.effect_minima[14], 0)
        self.assertEqual(fight.native_retained_records, {})
        self.assertEqual(fight.native_retained_order, [])

    def test_unimplemented_retained_family_remains_rejected_before_handler(self):
        from unittest.mock import Mock

        fight, actor, handler, packets = MinimumKOResourceTests().fixture()
        fight.native_retained_tracking = True
        data = json.loads(
            (
                Path(__file__).parent
                / "fixtures/next_central_recovery"
                / "actual170720.json"
            ).read_text()
        )
        effect = dict(data["combat-state-definitions.json"], effect_class=999999)
        metadata = dict(
            data["native-retained-effect-metadata.json"], effect_class=999999
        )
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={"effects": {"170720": metadata}},
        )
        retention.stat_handler = SimpleNamespace(registry={})
        invocation = EffectInvocation(
            170720,
            1,
            7,
            -7,
            actor.position,
            native_retained_container={"present": False},
        )
        callback = Mock()
        with self.assertRaisesRegex(ValueError, "lacks central ownership machinery"):
            retention.wrap(callback)(effect, {}, invocation)
        callback.assert_not_called()
        self.assertEqual(packets, [])
        self.assertEqual(fight.owned_stat_effects, {})
