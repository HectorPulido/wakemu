"""Native faI target ordering reaches damage/healing without new arithmetic."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
import test_combat_damage_handler as damage_fixture
import test_combat_healing_handler as healing_fixture
from wakfu_server.combat_target_ordering import order_native_targets
from wakfu_server.combat_target_health_ordering import NativeHealthOperand
from wakfu_server.fight_checkpoint_store import snapshot

# Exact installed eVn identities: native-health-target-ordering export.
NATIVE = {
    str(ref): dict(
        effect_class=family,
        native_effect_flags=[8, 22],
        maximum_targets=1,
        ordering_contract="faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1",
    )
    for ref, family in [(113941, 5), (117594, 5), (150878, 258), (174852, 258)]
}
LOOKUP = "wakfu_server.combat_target_ordering.native_health_target_ordering"


class HealthOrderingHandlerFlagTests(unittest.TestCase):
    def fixture(self, healing=False, reference=None, flags=(8, 22)):
        fixture = (
            healing_fixture.HealingHandlerTests()
            if healing
            else damage_fixture.DamageHandlerTests()
        )
        fixture.setUp()
        reference = reference or (150878 if healing else 113941)
        effect = dict(
            fixture.effect,
            effect_class=258 if healing else 5,
            native_effect_flags=list(flags),
        )
        invocation = replace(fixture.invocation, reference=reference)
        return fixture, effect, invocation

    def execute(self, healing, reference, flags):
        fixture, effect, invocation = self.fixture(healing, reference, flags)
        with patch(LOOKUP, return_value=NATIVE):
            self.assertTrue(fixture.handler(effect, {}, invocation))
        return snapshot(fixture.fight), fixture.packets

    def test_actual_damage_definitions_preserve_arithmetic_absorption_and_wire(self):
        for reference in (113941, 117594):
            with self.subTest(reference=reference):
                self.assertEqual(
                    self.execute(False, reference, (8, 22)),
                    self.execute(False, reference, (22,)),
                )

    def test_actual_healing_definitions_preserve_hp_virtual_hp_resistance_and_wire(
        self,
    ):
        for reference in (150878, 174852):
            with self.subTest(reference=reference):
                self.assertEqual(
                    self.execute(True, reference, (8, 22)),
                    self.execute(True, reference, (22,)),
                )

    def reject(
        self, healing, metadata, *, reference=None, flags=(8, 22), error="identity"
    ):
        fixture, effect, invocation = self.fixture(healing, reference, flags)
        before = snapshot(fixture.fight)
        with patch(LOOKUP, return_value=metadata), self.assertRaisesRegex(
            ValueError, error
        ):
            fixture.handler(effect, {}, invocation)
        self.assertEqual(snapshot(fixture.fight), before)
        self.assertEqual(fixture.packets, [])

    def test_damage_without_exported_native_identity_rejects_without_mutation(self):
        self.reject(False, {})

    def test_healing_without_exported_native_identity_rejects_without_mutation(self):
        self.reject(True, {})

    def test_damage_conflicting_native_class_flags_and_contract_reject(self):
        for field, value in [
            ("effect_class", 1),
            ("native_effect_flags", [8]),
            ("ordering_contract", "unknown"),
        ]:
            data = deepcopy(NATIVE)
            data["113941"][field] = value
            with self.subTest(field=field):
                self.reject(False, data)

    def test_healing_conflicting_native_class_flags_and_contract_reject(self):
        for field, value in [
            ("effect_class", 25),
            ("native_effect_flags", [8]),
            ("ordering_contract", "unknown"),
        ]:
            data = deepcopy(NATIVE)
            data["150878"][field] = value
            with self.subTest(field=field):
                self.reject(True, data)

    def test_ordering_identity_does_not_authorize_unknown_damage_flag(self):
        data = deepcopy(NATIVE)
        data["113941"]["native_effect_flags"].append(123)
        self.reject(
            False,
            data,
            flags=(8, 22, 123),
            error="Unsupported native damage flags.*123",
        )

    def test_ordering_identity_does_not_authorize_unknown_healing_flag(self):
        data = deepcopy(NATIVE)
        data["150878"]["native_effect_flags"].append(123)
        self.reject(
            True, data, flags=(8, 22, 123), error="Unhandled native healing flags"
        )

    def test_actual_health_ordering_caps_before_damage_reaches_selected_actor(self):
        fixture, effect, invocation = self.fixture()
        caster = fixture.fight.actors[7]
        target = fixture.fight.actors[-7]
        operands = {
            7: NativeHealthOperand(True, 90, 100),
            -7: NativeHealthOperand(True, 10, 100),
        }
        with patch(LOOKUP, return_value=NATIVE):
            ordered = order_native_targets(
                effect,
                invocation,
                (caster, target),
                health_operand=lambda actor: operands[actor.id],
            )
            self.assertEqual(ordered, (target,))
            self.assertTrue(
                fixture.handler(
                    effect, {}, replace(invocation, target_id=ordered[0].id)
                )
            )
        self.assertEqual(caster.hp, 100)
        self.assertLess(target.hp, 100)

    def test_ordering_still_requires_actual_pa_provider_before_handler(self):
        fixture, effect, invocation = self.fixture(True)
        before = snapshot(fixture.fight)
        with patch(LOOKUP, return_value=NATIVE), self.assertRaisesRegex(
            ValueError, "PA provider"
        ):
            order_native_targets(
                effect, invocation, tuple(fixture.fight.actors.values())
            )
        self.assertEqual(snapshot(fixture.fight), before)
        self.assertEqual(fixture.packets, [])
