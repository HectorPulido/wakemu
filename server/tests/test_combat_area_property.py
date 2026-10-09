import unittest
from types import SimpleNamespace
from itertools import count
from unittest.mock import patch
from wakfu_server.combat_area_property import (
    NativeAreaPropertyHandler,
    area_properties,
    remove_area_property,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class NativeAreaPropertyTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(uid=91, reference=111, native_area_contract="faY")
        self.fight = SimpleNamespace(
            id=77,
            actors={7: SimpleNamespace(id=7)},
            native_effect_areas={91: self.row},
            native_retired_area_managers={},
            owned_stat_effects={},
        )
        self.packets = []
        ids = count(901)
        self.handler = NativeAreaPropertyHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=lambda: next(ids),
            context=lambda *_: StatExecutionContext(True, True, None, True, None),
        )
        self.definition = dict(native_area_properties=[1])
        self.catalog = patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"111": self.definition},
        )
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def apply(self, prop, target=91):
        return self.handler(
            dict(effect_class=451),
            dict(parameters=(prop,)),
            EffectInvocation(101, 1, 7, target, (0, 0, 0)),
        )

    def test_fighter_null_invalid_enum_are_native_noop(self):
        for prop, target in ((10, 7), (10, None), (-1, 91), (15, 91)):
            self.assertFalse(self.apply(prop, target))
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertNotIn("native_current_area_properties", self.row)

    def test_duplicate_application_is_set_not_property_counter(self):
        self.assertTrue(self.apply(10))
        self.assertTrue(self.apply(10))
        self.assertEqual(area_properties(self.row, self.definition), {1, 10})
        remove_area_property(self.handler, 901)
        self.assertEqual(area_properties(self.row, self.definition), {1})
        self.assertIn(902, self.fight.owned_stat_effects)
        remove_area_property(self.handler, 902)
        self.assertEqual(area_properties(self.row, self.definition), {1})
        self.assertEqual([p for p, _ in self.packets], [12613, 12613, 13560, 13560])
        self.assertEqual([body[12] for _, body in self.packets[:2]], [0, 0])

    def test_immediate_property_executes_without_retained_record(self):
        self.handler.context = lambda *_: StatExecutionContext(
            True, True, None, False, None
        )
        self.assertTrue(self.apply(10))
        self.assertEqual(area_properties(self.row, self.definition), {1, 10})
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual(self.packets[0][0], 12613)
        self.assertEqual(self.packets[0][1][12], 1)

    def test_removal_clears_preexisting_property_without_restoring_base(self):
        self.assertTrue(self.apply(1))
        remove_area_property(self.handler, 901)
        self.assertEqual(area_properties(self.row, self.definition), set())
        self.assertEqual(self.definition["native_area_properties"], [1])

    def test_retired_actual_area_remains_exact_property_target(self):
        self.apply(10)
        self.fight.native_retired_area_managers[
            91
        ] = self.fight.native_effect_areas.pop(91)
        remove_area_property(self.handler, 901)
        self.assertEqual(area_properties(self.row, self.definition), {1})

    def test_dynamic_manager_lifecycle_is_explicitly_guarded(self):
        with self.assertRaisesRegex(ValueError, "manager authority"):
            self.apply(12)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_prepared_lifecycle_exposes_inherited_property_amount_after_calculation(
        self,
    ):
        from unittest.mock import Mock

        lifecycle = Mock()
        self.handler.event_lifecycle = lifecycle
        effect = dict(effect_class=451, target_masks=[[], [], [], [], [], [], [123]])
        invocation = EffectInvocation(101, 1, 7, 91, (0, 0, 0))
        invocation = self.handler.prepare(effect, dict(parameters=(10,)), invocation)
        self.assertTrue(self.handler(effect, dict(parameters=(10,)), invocation))
        phases = lifecycle.phase.call_args_list
        self.assertEqual([call.kwargs["channel"] for call in phases], [1, 2, 3, 4])
        self.assertEqual([call.kwargs["value"] for call in phases], [0, 10, 10, 10])
        self.assertEqual(area_properties(self.row, self.definition), {1, 10})
        lifecycle.register_applied.assert_called_once_with(effect, invocation, 901)
        self.assertEqual(self.handler.prepared, {})
        self.assertEqual(self.handler.runners, {})

    def test_wall_visibility_reads_current_property_set_through_native_qi_h(self):
        from wakfu_server.combat_wall_area import wall_constructor
        from wakfu_server.combat_casting_los import native_area_visibility, native_qi_h
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot

        self.definition.update(
            type="WALL",
            native_class="bcZ",
            native_type_id=7,
            native_container_type=3,
            raw_bdh=[100, 0, 0, 1],
        )
        constructor = wall_constructor(self.definition, 1)
        self.row.update(
            native_area_contract="fbd",
            native_type_id=7,
            level=1,
            native_running_effect_manager=True,
            native_wall_constructor=constructor,
            native_wall_hp_current=100,
            native_wall_hp_source="fbd.PA.sgC.aYS",
            native_obstacle_id=2,
            native_obstacle_source="QI.f(QK)",
        )
        terrain = NativeQISnapshot(dict(x=0, y=0, width=1, height=1, cell_masks=[0]))

        def blocked():
            return native_qi_h(
                terrain,
                0,
                0,
                0,
                ordered_slots=lambda *_: [2],
                visibility=lambda _: native_area_visibility(self.fight, 91),
                ignored=set(),
            )

        self.assertTrue(blocked())
        self.apply(10)
        self.assertFalse(blocked())
        remove_area_property(self.handler, 901)
        self.assertTrue(blocked())
