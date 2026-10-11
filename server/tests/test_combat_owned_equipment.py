"""Real owned item PL execution, catalog composition and atomic previews."""
import unittest
from copy import deepcopy

import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_owned_equipment import (
    compiled_with_sources,
    immediate_scalar_contract,
    initialize_transaction,
)
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_copied_equipment_execution import equipment_effect_definitions
from wakfu_server.combat_server_spell import compiled_runtime_catalog, server_runtime
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class OwnedEquipmentInitializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.character,
            cls.monster,
            cls.fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            1, 100, native_qi=True
        )
        cls.compiled = compiled_runtime_catalog()
        cls.registry = characteristic_registry()
        cls.native = native_copied_equipment_catalog()

    def source(self, reference=27152):
        attached = copied_equipment_plan(reference, self.native)
        parent = copied_equipment_plan(10272, self.native)
        return dict(
            uid=500,
            reference=10272,
            source_reference=reference,
            attachment_field=24,
            roots=tuple(row["reference"] for row in attached["roots"]),
            effects=equipment_effect_definitions(attached),
            native_retained_container=dict(parent["native_retained_container"]),
        )

    def preparation(self, sources):
        compiled = compiled_with_sources(self.compiled, sources)
        for source in sources:
            self.assertIsNone(
                immediate_scalar_contract(source, compiled, self.registry)
            )
        return dict(compiled=compiled, sources=tuple(sources), deferred=())

    def factory(self, compiled):
        return server_runtime(
            self.character,
            {self.monster["id"]: self.monster},
            encode_deck(),
            action_id=1,
            critical=False,
            compiled=compiled,
        )[0]

    def test_actual_owned_dispatch_installs_parent_item_container_without_mutating_original(
        self,
    ):
        source = self.source()
        preparation = self.preparation([source])
        before = snapshot(self.fight)
        preview, packets = initialize_transaction(
            self.fight,
            7,
            preparation,
            self.factory(preparation["compiled"]),
            owner_id=3,
        )
        self.assertEqual(snapshot(self.fight), before)
        self.assertTrue(packets)
        # Native state6026 at root level2 selects class150 with amount6.
        self.assertEqual(
            preview.actors[7].effect_stats[9], self.fight.actors[7].effect_stats[9] + 6
        )
        records = list(preview.native_retained_records.values())
        expected = source["native_retained_container"]
        self.assertTrue(
            any(
                row["container_id"] == expected["id"]
                and row["container_type"] == expected["type"]
                for row in records
            )
        )
        self.assertIn(7, preview.native_owned_equipment_initializations)
        with self.assertRaisesRegex(ValueError, "already initialized"):
            initialize_transaction(
                preview,
                7,
                preparation,
                self.factory(preparation["compiled"]),
                owner_id=3,
            )

    def test_uncomposed_factory_and_foreign_owner_are_rejected_before_mutation(self):
        preparation = self.preparation([self.source()])
        before = snapshot(self.fight)
        with self.assertRaisesRegex(ValueError, "predates"):
            initialize_transaction(
                self.fight, 7, preparation, self.factory(self.compiled), owner_id=3
            )
        with self.assertRaisesRegex(ValueError, "owned active"):
            initialize_transaction(
                self.fight,
                7,
                preparation,
                self.factory(preparation["compiled"]),
                owner_id=4,
            )
        self.assertEqual(snapshot(self.fight), before)

    def test_late_failure_discards_prior_native_effects_and_packets(self):
        preparation = self.preparation([self.source(), self.source(28871)])
        factory = self.factory(preparation["compiled"])
        calls = []

        def fail_second(preview, invocation):
            calls.append(True)
            if len(calls) == 2:
                raise ValueError("injected second source failure")
            return factory(preview, invocation)

        fail_second.effects = factory.effects
        before = snapshot(self.fight)
        with self.assertRaisesRegex(ValueError, "injected second"):
            initialize_transaction(self.fight, 7, preparation, fail_second, owner_id=3)
        self.assertEqual(len(calls), 2)
        self.assertEqual(snapshot(self.fight), before)
        self.assertFalse(hasattr(self.fight, "native_owned_equipment_initializations"))

    def test_shape_gate_defers_event_subscriptions_and_ordinary_snapshot_roots(self):
        source = self.source()
        preparation = self.preparation([source])
        ordinary = dict(source, attachment_field=None)
        self.assertEqual(
            immediate_scalar_contract(ordinary, preparation["compiled"], self.registry),
            "ordinary_equipment_remains_snapshot_owned",
        )
        altered = deepcopy(source)
        root = str(source["roots"][0])
        altered["effects"][root]["criteria"] = "caster.level>1"
        # Changing existing definitions is a collision, never an override.
        with self.assertRaises(ValueError):
            compiled_with_sources(preparation["compiled"], [altered])

    def test_empty_area_requires_native_explicit_self_selector(self):
        for mask, area in ((1, "empty"), (2, "point"), (0, "circle")):
            with self.subTest(mask=mask, area=area):
                source = self.source()
                root = source["effects"][str(source["roots"][0])]
                root["native_target_selector"] = {"class": "fcE", "mask": mask}
                root["area_native"] = area
                compiled = compiled_with_sources(self.compiled, [source])
                self.assertEqual(
                    immediate_scalar_contract(source, compiled, self.registry),
                    "nonself_target_contract_requires_qualification",
                )

    def test_later_additive_state_levels_cannot_enable_unqualified_children(self):
        from wakfu_server.combat_static_catalogs import CompiledEffects

        source = self.source()
        states = dict(self.compiled.source_states)
        states["effects"] = dict(states["effects"])
        # Negative fixture: only levels above2 select this changed predicate.
        states["effects"]["283474"] = dict(
            states["effects"]["283474"], minimum_level=3, criteria="caster.level>1"
        )
        effects = dict(self.compiled.source_effects)
        effects.pop("283474", None)
        compiled = compiled_with_sources(CompiledEffects(effects, states), [source])
        self.assertEqual(
            immediate_scalar_contract(source, compiled, self.registry),
            "conditional_or_group_execution_requires_qualification",
        )
