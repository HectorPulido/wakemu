"""Actual preview binding, bounded metadata reuse and private failure rollback."""
from copy import deepcopy
import unittest

import test_combat_owned_equipment_pin as pin_fixture
from wakfu_server.combat_owned_equipment import initialize_transaction
from wakfu_server.combat_owned_equipment_factory import (
    OwnedEquipmentRuntimeFactory,
    _compiled_sources,
)
from wakfu_server.fight_checkpoint_store import snapshot


class OwnedEquipmentFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pin_fixture.OwnedEquipmentPinTests.setUpClass()
        cls.fixture = pin_fixture.OwnedEquipmentPinTests(
            "test_actual_plan_pin_is_immutable_detached_and_used_by_later_factory"
        )

    def test_actual_preview_binds_late_factory_and_preserves_group_authorities(self):
        fixture = self.fixture
        base = fixture.native.factory(fixture.compiled)
        wrapped = OwnedEquipmentRuntimeFactory(base, fixture.compiled)
        groups = (base.relative_group_children, base.random_group_children)
        definitions = tuple(authority.effects for authority in groups)
        character, (pinned, initial) = fixture.pin()
        root = str(initial["sources"][0]["roots"][0])
        self.assertNotIn(root, base.effects)
        character["inventory_items"].clear()
        character["builds"].clear()
        # The factory existed before the pin, as readiness expiration providers do.
        cache_before = _compiled_sources.cache_info()
        dispatcher, packets = wrapped(
            pinned, {"native_retained_container": {"present": False}}
        )
        self.assertIn(root, dispatcher.effects)
        self.assertFalse(packets)
        repeated, _ = wrapped(pinned, {"native_retained_container": {"present": False}})
        self.assertIs(repeated.effects, dispatcher.effects)
        self.assertGreater(_compiled_sources.cache_info().hits, cache_before.hits)
        # Equal static definitions must share cache even for distinct bag UIDs.
        from wakfu_server.combat_owned_equipment_pin import pin_transaction
        from wakfu_server.wire import proto_field

        other_character, authority = fixture.equipped()
        other_character["inventory_items"][0]["uid"] = 700
        other_character["builds"][0]["equipment"] = proto_field(
            10, proto_field(8, 700) + proto_field(16, 10)
        ).hex()
        other_pin, _ = pin_transaction(
            fixture.fight,
            other_character,
            authority,
            fixture.compiled,
            fixture.registry,
            owner_id=3,
        )
        other_dispatcher, _ = wrapped(
            other_pin, {"native_retained_container": {"present": False}}
        )
        self.assertIs(other_dispatcher.effects, dispatcher.effects)
        self.assertEqual(
            (base.relative_group_children, base.random_group_children), groups
        )
        self.assertTrue(
            all(
                authority.effects is original
                for authority, original in zip(groups, definitions)
            )
        )
        self.assertNotIn(root, base.effects)
        # Normal owned application uses the same wrapper and preserves stats.
        initial_factory = fixture.native.factory(initial["compiled"])
        preview, _ = initialize_transaction(
            pinned,
            7,
            initial,
            OwnedEquipmentRuntimeFactory(initial_factory, initial["compiled"]),
            owner_id=3,
        )
        self.assertEqual(
            preview.actors[7].effect_stats[9],
            fixture.fight.actors[7].effect_stats[9] + 6,
        )
        # Weapon/melee and NPC factories use different static source catalogs.
        # They must verify the same pinned state contract without live bags.
        from wakfu_server.combat_weapon import weapon_runtime_catalog
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        for compiled in (weapon_runtime_catalog(), npc_runtime_catalog()):
            other = OwnedEquipmentRuntimeFactory(
                fixture.native.factory(compiled), compiled
            )
            other_dispatcher, _ = other(
                preview, {"native_retained_container": {"present": False}}
            )
            self.assertIn(root, other_dispatcher.effects)

    def test_failure_after_actual_native_mutation_rolls_back_private_preview(self):
        fixture = self.fixture
        _, (pinned, initial) = fixture.pin()
        wrapped = OwnedEquipmentRuntimeFactory(
            fixture.native.factory(initial["compiled"]), initial["compiled"]
        )
        captured = []

        class FailingFactory:
            effects = wrapped.effects

            def __call__(self, preview, plan):
                dispatcher, packets = wrapped(preview, plan)
                original = dispatcher.execute

                def fail(invocation):
                    result = original(invocation)
                    captured.append(preview.actors[7].effect_stats[9])
                    raise ValueError("injected after native application")

                dispatcher.execute = fail
                return dispatcher, packets

        before = snapshot(pinned)
        with self.assertRaisesRegex(ValueError, "after native"):
            initialize_transaction(pinned, 7, initial, FailingFactory(), owner_id=3)
        self.assertIn(fixture.fight.actors[7].effect_stats[9] + 6, captured)
        self.assertEqual(snapshot(pinned), before)

    def test_corrupt_restored_pin_rejects_before_factory_mutates_preview(self):
        fixture = self.fixture
        _, (pinned, _) = fixture.pin()
        restored = deepcopy(fixture.fight)
        restored.native_owned_equipment_sources = snapshot(pinned)[
            "native_owned_equipment_sources"
        ]
        restored.native_owned_equipment_sources["7"]["sources"][0]["uid"] += 1
        before = snapshot(restored)
        wrapped = OwnedEquipmentRuntimeFactory(
            fixture.native.factory(fixture.compiled), fixture.compiled
        )
        with self.assertRaisesRegex(ValueError, "integrity"):
            wrapped(restored, {"native_retained_container": {"present": False}})
        self.assertEqual(snapshot(restored), before)

    def test_copied_factory_keeps_private_equipment_overlays_and_original_identity(
        self,
    ):
        from copy import copy
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )

        fixture = self.fixture
        _, (pinned, _) = fixture.pin()
        base = fixture.native.factory(fixture.compiled)
        original_effects, original_states = base.effects, base.state_catalog
        wrapped = OwnedEquipmentRuntimeFactory(base, fixture.compiled)
        private = copy(wrapped)
        definitions = equipment_effect_definitions(
            copied_equipment_plan(10272, fixture.native.native)
        )
        private.effects = dict(private.effects, **definitions)
        private.state_catalog = dict(
            private.state_catalog,
            effects=dict(private.state_catalog["effects"], **definitions),
        )
        dispatcher, _ = private(
            pinned, {"native_retained_container": {"present": False}}
        )
        self.assertTrue(set(definitions) <= set(dispatcher.effects))
        self.assertIn("283591", dispatcher.effects)
        self.assertIs(base.effects, original_effects)
        self.assertIs(base.state_catalog, original_states)
        self.assertIsNot(private.effects, base.effects)
        self.assertIsNot(private.state_catalog, base.state_catalog)

    def test_repeated_same_catalog_wrapper_preserves_one_private_factory(self):
        from copy import copy

        base = self.fixture.native.factory(self.fixture.compiled)
        wrapped = OwnedEquipmentRuntimeFactory(base, self.fixture.compiled)
        self.assertIs(wrapped._factory, base._factory)
        private = copy(wrapped)
        self.assertIsNot(private._factory, wrapped._factory)
        original_effects = wrapped.effects
        private.effects = dict(private.effects)
        self.assertIs(wrapped.effects, original_effects)
        self.assertIsNot(private.effects, original_effects)

    def test_private_factory_rejects_genuinely_different_native_point_offsets(self):
        from copy import copy
        from wakfu_server.combat_native_area_metadata import native_point_area_metadata

        _, (pinned, _) = self.fixture.pin()
        private = copy(self.fixture.native.factory(self.fixture.compiled))
        metadata = native_point_area_metadata()
        reference = next(
            key
            for key, effect in private.effects.items()
            if effect.get("area_class") in ("anE", "anJ") and key in metadata
        )
        changed = dict(
            private.effects[reference], native_area_points=[[987654, 987654]]
        )
        private.effects = dict(private.effects, **{reference: changed})
        with self.assertRaisesRegex(
            ValueError, "Conflicting native point area offsets"
        ):
            private(pinned, {"native_retained_container": {"present": False}})
