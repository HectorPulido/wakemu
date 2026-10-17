"""Source-only operation metadata controls conservative test reachability."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from tools.combat_test_impact import build_graph, select_changes


class OperationImpactTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        environment = patch(
            "tools.combat_test_impact.environment_manifest",
            return_value={"sha256": "e" * 64},
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.catalog = {
            "status": "published",
            "revision": "fixture",
            "documents": {},
            "sha256": "a" * 64,
            "publication_verified": True,
        }
        for name in ("alpha", "beta", "unrelated"):
            self.write("server/tests/test_" + name + ".py", "import unittest\n")
        for name in ("alpha", "beta"):
            self.write("server/wakfu_server/combat/" + name + ".py", "VALUE = 1\n")

    def write(self, path, body):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    def registry(self, suffix=""):
        # A deliberately non-executable module proves the graph does not import it.
        self.write(
            "server/wakfu_server/combat/combat_operation_registry.py",
            """
raise RuntimeError("Never import this source fixture")
_CONTRACTS = (
 _contract("fixture.alpha", (5000,), "alpha.Handler", (), (), (), (), ("test_alpha",)),
 _contract("fixture.beta", (5001,), "beta.Handler", (), (), (), (), ("test_beta",)),
)
"""
            + suffix,
        )

    def graph(self, interactions=None):
        from tools.combat_test_impact import CONTRACTS_PATH

        policy = json.loads(CONTRACTS_PATH.read_bytes())
        policy["operation_interactions"] = [] if interactions is None else interactions
        path = self.root / "fixture-impact-contracts.json"
        path.write_text(json.dumps(policy))
        with patch("tools.combat_test_impact.CONTRACTS_PATH", path):
            return build_graph(self.root, catalog_inventory=self.catalog)

    def migration(self):
        self.write(
            "server/wakfu_server/combat/combat_core_migration.py",
            """
raise RuntimeError("Never import migration source fixtures")
_FAMILIES = (
 MigrationFamily("alpha", "native_alpha_backend", ("fixture.alpha",), ("ordering",)),
 MigrationFamily("beta", "native_beta_backend", ("fixture.beta",), ("ownership",)),
)
MIGRATION_FAMILIES = MappingProxyType({family.name: family for family in _FAMILIES})
""",
        )
        self.write("server/wakfu_server/combat/shared_alpha.py", "VALUE = 1\n")
        self.write(
            "server/wakfu_server/combat/alpha_boundary.py",
            """
from .combat_core_migration import resolve_backend
from .shared_alpha import VALUE
def execute(owner):
    return resolve_backend(owner, "alpha"), VALUE
""",
        )
        self.write(
            "server/tests/test_family_alpha.py",
            """
from wakfu_server.combat_core_migration import family_backend_scope
def test_rollback():
    with family_backend_scope({"alpha": "legacy"}):
        pass
