import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area_targets import area_targets, area_target_context
from wakfu_server.combat_effect_targets import select_native_effect_targets


class NativeAreaTargetTests(unittest.TestCase):
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
                )
            },
        )
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
                )
            },
        )
        with self.assertRaises(ValueError):
            area_targets(fight)
