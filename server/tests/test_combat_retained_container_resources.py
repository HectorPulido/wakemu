"""Original Spirit operations through central retention, not bare handlers."""
from types import SimpleNamespace
import unittest

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_container_cleanup import NativeContainerCleanupHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_stat_handler import NativeStatHandler
import test_combat_container_cleanup as cleanup_fixtures
import test_combat_resource_fill as resource_fixtures


def original_metadata(reference):
    row = native_catalog.record(
        DATA_ROOT / "native-retained-effect-metadata.json", "effects", reference
    )
    if row is None:
        raise AssertionError("Original native retained metadata must be published")
    return {"states": {}, "spells": {}, "effects": {str(reference): row}}


class RetainedContainerResourceTests(unittest.TestCase):
    def test_actual_cleanup_definitions_execute_inside_central_wrapper(self):
        for family, kind, reference in ((1031, 12, 410219), (1033, 36, 411311)):
            with self.subTest(family=family):
                (
                    fight,
                    retention,
                    packets,
                    _,
                ) = cleanup_fixtures.ContainerCleanupTests().fixture(kind)
                effect = native_catalog.record(
                    DATA_ROOT / "combat-state-definitions.json", "effects", reference
                )
                retention.metadata = original_metadata(reference)
                phases = []
                handler = NativeContainerCleanupHandler(
                    retention,
                    family=family,
                    allocate_uid=lambda: 999,
                    rng=lambda: 0.5,
                    event_lifecycle=SimpleNamespace(
                        phase=lambda *args, channel, **kwargs: phases.append(channel)
                    ),
                )
                invocation = handler.prepare(
                    effect,
                    {"parameters": []},
                    EffectInvocation(reference, 1, 7, 7, (0, 0, 0)),
                )
                self.assertTrue(
                    retention.wrap(handler)(effect, {"parameters": []}, invocation)
                )
                self.assertEqual(phases, [1, 2, 3, 4])
                self.assertEqual(set(fight.native_retained_records), {200, 91})
                self.assertEqual([opcode for opcode, _ in packets], [13560] * 4)
                self.assertEqual(handler.prepared, {})

    def test_original_resource_families_register_and_reverse_through_shared_owner(self):
        for family, stat, field in ((272, 3, "mp"), (983, 2, "ap")):
            with self.subTest(family=family):
                (
                    fight,
                    actor,
                    handler,
                    effect,
                    invocation,
                    packets,
                ) = resource_fixtures.ResourceFillTests().fixture(family)
                before = getattr(actor, field)
                retention = NativeRetainedRuntime(
                    fight,
                    packets,
                    plan={"native_retained_container": {"present": False}},
                    state_catalog={},
                    action_id=5,
                    timing=None,
                    metadata=original_metadata(invocation.reference),
                )
                # Production central removal uses the ordinary stat owner, whose
                # catalog does not need a fabricated eYP parameter descriptor.
                retention.stat_handler = NativeStatHandler(
                    fight,
                    packets,
                    {"effects": {}},
                    action_id=5,
                    allocate_uid=lambda: 999,
                    context=handler.context,
                    rng=lambda: 0.5,
                )
                self.assertTrue(retention.wrap(handler)(effect, {}, invocation))
                (uid,) = fight.native_retained_records
                self.assertEqual(
                    fight.native_retained_records[uid]["effect_class"], family
                )
                self.assertEqual(
                    fight.owned_stat_effects[uid]["actual"],
                    actor.effect_maxima[stat] - before,
                )
                self.assertEqual(getattr(actor, field), actor.effect_maxima[stat])
                retention.removal(retention.view()).remove([uid])
                retention.synchronize()
                self.assertEqual(getattr(actor, field), before)
                self.assertFalse(fight.owned_stat_effects)
                self.assertFalse(fight.native_retained_records)
                self.assertEqual(packets[-1][0], 13560)

    def test_unsupported_retained_family_reports_original_identity_before_execution(
        self,
    ):
        (
            fight,
            retention,
            packets,
            _,
        ) = cleanup_fixtures.ContainerCleanupTests().fixture()
        effect = dict(cleanup_fixtures.FIXTURE["effect411311"], effect_class=123456)
        metadata = original_metadata(411311)
        metadata["effects"]["411311"] = dict(
            metadata["effects"]["411311"], effect_class=123456
        )
        retention.metadata = metadata
        retention.stat_handler.registry = {}
        invoked = []
        invocation = EffectInvocation(
            411311, 1, 7, 7, (0, 0, 0), native_running_uid=999
        )
        with self.assertRaisesRegex(
            ValueError, r"effect=411311, family=123456, uid=999"
        ):
            retention.wrap(lambda *args: invoked.append(True))(effect, {}, invocation)
        self.assertEqual(invoked, [])
        self.assertEqual(packets, [])