""",
        )

    def test_shared_component_reaches_canonical_family_and_researched_interaction(self):
        self.registry()
        self.migration()
        path = "server/tests/test_researched_family.py"
        self.write(path, "class Research:\n def test_native_sequence(self): pass\n")
        interactions = [
            {
                "id": "native-family-sequence",
                "status": "source-bound-interaction",
                "operation_ids": ["fixture.alpha"],
                "source_ids": ["player-guide"],
                "scope": "Selection only, not execution qualification",
                "test_dependencies": [
                    {
                        "path": path,
                        "source_sha256": hashlib.sha256(
                            (self.root / path).read_bytes()
                        ).hexdigest(),
                        "assertion_witnesses": ["Research.test_native_sequence"],
                    }
                ],
            }
        ]
        before = self.graph(interactions)
        self.write("server/wakfu_server/combat/shared_alpha.py", "VALUE = 2\n")
        after = self.graph(interactions)
        plan = select_changes(before, after)
        self.assertFalse(after["migration_registry"]["errors"])
        self.assertEqual(
            plan["selected_module_names"],
            ["test_alpha", "test_family_alpha", "test_researched_family"],
        )
        edges = {(row["consumer"], row["dependency"]) for row in after["edges"]}
        self.assertIn(("operation:fixture.alpha", "migration-family:alpha"), edges)
        self.assertIn(
            (
                "migration-family:alpha",
                "module:server/wakfu_server/combat/alpha_boundary.py",
            ),
            edges,
        )

    def test_common_rollback_policy_change_selects_all_declared_families(self):
        self.registry()
        self.migration()
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_core_migration.py"
        path.write_text(
            path.read_text() + "\ndef resolve_backend(owner, family): return 'legacy'\n"
        )
        plan = select_changes(before, self.graph())
        self.assertEqual(
            plan["selected_module_names"],
            ["test_alpha", "test_beta", "test_family_alpha"],
        )

    def test_deleted_boundary_preserves_previous_family_consumers(self):
        self.registry()
        self.migration()
        before = self.graph()
        (self.root / "server/wakfu_server/combat/alpha_boundary.py").unlink()
        plan = select_changes(before, self.graph())
        self.assertIn("test_alpha", plan["selected_module_names"])
        self.assertIn("test_family_alpha", plan["selected_module_names"])

    def test_unknown_migration_construction_or_operation_forces_full_selection(self):
        self.registry()
        self.migration()
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_core_migration.py"
        original = path.read_text()
        for changed in (
            original.replace('("fixture.alpha",)', '("fixture.missing",)'),
            original.replace("_FAMILIES = (", "_FAMILIES = discover_families( "),
            original.replace("family.name: family", "family.backend_attribute: family"),
        ):
            with self.subTest(changed=changed):
                path.write_text(changed)
                after = self.graph()
                self.assertTrue(after["migration_registry"]["errors"])
                self.assertEqual(
                    select_changes(before, after)["selected_module_names"],
                    after["module_names"],
                )

    def test_migration_reader_does_not_substitute_workspace_for_historical_snapshot(
        self,
    ):
        self.registry()
        graph = self.graph()
        self.assertIsNone(graph["migration_registry"]["source_sha256"])
        self.assertFalse(
            any(row["kind"] == "migration-family" for row in graph["nodes"])
        )

    def test_metadata_only_cannot_bypass_unchanged_invalid_migration_policy(self):
        self.registry()
        self.migration()
        policy = self.root / "server/wakfu_server/combat/combat_core_migration.py"
        policy.write_text(
            policy.read_text().replace('("fixture.alpha",)', '("fixture.missing",)')
        )
        before = self.graph()
        registry = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        registry.write_text(
            registry.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", ("required snapshot",),'
            )
        )
        after = self.graph()
        plan = select_changes(before, after)
        self.assertFalse(plan["registry_metadata_only"])
        self.assertEqual(plan["selected_module_names"], after["module_names"])

    def test_runtime_dynamic_family_binds_all_declared_operations(self):
        self.registry()
        self.migration()
        self.write(
            "server/wakfu_server/combat/dynamic_boundary.py",
            """
from .combat_core_migration import resolve_backend
def execute(owner, family): return resolve_backend(owner, family)
""",
        )
        before = self.graph()
        self.write(
            "server/wakfu_server/combat/dynamic_boundary.py",
            """
from .combat_core_migration import resolve_backend
def execute(owner, family): return resolve_backend(owner, family), None
""",
        )
        self.assertEqual(
            select_changes(before, self.graph())["selected_module_names"],
            ["test_alpha", "test_beta", "test_family_alpha"],
        )

    def test_component_metadata_preserves_edges_without_runtime_selector_calls(self):
        self.registry()
        self.write("server/wakfu_server/combat/shared_alpha.py", "VALUE = 1\n")
        self.write("server/wakfu_server/combat/shared_beta.py", "VALUE = 1\n")
        self.write(
            "server/wakfu_server/combat/combat_core_migration.py",
            """
