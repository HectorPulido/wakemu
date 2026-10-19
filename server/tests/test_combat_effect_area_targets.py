import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_effect_area_targets import area_targets, area_target_context
from wakfu_server.combat_effect_targets import select_native_effect_targets


class NativeAreaTargetTests(unittest.TestCase):
    def test_native_bcR_prototype_is_required_and_preserved_for_active_areas(self):
        from wakfu_server.combat_effect_area_targets import native_area_targeting_bcR

        row = dict(reference=314, native_area_contract="faY")
        for raw_bcr in (True, False):
            with patch(
                "wakfu_server.combat_effect_area.native_effect_areas",
                return_value={"314": {"type": "GLYPH", "raw_bcR": raw_bcr}},
            ):
                self.assertIs(native_area_targeting_bcR(row), raw_bcr)

        for definition, contract in (
            ({"type": "GLYPH"}, "faY"),
            ({"type": "GLYPH", "raw_bcR": 1}, "faY"),
            ({"type": "GLYPH", "raw_bcR": False}, "faN"),
        ):
            with self.subTest(definition=definition, contract=contract):
                with patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={"314": definition},
                ):
                    with self.assertRaisesRegex(ValueError, "bcR"):
                        native_area_targeting_bcR(
                            dict(reference=314, native_area_contract=contract)
                        )

    def test_area64_selector_observes_native_bcR_true_and_false(self):
        caster = SimpleNamespace(id=7, position=(0, 0, 0), team=0, direction=0)
        fight = SimpleNamespace(
            actors={7: caster},
            native_effect_areas={
                901: dict(
                    uid=901,
                    reference=314,
                    level=1,
                    cell=(1, 0, 0),
                    owner_id=7,
                    direction=0,
                    native_hour_contract=True,
                    native_area_contract="faY",
                    native_qq_bhi=False,
                    native_qq_guard_source="Qq.constructor",
                )
            },
        )
        selector = dict(native_target_selector=dict(**{"class": "fcE"}, mask=1 << 43))
        for raw_bcr, expected in ((True, (901,)), (False, ())):
            with self.subTest(raw_bcR=raw_bcr):
                with patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={"314": {"type": "GLYPH", "raw_bcR": raw_bcr}},
                ):
                    area = area_targets(fight)[0]
                    context = {
                        7: dict(is_eGj=True, is_Qq=False, bEe=True, is_eHH=True),
                        901: area_target_context(area),
                    }
                    result = select_native_effect_targets(
                        selector, caster, (1, 0, 0), [area], native_context=context
                    )
                self.assertEqual(tuple(actor.id for actor in result), expected)

    def test_unknown_native_bcR_area_target_fails_closed(self):
        from wakfu_server.combat_effect_area_targets import NativeAreaTarget

        area = NativeAreaTarget(901, (1, 0, 0), 0, 7)
        with self.assertRaisesRegex(ValueError, "bcR"):
            area_target_context(area)

    def test_fcE_owned_Qq_bit43_without_fabricated_actor_resources(self):
        caster = SimpleNamespace(id=7, position=(0, 0, 0), team=0, direction=0)
        fight = SimpleNamespace(
            actors={7: caster},
            native_effect_areas={
                901: dict(
                    uid=901,
                    reference=1551,
                    level=1,
                    cell=(2, 0, 0),
                    owner_id=7,
                    direction=0,
                    native_hour_contract=True,
                    native_area_contract="faY",
                    native_qq_bhi=False,
                    native_qq_guard_source="Qq.constructor",
                )
            },
        )
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"1551": {"type": "GLYPH", "raw_bcR": False}},
        ):
            area = area_targets(fight)[0]
        self.assertFalse(hasattr(area, "hp"))
        effect = dict(
            area_class="anH",
            area_native="ring-1-6",
            native_target_selector=dict(
                **{"class": "fcE"}, mask=(1 << 43) | (1 << 51) | 1
            ),
        )
        contexts = {
            7: dict(is_eGj=True, is_Qq=False, bEe=True, is_eHH=True),
            901: area_target_context(area),
        }
        result = select_native_effect_targets(
            effect, caster, (0, 0, 0), [area], native_context=contexts
        )
        self.assertEqual(tuple(a.id for a in result), (901,))
        contexts[901]["q_owner_id"] = 8
        self.assertEqual(
            select_native_effect_targets(
                effect, caster, (0, 0, 0), [area], native_context=contexts
            ),
            (),
        )

    def test_unknown_area_owner_is_not_assumed(self):
        fight = SimpleNamespace(
            actors={},
            native_effect_areas={
                901: dict(
                    uid=901,
                    reference=1551,
                    cell=(2, 0, 0),
                    owner_id=7,
                    direction=0,
                    native_hour_contract=True,
                    native_area_contract="faY",
                    native_qq_bhi=False,
                    native_qq_guard_source="Qq.constructor",
                )
            },
        )
        with self.assertRaises(ValueError):
            area_targets(fight)
