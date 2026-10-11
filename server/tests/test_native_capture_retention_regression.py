"""Actual factory dispatch with explicit synthetic activation/authority scope."""
import unittest
import struct
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import test_combat_effect_runtime as runtime_fixture
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class CaptureRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_fixture.NativeRuntimeFactoryTests.setUpClass()

    def fixture(self, full=False, retained=False):
        fx = runtime_fixture.NativeRuntimeFactoryTests()
        fx.setUp()
        preview = deepcopy(fx.fight)
        reference = 326383
        original = (
            fx.effects.get(str(reference)) or fx.states["effects"][str(reference)]
        )
        effect = deepcopy(original)
        effect[
            "criteria"
        ] = ""  # Explicit synthetic activation, not original reachable proof.
        roster = OwnedCapturedRoster(7)
        if full:
            roster = OwnedCapturedRoster(
                7,
                tuple(CapturedCreature(i, 1152, "") for i in range(10)),
                selected_slot=9,
            )
        source = SimpleNamespace(
            targeting={"is_eGj": True},
            native_is_ehp=True,
            native_captured_roster=roster,
        )
        target = SimpleNamespace(
            targeting={"is_eGj": True, "dTE": False}, native_actor_type=1, breed_id=1152
        )
        authority = lambda p, a: source if a.id == 7 else target
        authority.property_counts = lambda p, a: {40: 1}
        authority.world_property_counts = lambda p, a: {}
        effects = dict(fx.effects)
        effects[str(reference)] = effect
        states = dict(fx.states)
        states["effects"] = dict(fx.states["effects"])
        states["effects"][str(reference)] = effect
        contexts = replace(
            fx.contexts,
            stat=lambda *args: StatExecutionContext(
                True, True, None, retained, b"", None
            ),
        )
        factory = fx.factory(
            effects=effects,
            states=states,
            contexts=contexts,
            displacement_authority=authority,
        )
        dispatcher, packets = factory(preview, dict(spell_id=7348, evaluation_level=1))
        return (
            preview,
            dispatcher,
            packets,
            EffectInvocation(reference, 1, 7, -7, (1, 0, 0)),
        )

    def test_factory_capture_dispatch_commits_component_and_preserves_actor_hp(self):
        preview, dispatcher, packets, invocation = self.fixture()
        hp = preview.actors[-7].hp
        dispatcher.execute(invocation)
        roster = OwnedCapturedRoster.from_record(
            preview.native_captured_rosters["7"], expected_owner_id=7
        )
        self.assertEqual(roster.selected_creature.profile_id, 1152)
        self.assertEqual(preview.actors[-7].hp, hp)
        deliveries = [payload for opcode, payload in packets if opcode == 12613]
        self.assertEqual(len(deliveries), 1)
        fight_id, action_id, source_id, execute, family, size = struct.unpack(
            ">iiiBih", deliveries[0][:19]
        )
        self.assertEqual(fight_id, preview.id)
        self.assertEqual(source_id, -1)
        self.assertEqual(execute, 1)
        self.assertEqual(family, 320)
        self.assertEqual(size, len(deliveries[0]) - 19)
        self.assertFalse(any(opcode == 13497 for opcode, _ in packets))
        from wakfu_server.combat_effect_removal import _parse_identity_fields

        fields = _parse_identity_fields(deliveries[0][19:])
        self.assertEqual(fields[3], invocation.reference)
        self.assertEqual(fields[6], invocation.caster_id)
        self.assertEqual(fields[7], invocation.target_id & ((1 << 64) - 1))

    def test_factory_retained_capture_observes_owned_payload_without_immediate_execution(
        self,
    ):
        preview, dispatcher, packets, invocation = self.fixture(retained=True)
        hp = preview.actors[invocation.target_id].hp
        dispatcher.execute(invocation)
        roster = OwnedCapturedRoster.from_record(
            preview.native_captured_rosters["7"], expected_owner_id=7
        )
        self.assertEqual(roster.selected_creature.profile_id, 1152)
        self.assertEqual(preview.actors[invocation.target_id].hp, hp)
        deliveries = [payload for opcode, payload in packets if opcode == 13497]
        self.assertEqual(len(deliveries), 1)
        fight_id, action_id, source_id, family, size = struct.unpack(
            ">iiiih", deliveries[0][:18]
        )
        self.assertEqual(fight_id, preview.id)
        self.assertEqual(source_id, -1)
        self.assertEqual(family, 320)
        self.assertEqual(size, len(deliveries[0]) - 18)
        from wakfu_server.combat_effect_removal import _parse_identity_fields

        fields = _parse_identity_fields(deliveries[0][18:])
        self.assertEqual(fields[3], invocation.reference)
        self.assertEqual(fields[6], invocation.caster_id)
        self.assertEqual(fields[7], invocation.target_id & ((1 << 64) - 1))
        self.assertTrue(
            any(
                row.get("effect_class") == 320
                for row in preview.owned_stat_effects.values()
            )
        )
        self.assertFalse(any(opcode == 12613 for opcode, _ in packets))

    def test_factory_full_component_rejection_keeps_target_and_outbox_unchanged(self):
        preview, dispatcher, packets, invocation = self.fixture(full=True)
        hp = preview.actors[-7].hp
        dispatcher.execute(invocation)
        self.assertEqual(preview.actors[-7].hp, hp)
        self.assertFalse(hasattr(preview, "native_captured_rosters"))
        self.assertFalse(packets)


if __name__ == "__main__":
    unittest.main()