raise RuntimeError("Never import source metadata")
_FAMILIES = (
 MigrationFamily("alpha", "historical_alpha", ("fixture.alpha",), ("order",),
                 components=("shared_alpha",)),
 MigrationFamily("beta", "historical_beta", ("fixture.beta",), ("ownership",),
                 ("shared_beta",)),
)
MIGRATION_FAMILIES = MappingProxyType({family.name: family for family in _FAMILIES})
""",
        )
        self.write(
            "server/tests/test_family_alpha.py",
            "from wakfu_server.combat_core_migration import operation_contracts\n"
            "operation_contracts('alpha')\n",
        )
        before = self.graph()
        self.write("server/wakfu_server/combat/shared_alpha.py", "VALUE = 2\n")
        after = self.graph()
        self.assertFalse(after["migration_registry"]["errors"])
        edges = {(row["consumer"], row["dependency"]) for row in after["edges"]}
        self.assertIn(
            (
                "migration-family:alpha",
                "module:server/wakfu_server/combat/shared_alpha.py",
            ),
            edges,
        )
        self.assertIn(("operation:fixture.alpha", "migration-family:alpha"), edges)
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            ["test_alpha", "test_family_alpha"],
        )

    def test_unknown_component_metadata_never_authorizes_bounded_selection(self):
        self.registry()
        self.migration()
        path = self.root / "server/wakfu_server/combat/combat_core_migration.py"
        original = path.read_text()
        before = self.graph()
        for components in (
            '("missing_component",)',
            '("../escape",)',
            '("shared_alpha", "shared_alpha")',
            "discover_components()",
        ):
            with self.subTest(components=components):
                path.write_text(
                    original.replace(
                        '("ordering",))',
                        '("ordering",), components=' + components + ")",
                    )
                )
                after = self.graph()
                self.assertTrue(after["migration_registry"]["errors"])
                self.assertEqual(
                    select_changes(before, after)["selected_module_names"],
                    after["module_names"],
                )

    def test_all_current_family_components_reach_their_canonical_operations(self):
        from tools.combat_test_impact import (
            _migration_source_contracts,
            _operation_source_contracts,
        )

        actual = Path(__file__).resolve().parents[2]
        _, operations, errors, _ = _operation_source_contracts(actual)
        _, families, migration_errors = _migration_source_contracts(
            actual, {operation["id"] for operation in operations}
        )
        self.assertFalse(errors)
        self.assertFalse(migration_errors)
        self.assertEqual(len(families), 7)
        declarations, contracts = [], []
        for index, family in enumerate(families):
            name = family["name"]
            self.assertTrue(family["components"])
            test = "test_family_" + name
            self.write("server/tests/" + test + ".py", "import unittest\n")
            for component in family["components"]:
                self.write(
                    "server/wakfu_server/combat/" + component + ".py", "VALUE = 1\n"
                )
            declarations.append(
                "MigrationFamily("
                + repr(name)
                + ", "
                + repr(family["backend_attribute"])
                + ", "
                + repr(tuple(family["operation_ids"]))
                + ", ('invariant',), "
                + repr(tuple(family["components"]))
                + ")"
            )
            for operation in family["operation_ids"]:
                contracts.append(
                    "_contract("
                    + repr(operation)
                    + ", (), "
                    + repr(family["components"][0] + ".Handler")
                    + ", (), (), (), (), ("
                    + repr(test)
                    + ",))"
                )
        self.write(
            "server/wakfu_server/combat/combat_operation_registry.py",
            "_CONTRACTS = (" + ",".join(contracts) + ",)\n",
        )
        self.write(
            "server/wakfu_server/combat/combat_core_migration.py",
            "_FAMILIES = (" + ",".join(declarations) + ",)\n"
            "MIGRATION_FAMILIES = MappingProxyType({family.name: family for family in _FAMILIES})\n",
        )
        before = self.graph()
        edges = {(row["consumer"], row["dependency"]) for row in before["edges"]}
        self.assertFalse(before["migration_registry"]["errors"])
        for family in families:
            for component in family["components"]:
                with self.subTest(family=family["name"], component=component):
                    self.assertIn(
                        (
                            "migration-family:" + family["name"],
                            "module:server/wakfu_server/combat/" + component + ".py",
                        ),
                        edges,
                    )
            for operation in family["operation_ids"]:
                self.assertIn(
                    ("operation:" + operation, "migration-family:" + family["name"]),
                    edges,
                )
            changed = (
                self.root
                / "server/wakfu_server/combat"
                / (family["components"][0] + ".py")
            )
            changed.write_text("VALUE = 2\n")
            self.assertIn(
                "test_family_" + family["name"],
                select_changes(before, self.graph())["selected_module_names"],
            )
            changed.write_text("VALUE = 1\n")

    def test_actual_migration_contracts_reference_current_registry_without_import(self):
        from tools.combat_test_impact import (
            _migration_source_contracts,
            _operation_source_contracts,
        )

        root = Path(__file__).resolve().parents[2]
        _, operations, registry_errors, _ = _operation_source_contracts(root)
        _, families, migration_errors = _migration_source_contracts(
            root, {operation["id"] for operation in operations}
        )
        self.assertFalse(registry_errors)
        self.assertFalse(migration_errors)
        self.assertTrue(families)

    def test_executor_change_selects_declared_test_without_import(self):
        self.registry()
        before = self.graph()
        self.write("server/wakfu_server/combat/alpha.py", "VALUE = 2\n")
        plan = select_changes(before, self.graph())
        self.assertIn("test_alpha", plan["selected_module_names"])
        self.assertNotIn("test_beta", plan["selected_module_names"])
        self.assertNotIn("test_unrelated", plan["selected_module_names"])

    def test_registry_comment_preserves_contract_fingerprints(self):
        self.registry()
        before = self.graph()
        self.registry("# changed shared contract\n")
        after = self.graph()
        plan = select_changes(before, after)
        self.assertEqual(plan["selected_module_names"], [])
        old = next(
            row for row in before["nodes"] if row["id"] == "operation:fixture.alpha"
        )
        new = next(
            row for row in after["nodes"] if row["id"] == "operation:fixture.alpha"
        )
        self.assertEqual(old["contract_sha256"], new["contract_sha256"])
        self.assertNotEqual(
            before["operation_registry"]["source_sha256"],
            after["operation_registry"]["source_sha256"],
        )

    def test_snapshot_absence_never_loads_workspace_registry(self):
        graph = self.graph()
        self.assertFalse(
            any(row["id"] == "operation:state.apply" for row in graph["nodes"])
        )
        self.assertFalse(any(row.get("contract_sha256") for row in graph["nodes"]))

    def test_dynamic_declarations_are_explicit_full_fallback(self):
        self.write(
            "server/wakfu_server/combat/combat_operation_registry.py",
            "_CONTRACTS = discover_contracts()\n",
        )
        before = self.graph()
        self.write(
            "server/wakfu_server/combat/combat_operation_registry.py",
            "_CONTRACTS = other_contracts()\n",
        )
        after = self.graph()
        self.assertTrue(
            any(
                row["reason"] == "registry-contract-list-not-literal"
                for row in after["unknowns"]
            )
        )
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            after["module_names"],
        )

    def test_missing_declared_test_does_not_claim_bounded_selection(self):
        self.registry()
        (self.root / "server/tests/test_alpha.py").unlink()
        before = self.graph()
        self.write("server/wakfu_server/combat/alpha.py", "VALUE = 3\n")
        after = self.graph()
        self.assertTrue(
            any(
                row["reason"] == "registry-test-source-unavailable"
                for row in after["unknowns"]
            )
        )
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            after["module_names"],
        )

    def test_retained_capability_and_deleted_edges_keep_consumers(self):
        self.registry(
            'RETAINED_EXECUTION = _contract("fixture.retained", (), "alpha.Handler", (), (), (), (), ("test_alpha",))\n'
        )
        before = self.graph()
        self.registry()
        after = self.graph()
        self.assertTrue(
            any(row["id"] == "operation:fixture.retained" for row in before["nodes"])
        )
        self.assertIn(
            "test_alpha", select_changes(before, after)["selected_module_names"]
        )

    def test_exported_provider_contracts_and_pure_family_source_are_dependencies(self):
        self.registry(
            """
