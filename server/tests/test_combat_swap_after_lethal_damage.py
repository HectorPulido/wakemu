"""An owned lethal child must not turn a subsequent native swap into an error."""
import unittest
from unittest.mock import patch


class SwapAfterLethalDamageTests(unittest.TestCase):
    def test_mento_swap_child_skips_actual_off_play_target(self):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_active_spell_id = 4638
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        # Exact native eligibility operands of 4638 child144115/146892.
        effect = dict(
            effect_class=422,
            native_effect_flags=[17],
            target_masks=(None,) * 7,
        )
        before = {identity: actor.position for identity, actor in fight.actors.items()}
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 100)
            with patch.object(
                handler,
                "prepare",
                side_effect=AssertionError("Rejected swap must not prepare"),
            ):
                self.assertFalse(handler(effect, {}, fixture.invocation))
        self.assertEqual(
            {identity: actor.position for identity, actor in fight.actors.items()},
            before,
        )

    def test_unknown_corpse_bypass_operands_still_fail_closed(self):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_active_spell_id = 4638
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 100)
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                handler(
                    dict(effect_class=422, native_effect_flags=[17]),
                    {},
                    fixture.invocation,
                )
