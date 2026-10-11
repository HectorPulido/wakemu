"""Advanced Mechanics excludes actual state-container indirect damage."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_special_passives_runtime as qualified


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerIndirectGuardRuntimeTests(unittest.TestCase):
    def test_advanced_mechanics_does_not_modify_actual_indirect_state_damage(self):
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        instance = qualified.SteamerSpecialPassivesRuntimeTests()
        fixture = instance.fixture
        instance.fixture = lambda passives=(), **kwargs: fixture(
            tuple(passives) + (6943,), **kwargs
        )
        execute, calculate = EffectDispatcher.execute, NativeDamageHandler._calculate
        stack, calculations, modifiers = [], [], []

        def observe_execute(dispatcher, invocation, **kwargs):
            stack.append((invocation.reference, invocation.caster_id))
            try:
                result = execute(dispatcher, invocation, **kwargs)
                if invocation.reference == 344029:
                    modifiers.append((tuple(stack), result))
                return result
            finally:
                stack.pop()

        def observe_calculate(handler, effect, invocation, **kwargs):
            result = calculate(handler, effect, invocation, **kwargs)
            if result[1] is not None:
                calculations.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        result[1]["indirect"],
                        result[2],
                    )
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe_execute), patch.object(
            NativeDamageHandler, "_calculate", observe_calculate
        ):
            instance.test_water_turret_specialization_selects_actual_half_damage_state()
        indirect = {
            ref
            for ref, caster, flag, amount in calculations
            if caster == 7 and flag and amount is not None and amount > 0
        }
        self.assertTrue(indirect, calculations)
        unexpected = [
            (path, result)
            for path, result in modifiers
            if result and any(ref in indirect and caster == 7 for ref, caster in path)
        ]
        self.assertFalse(
            unexpected, dict(indirect=sorted(indirect), modifiers=modifiers)
        )
