"""Original eXY PL cleanup through existing retained removal callbacks/codecs."""
from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.combat_container_cleanup import (
    ContainerTypeCleanupAuthority,
    NativeContainerCleanupHandler,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_runner_callbacks import runner_value_scope
import test_combat_state_cleanup as cleanup_fixture

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/native_container_cleanup_1033.json").read_text()
)


class ContainerCleanupTests(unittest.TestCase):
    def fixture(self, kind=36):
        return cleanup_fixture.CleanupRuntimeTests().fixture(
            second_flag=True,
            container_kind=kind,
        )

    def test_aptitude_container_is_removed_without_the_natural_state_cleanup_phase(
        self,
    ):
        fight, retention, packets, _ = self.fixture()
        ContainerTypeCleanupAuthority(retention, 7, 36).execute()
        self.assertEqual(
            [struct.unpack(">q", packet[-8:])[0] for _, packet in packets],
            [90, 101, 201, 100],
        )
        self.assertTrue(all(opcode == 13560 for opcode, _ in packets))
        self.assertEqual(set(fight.native_retained_records), {200, 91})
        self.assertEqual(
            [entry.uid for entry in fight.actors[7].state_ledger.entries], [200]
        )
        self.assertEqual(fight.actors[7].hp, 50)

    def test_equipment_container_uses_the_same_original_exy_contract(self):
        fight, retention, packets, _ = self.fixture(12)
        ContainerTypeCleanupAuthority(retention, 7, 12).execute()
        self.assertEqual(
            [struct.unpack(">q", packet[-8:])[0] for _, packet in packets],
            [90, 101, 201, 100],
        )
        self.assertEqual(set(fight.native_retained_records), {200, 91})

    def test_nonmatching_passive_and_natural_sources_remain_untouched(self):
        fight, retention, packets, _ = self.fixture(25)
        before = deepcopy(
            (
                fight.native_retained_records,
                fight.state_wire_payloads,
                fight.native_owned_group_effects,
                fight.actors[7].state_ledger.entries,
            )
        )
        ContainerTypeCleanupAuthority(retention, 7, 36).execute()
        self.assertEqual(
            (
                fight.native_retained_records,
                fight.state_wire_payloads,
                fight.native_owned_group_effects,
                fight.actors[7].state_ledger.entries,
            ),
            before,
        )
        self.assertEqual(packets, [])

    def test_forged_container_metadata_rejects_before_any_unapplication(self):
        fight, retention, packets, _ = self.fixture(12)
        fight.native_retained_records[90]["container_type"] = 36
        with self.assertRaisesRegex(ValueError, "PL key differs"):
            ContainerTypeCleanupAuthority(retention, 7, 36).execute()
        self.assertEqual(packets, [])
        self.assertIn(100, fight.state_wire_payloads)
        self.assertIn(90, fight.native_owned_group_effects)

    def test_actual_original_1033_record_uses_real_family_runner_lifecycle(self):
        fight, retention, packets, _ = self.fixture()
        effect = FIXTURE["effect411311"]
        phases, observed = [], []

        class Lifecycle:
            def phase(self, definition, invocation, **kwargs):
                phases.append(
                    (kwargs["channel"], kwargs["uid"], kwargs["runner_modifier"].family)
                )

        handler = NativeContainerCleanupHandler(
            retention,
            family=1033,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            event_lifecycle=Lifecycle(),
        )
        with runner_value_scope(
            lambda invocation, value: observed.append(value)
        ) as observer:
            invocation = EffectInvocation(
                411311, 1, 7, 7, (0, 0, 0), native_value_scope=observer
            )
            invocation = handler.prepare(effect, {"parameters": []}, invocation)
            self.assertTrue(handler(effect, {"parameters": []}, invocation))
        self.assertEqual(
            phases, [(1, 999, 1033), (2, 999, 1033), (3, 999, 1033), (4, 999, 1033)]
        )
        self.assertEqual(observed, [0])
        self.assertEqual(handler.prepared, {})
        self.assertEqual(len(packets), 4)

    def test_1031_does_not_reuse_the_1033_runner_identity(self):
        fight, retention, _, _ = self.fixture(12)
        phases = []
        effect = dict(FIXTURE["effect411311"], effect_class=1031)
        handler = NativeContainerCleanupHandler(
            retention,
            family=1031,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            event_lifecycle=SimpleNamespace(
                phase=lambda *args, **kwargs: phases.append(
                    kwargs["runner_modifier"].family
                )
            ),
        )
        invocation = handler.prepare(
            effect, {"parameters": []}, EffectInvocation(410219, 1, 7, 7, (0, 0, 0))
        )
        self.assertTrue(handler(effect, {"parameters": []}, invocation))
        self.assertEqual(phases, [1031, 1031, 1031, 1031])

    def test_parameters_and_unqualified_container_types_are_rejected(self):
        fight, retention, packets, _ = self.fixture()
        handler = NativeContainerCleanupHandler(
            retention,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            event_lifecycle=SimpleNamespace(phase=lambda *args, **kwargs: None),
        )
        with self.assertRaisesRegex(ValueError, "no parameters"):
            handler.prepare(
                FIXTURE["effect411311"],
                {"parameters": [1]},
                EffectInvocation(411311, 1, 7, 7, (0, 0, 0)),
            )
        with self.assertRaisesRegex(ValueError, "container contracts"):
            ContainerTypeCleanupAuthority(retention, 7, 25)
        self.assertEqual(packets, [])


if __name__ == "__main__":
    unittest.main()
