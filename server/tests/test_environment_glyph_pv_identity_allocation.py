"""Initial scene PV identities remain reserved after their Qq disappears."""
from copy import deepcopy
from types import MethodType
import unittest

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_environment_glyphs import (
    SOURCE,
    ensure_environment_glyphs,
    environment_sections,
)
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import StateLedger


class EnvironmentGlyphPVIdentityAllocationTests(unittest.TestCase):
    def fixture(self, uid):
        fight, handler, _, packets = area_fixture.NativeFakeFighterAreaTests().create()
        fight.actors[7].state_ledger = StateLedger(7)
        fight.actors[7].physical_radius = 0
        for name in (
            "owned_stat_effects",
            "state_wire_payloads",
            "native_owned_group_effects",
            "native_owned_area_effects",
            "native_owned_spatial_effects",
            "native_retired_area_managers",
        ):
            setattr(fight, name, {})
        fight.walkable = {(x, y, 0) for x in range(4) for y in range(4)}
        fight.native_effect_uid_next = uid
        fight.native_environment_glyph_constructors = [
            dict(
                uid=uid,
                reference=2066,
                cell=(1, 1, 0),
                level=0,
                policy="wakemu.test.initial-scene.v1",
                source=SOURCE,
                authority="test.original-neutral-point-constructor",
            )
        ]
        fight.native_environment_glyphs_installed = True
        fight.allocate_effect_uid = MethodType(Fight.allocate_effect_uid, fight)
        fight.allocate_area_uid = MethodType(Fight.allocate_area_uid, fight)
        handler.allocate_uid = fight.allocate_effect_uid
        handler.allocate_area_uid = fight.allocate_area_uid
        return fight, handler, packets

    def create_actual_area(self, handler):
        return handler(
            {"effect_class": 339},
            {"parameters": [1035]},
            EffectInvocation(400, 1, 7, None, (2, 3, 0)),
        )

    def test_removed_initial_glyph_and_border_do_not_alias_new_area_or_reappear(self):
        fight, handler, _ = self.fixture(8991)
        fight.native_border_constructor = dict(identity=8992)
        original_source = deepcopy(fight.native_environment_glyph_constructors)
        self.assertTrue(self.create_actual_area(handler))
        self.assertEqual(tuple(fight.native_effect_areas), (8993,))
        self.assertEqual(fight.native_effect_areas[8993]["native_area_contract"], "faW")
        # This is the same ensure entry used by nested summon initialization.
        ensure_environment_glyphs(fight)
        self.assertEqual(environment_sections(fight), [])
        self.assertEqual(tuple(fight.native_effect_areas), (8993,))
        self.assertEqual(fight.native_environment_glyph_constructors, original_source)
        self.assertEqual(fight.native_effect_uid_next, 8995)

    def test_preview_keeps_running_namespace_and_original_constructor_guard_strict(
        self,
    ):
        fight, _, packets = self.fixture(8991)
        # Qe identities remain separate: a runner may have this numeric ID.
        self.assertEqual(fight.allocate_effect_uid(), 8991)
        self.assertEqual(fight.native_effect_uid_next, 8992)
        preview = deepcopy(fight)
        preview.native_effect_uid_next = 8991
        preview.allocate_effect_uid = MethodType(Fight.allocate_effect_uid, preview)
        preview.allocate_area_uid = MethodType(Fight.allocate_area_uid, preview)
        self.assertEqual(preview.allocate_area_uid(), 8992)
        self.assertEqual(fight.native_effect_uid_next, 8992)
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(packets, [])
        # Reserving old PVs does not make a forged replacement legitimate.
        preview.native_effect_areas[8991] = dict(
            uid=8991,
            reference=2078,
            cell=(-1, -12, 0),
            level=2,
            owner_id=-200,
            direction=3,
            native_area_contract="faN",
        )
        with self.assertRaisesRegex(ValueError, "faY constructor authority"):
            ensure_environment_glyphs(preview)
        self.assertEqual(fight.native_effect_areas, {})
