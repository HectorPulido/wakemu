"""Owned elemental spell arms the native turret's end-turn nested ability."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerTurretRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerRuntimeTests.fixture
    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_real_fire_spell_arms_and_executes_owned_turret_nested_ability(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        fixture = self.fixture(actives=(6902,))
        born = self.cast(fixture, 7700)
        fixture = self.adopt(fixture, born.fight)
        turret = next(
            a
            for a in born.fight.actors.values()
            if getattr(a, "native_summon_source", None)
        )
        completed = []
        execute = EffectDispatcher.execute
        activation = EffectDispatcher.execute_activation

        def observe(method):
            def run(dispatcher, invocation, *args, **kwargs):
                result = method(dispatcher, invocation, *args, **kwargs)
                if result:
                    completed.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                        )
                    )
                return result

            return run

        with patch.object(EffectDispatcher, "execute", observe(execute)), patch.object(
            EffectDispatcher, "execute_activation", observe(activation)
        ):
            attack = self.cast(
                fixture, 6902, target=fixture[2].actors[-7].position, action_id=3
            )
            fixture = self.next_owned_turn(self.adopt(fixture, attack.fight))
        references = {row[0] for row in completed}
        self.assertTrue({343652, 343653, 343654, 343655} <= references, completed)
        self.assertTrue(references & {343470, 345016}, completed)
        self.assertEqual(fixture[2].actors[turret.id].native_controller_id, 7)
        self.assertNotIn(turret.id, fixture[2].order)
