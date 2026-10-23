"""Original equipment graph Ready with the actual world registry producer."""
from postgres_case import PostgresCase
import test_equipment_null_carrier_pipeline as null_pipeline


class EquipmentProtectorReadyTests(PostgresCase):
    _fixture = null_pipeline.EquipmentNullCarrierPipelineTests._fixture

    def test_actual_native_source_ready_with_captured_absence_and_checkpoint(self):
        from wakfu_server.equipment import RULES
        from wakfu_server.combat_protector_fight_condition import (
            capture_world_registry_record,
        )
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts
        from wakfu_server.combat_equipment_operation_capability import validate_graph
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_server_spell import (
            server_runtime,
            compiled_runtime_catalog,
        )
        from wakfu_server.combat_protector_fight_condition import (
            bind_condition_capability,
        )

        def capture(preview, action_id, char, monster, deck, rng):
            with self.store.connection() as db:
                preview.native_protector_registry = capture_world_registry_record(
                    db, char, preview.id
                )

        # Actual source10632 shares the original protector predicate subtree
        # with9728 without9728's independentcrime equip requirement.
        char, monster, deck, rng, runtime, stats = self._fixture(
            reference=10632,
            slot=RULES[10632]["slots"][0],
            before_initialization=capture,
        )
        fight = runtime.fight
        sources = plan(char, ordinary_only=True)
        source = next(row for row in sources if row["source_reference"] == 10632)
        factory, _ = server_runtime(
            char, {-200: monster}, deck, action_id=901, critical=False, rng=rng
        )
        self.assertIsNotNone(bind_condition_capability(factory, fight))
        routes, provider = factory.equipment_operation_capability()
        result = validate_graph(
            source,
            compiled_with_sources(compiled_runtime_catalog(), sources),
            characteristic_registry(),
            runtime_bindings=routes,
            criteria_capability=provider,
            owner_level_facts=OwnerLevelFacts.capture(
                fight, char["id"], char["account_id"]
            ),
        )
        self.assertEqual(result.status, "supported", result.reasons)
        pin = fight.native_owned_equipment_sources[str(char["id"])]
        self.assertTrue(any(row["source_reference"] == 10632 for row in pin["sources"]))
        restored = decode_state(encode_state(fight))
        self.assertEqual(snapshot(restored), snapshot(fight))
        self.assertEqual(
            restored.native_protector_registry, fight.native_protector_registry
        )
