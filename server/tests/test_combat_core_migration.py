"""Canonical family, component and operation metadata after selector retirement."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import combat_core_migration as migration
from wakfu_server.combat_core_migration import MIGRATION_FAMILIES, operation_contracts


class CoreMigrationContractTests(unittest.TestCase):
    def test_contract_references_are_canonical_operations(self):
        from wakfu_server.combat_operation_registry import OPERATIONS

        self.assertEqual(len(MIGRATION_FAMILIES), 7)
        for name, family in MIGRATION_FAMILIES.items():
            with self.subTest(family=name):
                self.assertEqual(name, family.name)
                self.assertTrue(family.invariants)
                self.assertTrue(family.operation_ids)
                self.assertEqual(
                    operation_contracts(name),
                    tuple(OPERATIONS[identity] for identity in family.operation_ids),
                )
                for descriptor in operation_contracts(name):
                    self.assertIs(OPERATIONS[descriptor.operation_id], descriptor)
        with self.assertRaises(TypeError):
            MIGRATION_FAMILIES["other"] = None
        with self.assertRaises(FrozenInstanceError):
            next(iter(MIGRATION_FAMILIES.values())).components = ()

    def test_every_family_names_existing_shared_source_components(self):
        source = Path(migration.__file__).resolve().parent
        attributes = set()
        for family in MIGRATION_FAMILIES.values():
            with self.subTest(family=family.name):
                self.assertTrue(family.components)
                self.assertEqual(len(family.components), len(set(family.components)))
                self.assertNotIn(family.backend_attribute, attributes)
                attributes.add(family.backend_attribute)
                for component in family.components:
                    self.assertTrue(component.isidentifier())
                    self.assertTrue((source / (component + ".py")).is_file())

    def test_current_runtime_has_no_migration_selection_or_observation_api(self):
        for name in (
            "resolve_backend",
            "_backend",
            "_OVERRIDES",
            "_BACKENDS",
            "_OBSERVER",
            "family_backend_scope",
            "migration_observation_scope",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(migration, name))

    def test_unknown_family_and_dangling_canonical_reference_fail_explicitly(self):
        from wakfu_server import combat_operation_registry as registry

        for unknown in ("missing", None, []):
            with self.subTest(family=unknown), self.assertRaises(ValueError):
                operation_contracts(unknown)
        descriptors = dict(registry.OPERATIONS)
        descriptors.pop("execution.entry")
        with patch.object(registry, "OPERATIONS", descriptors):
            with self.assertRaisesRegex(
                ValueError, "Missing canonical combat operation"
            ):
                operation_contracts("entry")


if __name__ == "__main__":
    unittest.main()
