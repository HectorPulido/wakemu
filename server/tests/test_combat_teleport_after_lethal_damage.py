"""Teleport corpse eligibility precedes native C/prepare calculation."""
import unittest
from unittest.mock import Mock


class TeleportAfterLethalDamageTests(unittest.TestCase):
    def fixture(self):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_active_spell_id = 5947
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        return fixture, handler

    def dispatcher(self, handler, effect):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        prepared = Mock(side_effect=RuntimeError("prepared-live-teleport"))
        dispatcher = EffectDispatcher(
            {"282929": effect},
            {effect["effect_class"]: handler},
            resolve=lambda effect, invocation: (invocation,),
            condition_context=lambda invocation: None,
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda *args: (0, 0, 0),
            prepare_effect=prepared,
        )
        return dispatcher, prepared

    def effect(self, family=340):
        # Actual5947 child282929/282933 has no parameters/masks and flag17.
        return dict(
            effect_class=family,
            native_effect_flags=[17],
            target_masks=[None] * 7,
            parameters=[],
            parameter_count=0,
            minimum_level=0,
            maximum_level=32767,
            children=[],
            probability_base=100,
            probability_per_level=0,
            criteria="",
        )

    def test_actual_lethal_damage_skips_teleport_before_prepare(self):
        from dataclasses import replace

        for family in (340, 302):
            fixture, handler = self.fixture()
            dispatcher, prepared = self.dispatcher(handler, self.effect(family))
            with fixture.fight.effect_resolution():
                fixture.fight.apply_effect_damage(7, -7, 100)
                self.assertFalse(
                    dispatcher.execute(
                        replace(
                            fixture.invocation,
                            reference=282929,
                        )
                    )
                )
            prepared.assert_not_called()

    def test_living_target_reaches_existing_prepare(self):
        from dataclasses import replace

        fixture, handler = self.fixture()
        dispatcher, prepared = self.dispatcher(handler, self.effect())
        with self.assertRaisesRegex(RuntimeError, "prepared-live-teleport"):
            dispatcher.execute(replace(fixture.invocation, reference=282929))
        prepared.assert_called_once()

    def test_unknown_corpse_policy_fails_closed_before_prepare(self):
        from dataclasses import replace

        fixture, handler = self.fixture()
        effect = self.effect()
        del effect["native_effect_flags"]
        dispatcher, prepared = self.dispatcher(handler, effect)
        with fixture.fight.effect_resolution():
            fixture.fight.apply_effect_damage(7, -7, 100)
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                dispatcher.execute(replace(fixture.invocation, reference=282929))
        prepared.assert_not_called()
