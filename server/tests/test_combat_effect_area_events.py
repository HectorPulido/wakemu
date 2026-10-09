import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime


class AreaEventTests(unittest.TestCase):
    def fixture(self, kind="GLYPH", entry=(10000,), exit=()):
        actors = {
            i: SimpleNamespace(
                id=i, hp=10, position=(0, 0, 3), team=0, physical_radius=0
            )
            for i in (7, 8)
        }
        row = dict(
            uid=901,
            reference=1474,
            owner_id=7,
            level=5,
            cell=(0, 0, 0),
            native_cells_xy=((0, 0),),
            native_area_contract="faY" if kind == "GLYPH" else "faZ",
            remaining_activations=-1,
            child_effect_uids={},
        )
        fight = SimpleNamespace(
            actors=actors,
            native_effect_areas={901: row},
            native_retained_records={},
            phase="active",
            current=actors[8],
        )
        calls = []

        class Retention:
            def synchronize(self):
                pass

            def view(self):
                return None

            def removal(self, view):
                return self

            def remove(self, uids):
                calls.append(("remove", tuple(uids)))
                for uid in uids:
                    fight.native_retained_records.pop(uid)

        dispatcher = SimpleNamespace(
            native_retention=Retention(), execute=lambda inv: calls.append(inv)
        )
        definition = dict(
            properties=(),
            # This fixture models a freshly constructed manager with no faV
            # property bits. The runtime requires the native representation,
            # not the older descriptive `properties` alias.
            native_area_properties=[],
            type=kind,
            effect_ids=(298554,),
            entry_masks=entry,
            exit_masks=exit,
        )
        return (
            NativeAreaEventRuntime(fight, dispatcher, definitions={"1474": definition}),
            row,
            calls,
        )

    def test_native_subscription_does_not_invent_an_external_event_producer(self):
        runtime, row, calls = self.fixture(entry=(10013, 10016))
        self.assertEqual(runtime.created(row), ())
        with self.assertRaisesRegex(ValueError, "event producer"):
            runtime.event(10016, 8)
        self.assertEqual(calls, [])
        self.assertEqual(row["remaining_activations"], -1)

    def test_native_bitset_subscription_rejects_invalid_indices(self):
        for event in (-1, True, "10016", 1 << 31):
            with self.subTest(event=event):
                runtime, row, calls = self.fixture(entry=(event,))
                with self.assertRaisesRegex(ValueError, "BitSet masks"):
                    runtime.created(row)
                self.assertEqual(calls, [])

    def test_creation_does_not_activate_turn_start_glyph(self):
        runtime, row, calls = self.fixture()
        self.assertEqual(runtime.created(row), ())
        self.assertEqual(calls, [])
        runtime.turn_start(8)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].target_id, 8)
        self.assertEqual(calls[0].native_retained_container["id"], 901)
        self.assertFalse(calls[0].native_explicit_target)

    def test_turn_start_rejects_a_noncurrent_fighter_without_mutating(self):
        runtime, row, calls = self.fixture()
        with self.assertRaisesRegex(ValueError, "current active fighter"):
            runtime.turn_start(7)
        self.assertEqual(calls, [])
        self.assertEqual(row["remaining_activations"], -1)

    def test_hour_owner_charge_and_reentrant_gate(self):
        runtime, row, calls = self.fixture("HOUR", (10001,))
        row["remaining_activations"] = 1
        runtime.movement(8, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(row["remaining_activations"], 1)
        runtime.movement(7, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(row["remaining_activations"], 1)
        runtime.movement(7, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(len(calls), 2)
        row["remaining_activations"] = 1
        row["executing"] = True
        runtime.movement(7, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(row["remaining_activations"], 1)

    def test_movement_area_order_uses_actual_qs_registration_history(self):
        from copy import deepcopy
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            register_global_area,
        )

        runtime, template, calls = self.fixture(entry=(10001,))
        runtime.fight.native_effect_areas.clear()
        initialize_global_pv_collections(runtime.fight, (7, 8))
        for identity in (9, 2, -4):
            row = deepcopy(template)
            row["uid"] = identity
            runtime.fight.native_effect_areas[identity] = row
            register_global_area(runtime.fight, identity)
        runtime.movement(8, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(
            [call.native_retained_container["id"] for call in calls], [9, -4, 2]
        )

    def test_movement_freezes_actual_area_objects_before_reactions(self):
        from copy import deepcopy
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            register_global_area,
            unregister_global_area,
        )

        runtime, template, calls = self.fixture(entry=(10001,))
        runtime.fight.native_effect_areas.clear()
        initialize_global_pv_collections(runtime.fight, (7, 8))
        for identity in (9, 2):
            row = deepcopy(template)
            row["uid"] = identity
            runtime.fight.native_effect_areas[identity] = row
            register_global_area(runtime.fight, identity)

        def activate(row, definition, target):
            calls.append(row["uid"])
            if row["uid"] == 9:
                runtime.fight.native_effect_areas.pop(2)
                unregister_global_area(runtime.fight, 2)
            return True

        runtime._activate = activate
        runtime.movement(8, from_cell=(1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(calls, [9, 2])

    def test_movement_destination_uses_actual_actor_footprint(self):
        runtime, row, calls = self.fixture(entry=(10001,))
        runtime.fight.actors[8].physical_radius = 1
        runtime.movement(8, from_cell=(3, 0, 0), to_cell=(1, 0, 0))
        self.assertEqual(len(calls), 1)

    def test_exit_and_removal_use_exact_manager_children(self):
        runtime, row, calls = self.fixture(exit=(10002, 10011))
        row["child_effect_uids"] = {"7": [100], "8": [101]}
        runtime.fight.native_retained_records = {100: {}, 101: {}, 102: {}}
        runtime.movement(8, from_cell=(0, 0, 0), to_cell=(1, 0, 0))
        self.assertEqual(set(runtime.fight.native_retained_records), {100, 102})
        runtime.removed(row)
        self.assertEqual(set(runtime.fight.native_retained_records), {102})
        with self.assertRaisesRegex(ValueError, "Unknown native"):
            runtime.event(2251, 7)

    def test_2251_uses_actual_running_source_only_in_native_channel_one(self):
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        runtime, row, calls = self.fixture("HOUR", (2251,))
        runtime.fight.native_owned_group_effects = {}
        runtime.dispatcher.native_retention.definition = lambda *a: {
            "event_suppresses_level_one": False
        }
        effect = {
            "effect_class": 400,
            "target_masks": [None] * 6 + [[2251]],
            "native_effect_flags": [],
        }
        invocation = EffectInvocation(352198, 1, 7, 901, (0, 0, 0))
        identifiers = {
            "native_container": {"present": False},
            "effect_action_id": 400,
            "zone_trigger_policy": {
                "definition_present": True,
                "zone_flag": False,
                "point_area": True,
            },
        }
        with patch(
            "wakfu_server.combat_trigger_identifiers.source_identifiers",
            return_value=identifiers,
        ):
            runtime.running_source(effect, invocation, uid=999, value=0, channel=2)
            self.assertEqual(calls, [])
            runtime.running_source(effect, invocation, uid=999, value=0, channel=1)
        self.assertEqual(len(calls), 1)
        self.assertEqual((calls[0].caster_id, calls[0].target_id), (7, 7))
        source = calls[0].native_trigger_context
        self.assertEqual(
            (source["uid"], source["generic_effect"], source["target_id"]),
            (999, 352198, 901),
        )

    def test_null_removal_entry_does_not_invent_coordinates_or_owner(self):
        runtime, row, calls = self.fixture("GLYPH", (10011,))
        row["remaining_activations"] = 1
        self.assertEqual(runtime.removed(row), (True,))
        self.assertEqual(row["remaining_activations"], 0)
        self.assertEqual(calls, [])
        runtime, row, calls = self.fixture("HOUR", (10011,))
        row["remaining_activations"] = 1
        self.assertEqual(runtime.removed(row), (False,))
        self.assertEqual(row["remaining_activations"], 1)
        self.assertEqual(calls, [])

    def test_10016_routes_actual_qe_mask_six_and_preserves_trigger_identity(self):
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        runtime, row, calls = self.fixture(entry=(10016,))
        runtime.fight.native_owned_group_effects = {}
        runtime.dispatcher.native_retention.definition = lambda *a: {
            "event_suppresses_level_one": False,
        }
        effect = dict(
            effect_class=400,
            target_masks=[None] * 6 + [[10016]],
            native_effect_flags=[],
        )
        invocation = EffectInvocation(123, 1, 7, 901, (0, 0, 0))
        identifiers = dict(
            native_container={"present": False},
            effect_action_id=400,
            zone_trigger_policy=dict(
                definition_present=True, zone_flag=False, point_area=True
            ),
        )
        self.assertEqual(runtime.created(row), ())
        with patch(
            "wakfu_server.combat_trigger_identifiers.source_identifiers",
            return_value=identifiers,
        ):
            self.assertEqual(
                runtime.running_source(effect, invocation, uid=999, value=0, channel=2),
                (),
            )
            self.assertEqual(
                runtime.running_source(effect, invocation, uid=999, value=0, channel=1),
                (True,),
            )
        self.assertEqual(len(calls), 1)
        source = calls[0].native_trigger_context
        self.assertEqual(
            (
                source["uid"],
                source["generic_effect"],
                source["target_id"],
                source["event_ids"],
            ),
            (999, 123, 901, (10016,)),
        )

    def test_hour_removal_cleans_actual_owner_only(self):
        runtime, row, calls = self.fixture("HOUR", (), (10011,))
        row["child_effect_uids"] = {"7": [100], "8": [101]}
        runtime.fight.native_retained_records = {100: {}, 101: {}}
        runtime.removed(row)
        self.assertEqual(set(runtime.fight.native_retained_records), {101})

    def test_native_not_activated_by_allies_preserves_charge(self):
        runtime, row, calls = self.fixture()
        runtime.definitions["1474"]["native_area_properties"] = [1]
        row.update(
            native_fight_affiliation=0, native_fight_affiliation_source="faV.j(PV).bcM"
        )
        runtime.fight.actors[8].native_is_amO = True
        runtime.fight.actors[8].native_fight_affiliation = 0
        row["remaining_activations"] = 1
        runtime.turn_start(8)
        self.assertEqual(calls, [])
        self.assertEqual(row["remaining_activations"], 1)
