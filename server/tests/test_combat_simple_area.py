import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from wakfu_server.combat_effect_area import NativeEffectAreaHandler
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area_queries import cell_contains_type
from wakfu_server.combat_effect_area_targets import area_target_context, area_targets
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_managers import state_manager
from wakfu_server.combat_stat_handler import StatExecutionContext


def simple_definition(reference, *, area_type="SIMPLE", native_class="bcW", type_id=6):
    return dict(
        reference=reference,
        type=area_type,
        native_class=native_class,
        native_type_id=type_id,
        native_container_type=3,
        raw_bde=2,
        raw_bcR=False,
        properties=[],
        native_fight_properties=[],
        native_area_properties=[],
        effect_ids=[408816],
        entry_masks=[10001],
        exit_masks=[10011],
        native_shape_class="anD",
        native_shape_description="point",
        native_hour_contract=False,
    )


class SimpleEffectAreaTests(unittest.TestCase):
    def create_area(self, reference=314, definition=None):
        actors = {
            actor_id: NS(
                id=actor_id,
                position=(2, 3, 0),
                direction=2,
                team=0 if actor_id == 7 else 1,
            )
            for actor_id in (7, 8)
        }
        fight = NS(id=77, actors=actors, native_effect_areas={})
        packets = []
        uid_calls = []
        area_uid_calls = []
        definition = simple_definition(reference) if definition is None else definition
        dispatcher = NS(
            native_retention=NS(synchronize=Mock()),
            execute=Mock(),
            native_retained_records={},
        )
        fight.native_retained_records = dispatcher.native_retained_records
        runtime = NativeAreaEventRuntime(
            fight, dispatcher, definitions={str(reference): definition}
        )
        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: uid_calls.append(71) or 71,
            allocate_area_uid=lambda: area_uid_calls.append(901) or 901,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, native_time_payload(), None
            ),
            container=lambda invocation: (dict(container_type=3), 701),
        )
        handler.on_created = runtime.created
        owner_catalog = {"effects": {"315": dict(runner="eYQ", bbA=True, bbB=True)}}
        with patch(
            "wakfu_server.combat_delivery_owners.owner_catalog",
            return_value=owner_catalog,
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={str(reference): definition},
        ), patch(
            "wakfu_server.combat_effect_area_geometry.registered_area_cells",
            return_value=((2, 3),),
        ):
            result = handler(
                {"effect_class": 315},
                {"parameters": [reference, 4]},
                EffectInvocation(500, 4, 7, None, (2, 3, 0)),
            )
        self.assertTrue(result)
        return (
            fight,
            packets,
            uid_calls,
            area_uid_calls,
            dispatcher,
            runtime,
            definition,
        )

    def test_creation_uses_generic_simple_contract_for_314_and_other_reference(self):
        for reference in (314, 8192):
            with self.subTest(reference=reference):
                (
                    fight,
                    packets,
                    uid_calls,
                    area_uid_calls,
                    dispatcher,
                    runtime,
                    definition,
                ) = self.create_area(reference)
                row = fight.native_effect_areas[901]
                self.assertEqual(row["native_area_contract"], "fbb")
                self.assertEqual(row["native_type_id"], 6)
                self.assertEqual(
                    row["native_simple_constructor"],
                    dict(
                        source="bcW.fbb.Qr.constructor.type6",
                        owner_activation=True,
                        other_activation=False,
                        activation_coordinates=None,
                        obstacle=False,
                        movement_blocking=False,
                        bcK_value=6,
                    ),
                )
                self.assertNotIn("state_ledger", row)
                self.assertEqual((uid_calls, area_uid_calls), ([71], [901]))
                self.assertEqual(len(packets), 1)
                with patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={str(reference): definition},
                ):
                    self.assertIsNone(state_manager(fight, 901))
                dispatcher.execute.assert_not_called()

    def test_invalid_simple_type_class_or_type_id_fails_before_uid_allocation(self):
        for changes in (
            {"type": "UNKNOWN"},
            {"native_class": "not-bcW"},
            {"native_type_id": 5},
        ):
            with self.subTest(changes=changes):
                reference = 314
                definition = simple_definition(reference)
                definition.update(changes)
                actors = {7: NS(id=7, position=(2, 3, 0), direction=2, team=0)}
                fight = NS(id=77, actors=actors, native_effect_areas={})
                uid_calls = []
                area_uid_calls = []
                handler = NativeEffectAreaHandler(
                    fight,
                    [],
                    action_id=1,
                    allocate_uid=lambda: uid_calls.append(71) or 71,
                    allocate_area_uid=lambda: area_uid_calls.append(901) or 901,
                    context=lambda *args: StatExecutionContext(
                        True, True, None, True, native_time_payload(), None
                    ),
                    container=lambda invocation: (dict(container_type=3), 701),
                )
                handler.on_created = lambda row: None
                with patch(
                    "wakfu_server.combat_delivery_owners.owner_catalog",
                    return_value={
                        "effects": {"315": dict(runner="eYQ", bbA=True, bbB=True)}
                    },
                ), patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={str(reference): definition},
                ):
                    with self.assertRaises(ValueError):
                        handler(
                            {"effect_class": 315},
                            {"parameters": [reference, 4]},
                            EffectInvocation(500, 4, 7, None, (2, 3, 0)),
                        )
                self.assertEqual(uid_calls, [])
                self.assertEqual(area_uid_calls, [])
                self.assertEqual(fight.native_effect_areas, {})

    def test_owner_activation_consumes_charge_but_other_and_null_do_not_execute(self):
        fight, _, _, _, dispatcher, runtime, definition = self.create_area()
        row = fight.native_effect_areas[901]
        row["remaining_activations"] = 2
        self.assertFalse(runtime._activate(row, definition, fight.actors[8]))
        self.assertEqual(row["remaining_activations"], 2)
        self.assertFalse(runtime._activate(row, definition, None))
        self.assertEqual(row["remaining_activations"], 2)
        self.assertTrue(runtime._activate(row, definition, fight.actors[7]))
        self.assertEqual(row["remaining_activations"], 1)
        dispatcher.execute.assert_not_called()

    def test_removed_callback_cleans_only_the_actual_exit_recipient(self):
        fight, _, _, _, dispatcher, runtime, definition = self.create_area()
        row = fight.native_effect_areas[901]
        row["child_effect_uids"] = {"7": [101, 102], "8": [103]}
        dispatcher.native_retained_records.update({101: {}, 102: {}, 103: {}})
        removed = []

        class Retention:
            def synchronize(self):
                pass

            def view(self):
                return object()

            def removal(self, view):
                class Plan:
                    def remove(inner_self, uids):
                        removed.append(tuple(uids))
                        for uid in uids:
                            dispatcher.native_retained_records.pop(uid)

                return Plan()

        dispatcher.native_retention = Retention()
        self.assertEqual(runtime.removed(row, target_id=8), (True,))
        self.assertEqual(removed, [(103,)])
        self.assertEqual(set(dispatcher.native_retained_records), {101, 102})
        self.assertEqual(row["child_effect_uids"], {"7": [101, 102]})

    def test_spatial_query_targets_and_removal_keep_simple_area_nonphysical(self):
        fight, _, _, _, _, runtime, definition = self.create_area()
        row = fight.native_effect_areas[901]
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={"314": definition},
        ):
            self.assertTrue(
                cell_contains_type(
                    fight, cell=(2, 3, 50), area_type=6, source_id=7, owned=True
                )
            )
            (target,) = area_targets(fight)
            context = area_target_context(target)
        self.assertEqual(target.native_los_height, 6)
        self.assertFalse(target.native_is_obstacle)
        self.assertFalse(target.native_movement_blocking)
        self.assertFalse(context["bcO"])
        self.assertFalse(context["bcP"])
        self.assertFalse(hasattr(target, "hp"))
        self.assertTrue(runtime.remove_parent(row))
        self.assertNotIn(901, fight.native_effect_areas)
        self.assertFalse(
            cell_contains_type(
                fight, cell=(2, 3, 0), area_type=6, source_id=7, owned=True
            )
        )


if __name__ == "__main__":
    unittest.main()