from .combat_subscription_contracts import GROUP_SUBSCRIPTION_FAMILIES
CURRENT_RESOURCE = _contract("fixture.current", (), "alpha.Handler", (), (), (), (), ("test_alpha",))
GROUP_EXECUTION = _contract("fixture.group", (), "beta.Handler", (), (), (), (), ("test_beta",))
OPERATIONS = MappingProxyType({entry.operation_id: entry for entry in
                               (*_CONTRACTS, CURRENT_RESOURCE, GROUP_EXECUTION)})
"""
        )
        self.write(
            "server/wakfu_server/combat/combat_subscription_contracts.py",
            "GROUP_SUBSCRIPTION_FAMILIES = (330,)\n",
        )
        before = self.graph()
        self.assertTrue(
            any(row["id"] == "operation:fixture.current" for row in before["nodes"])
        )
        self.assertTrue(
            any(row["id"] == "operation:fixture.group" for row in before["nodes"])
        )
        self.assertFalse(
            any(row["reason"].startswith("registry-") for row in before["unknowns"])
        )
        self.write(
            "server/wakfu_server/combat/combat_subscription_contracts.py",
            "GROUP_SUBSCRIPTION_FAMILIES = (330, 341)\n",
        )
        selected = select_changes(before, self.graph())["selected_module_names"]
        self.assertIn("test_beta", selected)
        self.assertNotIn("test_unrelated", selected)

    def test_dynamic_export_provider_widens_selection(self):
        self.registry(
            """
