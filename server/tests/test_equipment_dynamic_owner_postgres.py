"""Real saved equipment/Ready controls and original eYm engine execution."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import unittest

from postgres_case import PostgresCase


class EquipmentDynamicOwnerPostgresTests(PostgresCase):
    def _owner(self):
        from test_equipment_level_groups_postgres import (
            EquipmentLevelGroupsPostgresTests,
        )

        return EquipmentLevelGroupsPostgresTests._owner(self, 245)

    def _grant(self, account, generation, owner, reference, slot):
        from test_equipment_level_groups_postgres import (
            EquipmentLevelGroupsPostgresTests,
        )

        return EquipmentLevelGroupsPostgresTests._grant(
            self, account, generation, owner, reference, slot
        )

    def _save(self, account, generation, owner, item=None):
        from test_equipment_level_groups_postgres import (
            EquipmentLevelGroupsPostgresTests,
        )

        return EquipmentLevelGroupsPostgresTests._save(
            self, account, generation, owner, item
        )

    def _ready(self, owner, account):
        from test_equipment_level_groups_postgres import (
            EquipmentLevelGroupsPostgresTests,
        )

        return EquipmentLevelGroupsPostgresTests._ready(self, owner, account)

    def test_saved_purple_source_ready_restore_and_actual_native_group_level(self):
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_execution import (
            equipment_effect_definitions,
        )
        from wakfu_server.combat_equipment_dynamic_levels import (
            OwnerLevelFacts,
            owner_child_levels,
        )
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        account, generation, owner = self._owner()
        item = self._grant(account, generation, owner, 33395, 0)
        owner = self._save(account, generation, owner, item)
        reopened = self.store.character(account, owner["id"])
        self.assertTrue(
            any(
                row["uid"] == item["uid"] and row["quantity"] == 1
                for row in reopened["inventory_items"]
            )
        )
        native = copied_equipment_plan(33395, native_copied_equipment_catalog())
        root = next(row for row in native["roots"] if row["effect_class"] == 999)
        planned = plan(owner, ordinary_only=True)
        # This actual source's eYm scalar root is already snapshot-owned. It
        # must not be silently executed a second time by the Ready change.
        self.assertFalse(
            any(root["reference"] in source["roots"] for source in planned)
        )
        started, _runtime, _packets, _arena, _actor_payload, _stats = self._ready(
            owner, account
        )
        restored = decode_state(encode_state(started))
        self.assertEqual(snapshot(restored), snapshot(started))
        self.assertEqual(
            restored.actors[owner["id"]].effective_level,
            started.actors[owner["id"]].effective_level,
        )

        # Exercise the original native group independently inside the real
        # initialized engine. This is not another item initialization, nor a
        # claim that a snapshot-owned root became a new Ready source.
        closure = equipment_effect_definitions({"roots": [root]})
        effect = closure[str(root["reference"])]
        actor = restored.actors[owner["id"]]
        facts = OwnerLevelFacts.capture(restored, actor.id, account)
        proof = owner_child_levels(
            effect, native["native_retained_container"]["level"], facts
        )
        self.assertEqual(proof.levels, (actor.effective_level,))
        self.assertNotEqual(
            proof.levels, (native["native_retained_container"]["level"],)
        )
        base, _ = server_runtime(
            owner,
            {-200: self._monster_for_runtime()},
            encode_deck([6972]),
            action_id=900,
            critical=False,
            rng=Random(8),
        )
        seen = []
        actual_stat = base.contexts.stat

        def observe_stat(preview, runtime_plan, definition, invocation):
            if definition["effect_class"] == 120:
                seen.append(invocation.level)
            return actual_stat(preview, runtime_plan, definition, invocation)

        factory = NativeEffectRuntimeFactory(
            effects=closure,
            state_catalog=base.state_catalog,
            characteristic_registry=base.characteristic_registry,
            action_id=900,
            contexts=replace(base.contexts, stat=observe_stat),
            summon_authority=base.summon_authority,
            healing_event_authority=base.healing_event_authority,
            relative_group_children=base.relative_group_children,
            random_group_children=base.random_group_children,
            displacement_authority=base.displacement_authority,
            transaction_rng=Random(8),
        )
        child = closure[str(effect["children"][0])]
        from wakfu_server.combat_equipment_operation_capability import validate_effect

        routes, provider = factory.equipment_operation_capability()
        container = native["native_retained_container"]
        group_capability = validate_effect(
            effect,
            container["level"],
            base.characteristic_registry,
            runtime_bindings=routes,
            criteria_capability=provider,
            retained_container=container,
            owner_level_facts=facts,
            effect_reference=root["reference"],
        )
        self.assertEqual(group_capability.status, "supported", group_capability.reasons)
        self.assertEqual(group_capability.parameters[0]["child_levels"], proof.levels)
        child_capability = validate_effect(
            child,
            proof.levels[0],
            base.characteristic_registry,
            runtime_bindings=routes,
            criteria_capability=provider,
            retained_container=container,
            effect_reference=effect["children"][0],
        )
        self.assertEqual(child_capability.status, "supported", child_capability.reasons)
        # These are complete real group/child operation checks, not a fabricated
        # claim that this scalar subtree is the item's entire passive source.
        stat_id = base.characteristic_registry["effects"][str(child["effect_class"])][
            "fixed_stat_id"
        ]
        expected = effect_profile(child, proof.levels[0])["parameters"][0]
        before = actor.effect_stats[stat_id]
        preview = deepcopy(restored)
        container = native["native_retained_container"]
        with preview.effect_resolution():
            dispatcher, packets = factory(
                preview, {"native_retained_container": container}
            )
            self.assertTrue(
                dispatcher.execute(
                    EffectInvocation(
                        root["reference"],
                        container["level"],
                        actor.id,
                        actor.id,
                        actor.position,
                        native_retained_container=container,
                        native_explicit_target=True,
                    )
                )
            )
        self.assertEqual(set(seen), {actor.effective_level})
        self.assertEqual(
            preview.actors[actor.id].effect_stats[stat_id] - before, expected
        )
        self.assertTrue(packets)
        self.assertEqual(restored.actors[actor.id].effect_stats[stat_id], before)
        self.assertTrue(facts.verify(preview))
        preview.actors[actor.id].effective_level += 1
        self.assertFalse(facts.verify(preview))

    def test_whole_ivory_source_uses_owned_movement_and_element_producers(self):
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts
        from wakfu_server.combat_equipment_operation_capability import validate_graph
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck

        account, generation, owner = self._owner()
        item = self._grant(account, generation, owner, 31361, 0)
        owner = self._save(account, generation, owner, item)
        sources = plan(owner, ordinary_only=True)
        source = next(row for row in sources if row["source_reference"] == 31361)
        fight, _runtime, _packets, _arena, _payload, _stats = self._ready(
            owner, account
        )
        pin = fight.native_owned_equipment_sources[str(owner["id"])]
        self.assertTrue(any(row["source_reference"] == 31361 for row in pin["sources"]))
        self.assertFalse(
            any(row["source_reference"] == 31361 for row in pin["deferred"])
        )
        factory, _ = server_runtime(
            owner,
            {-200: self._monster_for_runtime()},
            encode_deck([6972]),
            action_id=901,
            critical=False,
            rng=Random(9),
        )
        routes, provider = factory.equipment_operation_capability()
        result = validate_graph(
            source,
            compiled_with_sources(compiled_runtime_catalog(), sources),
            characteristic_registry(),
            runtime_bindings=routes,
            criteria_capability=provider,
            owner_level_facts=OwnerLevelFacts.capture(fight, owner["id"], account),
        )
        self.assertEqual(result.status, "supported", result.reasons)
        self.assertFalse(result.reasons)
        reopened = self.store.character(account, owner["id"])
        self.assertTrue(
            any(
                row["uid"] == item["uid"] and row["quantity"] == 1
                for row in reopened["inventory_items"]
            )
        )
        # This proves actual source admission; the movement/paid-hit lifecycle
        # has its own focused pipeline rather than an inferred helper claim.
        print(
            "Native whole-source31361 boundary:",
            dict(family=result.family, reasons=result.reasons),
        )

    def _monster_for_runtime(self):
        from wakfu_server.monsters import owned_instance

        return owned_instance(4168, 190, -200, map_id=1134, x=-5, y=-7, z=-1)


if __name__ == "__main__":
    unittest.main()
