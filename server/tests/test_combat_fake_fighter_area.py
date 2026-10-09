import unittest
import struct
from types import SimpleNamespace

from wakfu_server.combat_effect_area import (
    NativeEffectAreaHandler,
    native_effect_areas,
    remove_owned_hour_area,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area_targets import area_targets, area_target_context
from wakfu_server.combat_fake_fighter import fake_fighter_constructor
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_state_managers import registered_area_pv, state_manager
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state_ledger import StateLedger


class NativeFakeFighterAreaTests(unittest.TestCase):
    def definition(self, **changes):
        result = dict(
            type="FAKE_FIGHTER",
            native_type_id=15,
            native_class="bcQ",
            raw_bdh=[-1, -1, 0, 0, 1, 1, 1, 1, 6, -1],
        )
        result.update(changes)
        return result

    def test_absent_characteristics_and_independent_qf(self):
        constructor = fake_fighter_constructor(self.definition())
        self.assertEqual(constructor["characteristic_ids"], ())
        self.assertTrue(constructor["running_effect_manager"])
        self.assertFalse(constructor["movement_blocking"])
        self.assertTrue(constructor["obstacle"])

    def test_optional_characteristics_require_their_actual_producer(self):
        for index, value in ((1, 10), (9, 0)):
            definition = self.definition()
            definition["raw_bdh"][index] = value
            with self.assertRaisesRegex(ValueError, "characteristic"):
                fake_fighter_constructor(definition)

    def test_constructor_uses_exact_flags_signed_height_and_round(self):
        definition = self.definition()
        definition["raw_bdh"] = [-1.5, -1, 0, 2, 0, 0, 0, 1, 130, -1]
        constructor = fake_fighter_constructor(definition)
        self.assertEqual((constructor["kind"], constructor["height"]), (-1, -126))
        self.assertFalse(constructor["obstacle"])
        self.assertFalse(constructor["running_effect_manager"])

    def create(self, provider=True):
        fight = SimpleNamespace(
            id=77,
            actors={7: SimpleNamespace(id=7, position=(0, 0, 0), direction=0, team=0)},
            native_effect_areas={},
            native_qi_snapshot=dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16),
            native_qi_slots=[None] * 127,
            native_qi_touched_cells=[],
        )
        allocated, packets = [], []

        def allocate():
            uid = 901 + len(allocated)
            allocated.append(uid)
            return uid

        def register(preview, row, constructor):
            registry = NativeQIRegistry(
                preview.native_qi_snapshot,
                preview.native_qi_slots,
                touched_cells=preview.native_qi_touched_cells,
            )
            if row is None:
                if all(item is not None for item in registry.slots):
                    raise ValueError("Native QI obstacle capacity unavailable")
                return None
            slot = registry.register(
                dict(
                    identity=("effect_area", row["uid"]),
                    position=row["cell"][:2],
                    radius=0,
                    indexed=False,
                    movement_blocking=constructor["movement_blocking"],
                )
            )
            preview.native_qi_slots = registry.serialized_slots()
            preview.native_qi_touched_cells = registry.serialized_cells()
            return slot

        handler = NativeEffectAreaHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *args: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            container=lambda invocation: (dict(container_type=None), None),
            area_affiliation=lambda *args: 0,
            area_obstacle_register=register if provider else None,
        )
        handler.on_created = lambda row: None
        return fight, handler, allocated, packets

    def invoke(self, handler):
        return handler(
            {"effect_class": 339},
            {"parameters": [1035]},
            EffectInvocation(100, 1, 7, None, (2, 3, 0)),
        )

    def test_actual_constructor_qf_registration_and_removal(self):
        fight, handler, allocated, packets = self.create()
        self.assertTrue(self.invoke(handler))
        row = fight.native_effect_areas[901]
        self.assertEqual(allocated, [901, 902])
        self.assertEqual(row["native_area_contract"], "faW")
        self.assertEqual(row["native_obstacle_id"], 0)
        self.assertNotIn(12, native_effect_areas()["1035"]["native_area_properties"])
        self.assertIsNotNone(state_manager(fight, 901))
        self.assertTrue(registered_area_pv(fight, 901).native_running_effect_manager)
        self.assertNotIn("hp", row)
        registry = NativeQIRegistry(fight.native_qi_snapshot, fight.native_qi_slots)
        self.assertEqual(registry.snapshot().U(2, 3), frozenset((0,)))
        self.assertFalse(registry.slots[0]["movement_blocking"])
        targeting = area_target_context(area_targets(fight)[0])
        self.assertEqual(
            (targeting["bcN"], targeting["bcO"], targeting["bcP"], targeting["bEe"]),
            (0, True, False, True),
        )
        remove_owned_hour_area(fight, 901)
        self.assertIsNone(fight.native_qi_slots[0])
        self.assertEqual(row["native_obstacle_id"], -1)
        self.assertFalse(row["native_qq_bhi"])
        self.assertEqual(len(packets), 1)

    def test_missing_spatial_producer_rejects_before_uids(self):
        fight, handler, allocated, packets = self.create(provider=False)
        with self.assertRaisesRegex(ValueError, "QI registration provider"):
            self.invoke(handler)
        self.assertEqual((allocated, packets, fight.native_effect_areas), ([], [], {}))

    def test_central_retention_and_removal_keep_distinct_area_and_effect_uids(self):
        fight, handler, allocated, packets = self.create()
        fight.actors[7].state_ledger = StateLedger(7)
        fight.native_retained_tracking = True
        fight.native_retained_records = {}
        fight.native_retained_order = []
        fight.native_owned_group_effects = {}
        fight.owned_stat_effects = {}
        fight.state_wire_payloads = {}
        effect = dict(
            effect_class=339,
            variant=0,
            minimum_level=0,
            maximum_level=200,
            parameters=[1035],
            native_execution_mode=0,
        )
        definition = dict(
            effect,
            definition_type=0,
            definition_dispellable=True,
            owner_on_caster=True,
            subscription=False,
        )
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=dict(native_retained_container=dict(present=False)),
            state_catalog={},
            action_id=1,
            timing=None,
            metadata=dict(effects={"100": definition}),
        )
        retention.stat_handler = SimpleNamespace(fight=fight, registry={})
        handler.container = retention.container
        handler.context = lambda *args: StatExecutionContext(
            True, True, None, True, b"\x08\x00"
        )
        wrapped = retention.wrap(handler)
        self.assertTrue(
            wrapped(
                effect,
                {"parameters": [1035]},
                EffectInvocation(100, 1, 7, None, (2, 3, 0)),
            )
        )
        self.assertEqual(allocated, [901, 902])
        self.assertEqual(fight.native_owned_area_effects[902]["area_uid"], 901)
        self.assertEqual(fight.native_retained_records[902]["manager_id"], 7)
        self.assertEqual(fight.native_retained_order, [902])
        retention.removal(retention.view()).remove([902])
        retention.synchronize()
        self.assertEqual(fight.native_effect_areas, {})
        self.assertEqual(fight.native_owned_area_effects, {})
        self.assertEqual(fight.native_retained_records, {})
        self.assertIsNone(fight.native_qi_slots[0])
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(struct.unpack(">qq", packets[-1][1][-16:]), (7, 902))


if __name__ == "__main__":
    unittest.main()