OPERATIONS = MappingProxyType({entry.operation_id: entry for entry in (*_CONTRACTS, make_provider())})
"""
        )
        before = self.graph()
        self.write("server/wakfu_server/combat/alpha.py", "VALUE = 4\n")
        after = self.graph()
        self.assertTrue(
            any(
                row["reason"] == "registry-export-provider-unknown"
                for row in after["unknowns"]
            )
        )
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            after["module_names"],
        )

    def test_one_literal_contract_correction_selects_only_its_consumers(self):
        self.registry()
        self.write(
            "server/tests/test_alpha_importer.py",
            "from wakfu_server.alpha import VALUE\n",
        )
        self.write(
            "server/tests/test_global_registry.py",
            "from wakfu_server.combat_operation_registry import OPERATIONS\n",
        )
        self.write(
            "server/tools/fixture_compiler.py",
            "from wakfu_server.combat_operation_registry import OPERATIONS\n",
        )
        self.write(
            "server/tests/test_compiler_integrity.py",
            "from tools.fixture_compiler import OPERATIONS\n",
        )
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(
            path.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", ("required snapshot",),'
            )
        )
        after = self.graph()
        plan = select_changes(before, after)
        # The metadata correction does not change alpha's executor code.
        # Its ordinary runtime importer is not a metadata consumer.
        self.assertEqual(
            plan["selected_module_names"],
            ["test_alpha", "test_compiler_integrity", "test_global_registry"],
        )
        self.assertIn(
            "module:server/tools/fixture_compiler.py",
            plan["registry_integrity_guard_ids"],
        )
        self.assertEqual(
            before["operation_registry"]["common_implementation_sha256"],
            after["operation_registry"]["common_implementation_sha256"],
        )
        self.assertIn("operation:fixture.alpha", plan["changed_node_ids"])
        self.assertNotIn("operation:fixture.beta", plan["changed_node_ids"])

    def test_common_implementation_change_selects_all_contract_consumers(self):
        self.registry()
        before = self.graph()
        self.registry("def schema_revision(): return 2\n")
        after = self.graph()
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            ["test_alpha", "test_beta"],
        )
        self.assertNotEqual(
            before["operation_registry"]["common_implementation_sha256"],
            after["operation_registry"]["common_implementation_sha256"],
        )

    def test_dynamic_contract_metadata_cannot_enable_bounded_selection(self):
        self.registry()
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(
            path.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", calculate_prerequisites(),'
            )
        )
        after = self.graph()
        self.assertIn(
            "registry-contract-metadata-not-literal",
            after["operation_registry"]["errors"],
        )
        self.assertIsNone(after["operation_registry"]["common_implementation_sha256"])
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            after["module_names"],
        )

    def test_duplicate_family_breaks_registry_integrity_and_forces_full_scope(self):
        self.registry()
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(path.read_text().replace("(5000,)", "(5001,)"))
        after = self.graph()
        self.assertIn(
            "registry-duplicate-family:5001", after["operation_registry"]["errors"]
        )
        plan = select_changes(before, after)
        self.assertFalse(plan["registry_metadata_only"])
        self.assertEqual(plan["selected_module_names"], after["module_names"])

    def test_valid_family_reassignment_selects_both_changed_operation_consumers(self):
        self.registry()
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(
            path.read_text().replace("(5000,)", "(5002,)").replace("(5001,)", "(5000,)")
        )
        after = self.graph()
        plan = select_changes(before, after)
        self.assertTrue(plan["registry_metadata_only"])
        self.assertEqual(plan["selected_module_names"], ["test_alpha", "test_beta"])
        self.assertFalse(after["operation_registry"]["errors"])

    def test_metadata_only_keeps_reached_private_uncertainty_without_unrelated_env_fanout(
        self,
    ):
        self.registry()
        self.write(
            "server/tests/test_alpha.py", "import os\nos.getenv('ALPHA_TOKEN')\n"
        )
        self.write(
            "server/tests/test_unrelated.py",
            "import os\nos.getenv('UNRELATED_TOKEN')\n",
        )
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(
            path.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", ("required snapshot",),'
            )
        )
        plan = select_changes(before, self.graph())
        self.assertEqual(plan["selected_module_names"], ["test_alpha"])
        self.assertTrue(
            any(
                row["owner"] == "module:server/tests/test_alpha.py"
                and row["domain"] == "environment-private"
                for row in plan["unknowns"]
            )
        )
        self.assertFalse(
            any(
                row["owner"] == "module:server/tests/test_unrelated.py"
                for row in plan["unknowns"]
            )
        )

    def test_metadata_catalog_reader_uncertainty_scopes_to_consumer_when_inputs_unchanged(
        self,
    ):
        self.registry()
        self.write(
            "server/wakfu_server/storage/native_catalog.py", "def _database(): pass\n"
        )
        self.write(
            "server/tools/fixture_compiler.py",
            "from wakfu_server.combat_operation_registry import OPERATIONS\nimport wakfu_server.native_catalog as native_catalog\nnative_catalog._database()\n",
        )
        self.write(
            "server/tests/test_compiler_integrity.py",
            "from tools.fixture_compiler import OPERATIONS\n",
        )
        before = self.graph()
        path = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        path.write_text(
            path.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", ("required snapshot",),'
            )
        )
        after = self.graph()
        plan = select_changes(before, after)
        self.assertEqual(
            plan["selected_module_names"], ["test_alpha", "test_compiler_integrity"]
        )
        self.assertTrue(
            any(
                row["reason"] == "direct-catalog-sql"
                and row["scope"] == "owner-consumers"
                for row in plan["fallbacks"]
            )
        )
        self.catalog["sha256"] = "b" * 64
        changed_inputs = self.graph()
        broad = select_changes(before, changed_inputs)
        self.assertFalse(broad["registry_metadata_only"])
        self.assertEqual(broad["selected_module_names"], changed_inputs["module_names"])

    def test_researched_interaction_is_selected_and_stale_source_widens(self):
        self.registry()
        path = "server/tests/test_researched_state_resource.py"
        self.write(
            path,
            "import unittest\nclass Research(unittest.TestCase):\n def test_native_sequence(self): self.assertEqual(1, 1)\n",
        )
        interactions = [
            {
                "id": "resource-state-sequence",
                "status": "source-bound-interaction",
                "operation_ids": ["fixture.alpha"],
                "source_ids": ["published-player-guide"],
                "scope": "Native interaction segment; selection metadata only",
                "test_dependencies": [
                    {
                        "path": path,
                        "source_sha256": hashlib.sha256(
                            (self.root / path).read_bytes()
                        ).hexdigest(),
                        "assertion_witnesses": ["Research.test_native_sequence"],
                    }
                ],
            }
        ]
        before = self.graph(interactions)
        registry = self.root / "server/wakfu_server/combat/combat_operation_registry.py"
        registry.write_text(
            registry.read_text().replace(
                '"alpha.Handler", (),', '"alpha.Handler", ("required snapshot",),'
            )
        )
        after = self.graph(interactions)
        self.assertEqual(
            select_changes(before, after)["selected_module_names"],
            ["test_alpha", "test_researched_state_resource"],
        )
        self.assertFalse(after["operation_interaction_errors"])
        interactions[0]["test_dependencies"][0]["source_sha256"] = "0" * 64
        invalid = self.graph(interactions)
        self.assertTrue(invalid["operation_interaction_errors"])
        self.assertEqual(
            select_changes(before, invalid)["selected_module_names"],
            invalid["module_names"],
        )

    def test_missing_researched_operation_or_assertion_is_not_silently_accepted(self):
        self.registry()
        self.write(
            "server/tests/test_alpha.py",
            "import unittest\nclass Alpha(unittest.TestCase):\n def test_exists(self): pass\n",
        )
        path = "server/tests/test_alpha.py"
        row = {
            "id": "invalid-research",
            "status": "source-bound-interaction",
            "operation_ids": ["fixture.missing"],
            "source_ids": ["guide"],
            "scope": "Source selection only",
            "test_dependencies": [
                {
                    "path": path,
                    "source_sha256": hashlib.sha256(
                        (self.root / path).read_bytes()
                    ).hexdigest(),
                    "assertion_witnesses": ["Alpha.test_missing"],
                }
            ],
        }
        graph = self.graph([row])
        self.assertTrue(
            any(
                "interaction-operation-unavailable" in value
                for value in graph["operation_interaction_errors"]
            )
        )
        self.assertTrue(
            any(
                "interaction-test-witness-missing" in value
                for value in graph["operation_interaction_errors"]
            )
        )
