import unittest
from types import SimpleNamespace
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_effect_area_queries import area_type_count, actor_on_area_type


class AreaTypeConditionsTests(unittest.TestCase):
    def fixture(self):
        return SimpleNamespace(
            actors={
                7: SimpleNamespace(position=(0, 0, 0)),
                8: SimpleNamespace(position=(2, 0, 0)),
            },
            native_effect_areas={
                uid: dict(
                    uid=uid,
                    reference=1546,
                    owner_id=owner,
                    cell=(x, 0, 9),
                    native_cells_xy=((x, 0),),
                    native_type_id=kind,
                    native_area_contract="faZ",
                )
                for uid, x, kind, owner in (
                    (901, 0, 1, 7),
                    (902, 2, 1, 8),
                    (903, 4, 2, 7),
                )
            },
        )

    def test_callbacks_use_correct_native_signatures(self):
        seen = []
        context = ConditionContext(
            {},
            actor_area_type_query=lambda *a: seen.append(a) or True,
            area_type_range_query=lambda *a: seen.append(a) or 2,
        )
        self.assertTrue(
            evaluate_condition('IsOnEffectAreaType("TaRgEt",1,True)', context)
        )
        self.assertTrue(
            evaluate_condition(
                'GetEffectAreaCountInRange("target",1,0,2,True)==2', context
            )
        )
        self.assertEqual(seen, [("TaRgEt", 1, True), ("target", 1, 0, 2, True)])
        with self.assertRaises(UnknownCondition):
            evaluate_condition('IsOnEffectAreaType("caster",1)', ConditionContext({}))

    def test_native_type_range_and_selected_actor_ownership(self):
        fight = self.fixture()
        self.assertEqual(
            area_type_count(
                fight, source_id=7, center=(0, 0, 0), area_type=1, minimum=0, maximum=2
            ),
            2,
        )
        self.assertEqual(
            area_type_count(
                fight,
                source_id=7,
                center=(0, 0, 0),
                area_type=1,
                minimum=99,
                maximum=-1,
            ),
            2,
        )
        self.assertEqual(
            area_type_count(
                fight,
                source_id=7,
                center=(0, 0, 0),
                area_type=1,
                minimum=0,
                maximum=2,
                owned=True,
            ),
            1,
        )
        self.assertTrue(actor_on_area_type(fight, actor_id=8, area_type=1, owned=True))
        self.assertFalse(actor_on_area_type(fight, actor_id=None, area_type=1))
        self.assertFalse(actor_on_area_type(fight, actor_id=8, area_type=999))
