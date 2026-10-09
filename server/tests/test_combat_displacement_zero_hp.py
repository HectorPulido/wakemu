"""Native fax participation is independent of an unsettled complete HP operand."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from wakfu_server.combat_hp_raw import (
    SOURCE,
    install_fresh_hp_operand,
    set_hp_raw_current,
)
from wakfu_server.combat_displacement import NativeDisplacementHandler


class ZeroHPDisplacementAuthorityTests(unittest.TestCase):
    def test_off_play_recipient_skips_before_displacement_phases(self):
        from test_combat_damage_handler import DamageHandlerTests
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fixture = DamageHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_active_spell_id = 7076
        handler = object.__new__(NativeDisplacementHandler)
        handler.fight = fight
        # The actual damage operation registers OFF_PLAY; no scalar HP edit.
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 100)
            for family in (300, 301):
                effect = dict(
                    effect_class=family,
                    native_effect_flags=[],
                    target_masks=(None,) * 7,
                )
                with patch.object(
                    handler,
                    "prepare",
                    side_effect=AssertionError("Skipped runner prepared"),
                ):
                    self.assertFalse(handler(effect, {}, fixture.invocation))
            with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
                handler(
                    dict(effect_class=300, native_effect_flags=[]),
                    {},
                    fixture.invocation,
                )

    def fixture(self):
        actor = SimpleNamespace(
            id=7,
            hp=20,
            physical_radius=0,
            effect_stats={1: 20},
            effect_minima={1: 0},
            effect_maxima={1: 20},
            effect_frozen=frozenset(),
        )
        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=7, raw_current=20)
        )
        metadata = SimpleNamespace(
            targeting=dict(baF=True, baG=False, baK=False),
            is_carried=False,
            is_carrying=False,
        )

        class Authority:
            def __call__(self, fight, selected):
                if selected is not actor:
                    raise ValueError("Wrong actual actor")
                return metadata

            def properties(self, fight, selected):
                return frozenset()

        handler = object.__new__(NativeDisplacementHandler)
        handler.authority, handler.fight = Authority(), SimpleNamespace(
            actors={7: actor}
        )
        return handler, actor, metadata

    def test_complete_setter_zero_and_in_play_authority_are_admissible(self):
        handler, actor, _ = self.fixture()
        set_hp_raw_current(actor, 0)
        self.assertEqual(handler._ordinary(actor), frozenset())

    def test_raw_hp_mutation_or_off_play_cannot_bypass_life_guard(self):
        handler, actor, metadata = self.fixture()
        actor.hp = actor.effect_stats[1] = 0
        with self.assertRaises(ValueError):
            handler._ordinary(actor)
        actor.hp = actor.effect_stats[1] = 20
        set_hp_raw_current(actor, 0)
        metadata.targeting = dict(baF=False, baG=True, baK=False)
        with self.assertRaisesRegex(ValueError, "living ordinary"):
            handler._ordinary(actor)

    def test_actual_carry_and_radius_guards_remain(self):
        for field, value in [
            ("is_carrying", True),
            ("is_carrying", None),
            ("is_carried", True),
        ]:
            handler, actor, metadata = self.fixture()
            set_hp_raw_current(actor, 0)
            setattr(metadata, field, value)
            with self.assertRaisesRegex(ValueError, "empty carry relations"):
                handler._ordinary(actor)
        handler, actor, _ = self.fixture()
        actor.physical_radius = 1
        with self.assertRaisesRegex(ValueError, "radius0"):
            handler._ordinary(actor)
