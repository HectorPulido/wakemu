"""Operation metadata must point to real code without implying proof."""
import ast
import gc
from dataclasses import FrozenInstanceError
import os
import subprocess
import sys
from pathlib import Path
import unittest
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[2]
COMBAT_DIR = ROOT / "server/wakfu_server/combat"
REGISTRY_PATH = COMBAT_DIR / "combat_operation_registry.py"
sys.path.insert(0, str(ROOT / "server"))
from wakfu_server import combat_operation_registry as registry


class CombatOperationRegistryTests(unittest.TestCase):
    def test_triggering_amount_requires_its_real_handler_and_parameter_triple(self):
        effect = {"effect_class": 430, "parameters": [1, 0, -800, 0, 0, 0]}
        contract = registry.operation_for_family(430)
        self.assertEqual(
            contract.executor, "combat_trigger_value_handler.NativeTriggerValueHandler"
        )
        self.assertIn("exact live triggering Qe identity", contract.prerequisites)
        self.assertEqual(registry.assess_operation(effect).status, "conditional")
        self.assertEqual(
            registry.assess_operation(effect, runtime_bindings={}).status,
            "unsupported",
        )
        for parameters in ([], [1, 0], [1, 0, 800, 0, 0], [1, 0, 800, 0, 0, 0, 0, 0]):
            with self.subTest(parameters=parameters):
                self.assertEqual(
                    registry.assess_operation(
                        dict(effect, parameters=parameters)
                    ).status,
                    "unsupported",
                )

    def test_compiler_and_dispatcher_share_one_flat_registry_module(self):
        env = dict(os.environ)
        env.pop("WAKFU_DATABASE_URL", None)
        env.pop("WAKFU_DATABASE_PASSWORD_FILE", None)
        env["PYTHONPATH"] = (
            str(ROOT / "server") + os.pathsep + str(ROOT / "server/tools")
        )
        code = (
            "import sys; import combat_operation_catalog as compiler; "
            "import wakfu_server.combat_effect_dispatch as dispatch; "
            "module=sys.modules['wakfu_server.combat_operation_registry']; "
            "assert compiler.operation_registry is module; "
            "assert dispatch.RuntimeOperationBinding is module.RuntimeOperationBinding; "
            "assert not any(name.endswith('.combat.combat_operation_registry') for name in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_executor_modules_and_symbols_exist_in_source(self):
        for contract in registry.OPERATIONS.values():
            with self.subTest(operation=contract.operation_id):
                module_name, symbol_name = contract.executor.split(".", 1)
                source_path = COMBAT_DIR / f"{module_name}.py"
                self.assertTrue(source_path.is_file(), contract.executor)
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
                symbols = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(
                        node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                }
                self.assertIn(symbol_name, symbols, contract.executor)

    def test_test_references_resolve_to_real_test_modules(self):
        contracts = (*registry.OPERATIONS.values(), registry.RETAINED_EXECUTION)
        for contract in contracts:
            for test_name in contract.tests:
                with self.subTest(operation=contract.operation_id, test=test_name):
                    self.assertRegex(test_name, r"^test_[a-zA-Z0-9_]+$")
                    self.assertTrue(
                        (ROOT / "server/tests" / f"{test_name}.py").is_file()
                    )

    def test_family_ids_are_unique_and_index_matches_contracts(self):
        listed = [family for item in registry._CONTRACTS for family in item.families]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(set(listed), set(registry.FAMILY_OPERATIONS))
        for family in listed:
            self.assertIs(
                registry.operation_for_family(family),
                registry.FAMILY_OPERATIONS[family],
            )
        self.assertIsNone(registry.operation_for_family(True))
        self.assertIsNone(registry.operation_for_family("304"))

    def test_contract_and_registry_collections_are_immutable(self):
        contract = registry.OPERATIONS["state.decurse"]
        self.assertIsInstance(registry.OPERATIONS, MappingProxyType)
        self.assertIsInstance(registry.FAMILY_OPERATIONS, MappingProxyType)
        with self.assertRaises(TypeError):
            registry.OPERATIONS["new"] = contract
        with self.assertRaises(TypeError):
            registry.FAMILY_OPERATIONS[999] = contract
        with self.assertRaises(FrozenInstanceError):
            contract.operation_id = "mutated"
        with self.assertRaises(AttributeError):
            contract.families.append(777)
        # MappingProxyType is a view; ensure its mutable backing dict has no
        # independently reachable module-global alias that could alter it.
        operation_backing, family_backing = (
            gc.get_referents(registry.OPERATIONS)[0],
            gc.get_referents(registry.FAMILY_OPERATIONS)[0],
        )
        self.assertIsInstance(operation_backing, dict)
        self.assertIsInstance(family_backing, dict)
        self.assertFalse(
            any(value is operation_backing for value in vars(registry).values())
        )
        self.assertFalse(
            any(value is family_backing for value in vars(registry).values())
        )

    def test_runtime_binding_covers_absent_and_unmodeled_routes_without_accreditation(
        self,
    ):
        known_handler = object()
        unknown_handler = object()
        routes = {304: known_handler, 999999: unknown_handler}
        bound = registry.bind_runtime_contracts(routes)
        routes[321] = object()
        self.assertNotIn(321, bound)
        self.assertIsInstance(bound, MappingProxyType)
        self.assertIs(bound[304].handler, known_handler)
        self.assertEqual(bound[304].status, "conditional")
        self.assertIs(bound[304].contract, registry.operation_for_family(304))
        self.assertIsNone(bound[999999].contract)
        self.assertEqual(bound[999999].status, "unknown")
        self.assertNotIn(999999, registry.FAMILY_OPERATIONS)
        with self.assertRaises(TypeError):
            bound[304] = object()
        self.assertIsNone(registry.operation_for_family(777777))

    def test_removal_dependencies_are_explicit_and_not_reinterpreted_as_additions(self):
        state_dependencies = registry.dependency_specs(321)
        self.assertEqual(len(state_dependencies), 1)
        dependency = state_dependencies[0]
        self.assertEqual(dependency.kind, "state")
        self.assertEqual(dependency.parameter_index, 0)
        self.assertEqual(dependency.relation, "removes")
        self.assertEqual(registry.dependency_specs(304)[0].relation, "requires")
        self.assertEqual(registry.dependency_specs(999999), ())

    def test_aura_and_morph_dependencies_are_typed_without_admission(self):
        aura = registry.dependency_specs(338)
        self.assertEqual((aura[0].kind, aura[0].parameter_index), ("area", 0))
        self.assertIsNone(registry.operation_for_family(338))
        morph = registry.dependency_specs(933)
        self.assertEqual(
            (morph[0].kind, morph[0].parameter_index, morph[0].transform),
            ("morph", 0, "signed-short"),
        )
        self.assertNotEqual(morph[0].kind, registry.dependency_specs(307)[0].kind)

    def test_registry_source_does_not_import_catalog_or_runtime_modules(self):
        tree = ast.parse(REGISTRY_PATH.read_text(encoding="utf-8"))
        forbidden = (
            "protocol_catalog",
            "native_catalog",
            "combat_effect_runtime",
            "combat_effect_dispatch",
            "combat_subscription_runners",
        )
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        for name in imports:
            with self.subTest(import_name=name):
                self.assertFalse(any(part in name for part in forbidden), name)
        lookup = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "operation_for_family"
        )
        lookup_imports = [
            node
            for node in ast.walk(lookup)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertEqual(
            lookup_imports,
            [],
            "family lookup must stay independent of runtime/catalog imports",
        )

        # The registry's only local metadata dependency is a literal constants
        # module. Validate its transitive AST closure stays import-free too.
        pure_metadata_path = COMBAT_DIR / "combat_subscription_contracts.py"
        pure_metadata = ast.parse(pure_metadata_path.read_text(encoding="utf-8"))
        self.assertFalse(
            any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                for node in ast.walk(pure_metadata)
            )
        )
