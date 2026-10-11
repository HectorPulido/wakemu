"""NPC rollout scopes imported effects while preserving existing ownership."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
import sys
from pathlib import Path
import hashlib
import json
import tempfile
from contextlib import ExitStack
from unittest.mock import Mock, patch

from wakfu_server.combat.combat_npc_activation import imports_enabled

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_monster_spell_activation import merge_npc, merge_records, select_candidates
from validate_monster_spell_activation import (
    install_overlay,
    validate_receipt_context,
    changed_hashes,
    test_dependency_files,
)


class MonsterSpellActivationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "schema": "native-npc-activation-v1",
            "legacy_spell_ids": [7962],
            "enabled_monsters": {
                "2616": {"min_level": 4, "max_level": 6, "spell_ids": [1774, 3803]}
            },
        }
        self.owned = {1774: 5, 3803: 5, 9999: 5}

    def test_absent_policy_preserves_existing_unscoped_catalogs(self):
        self.assertTrue(imports_enabled(None, 2616, 5, 1774))

    def test_enabled_monster_uses_only_allowlisted_imports_without_mutation(self):
        before = deepcopy(self.policy)
        self.assertTrue(imports_enabled(self.policy, 2616, 5, 1774))
        self.assertTrue(imports_enabled(self.policy, 2616, 5, 3803))
        self.assertFalse(imports_enabled(self.policy, 2616, 5, 9999))
        self.assertEqual(self.policy, before)

    def test_inclusive_native_level_bounds_do_not_enable_neighbors(self):
        for level in (4, 6):
            with self.subTest(level=level):
                self.assertTrue(imports_enabled(self.policy, 2616, level, 1774))
        for level in (3, 7, 100, 230):
            with self.subTest(level=level):
                self.assertFalse(imports_enabled(self.policy, 2616, level, 1774))

    def test_unknown_monsters_and_epics_do_not_use_imported_effects(self):
        for reference in (1, 42, 999999):
            with self.subTest(reference=reference):
                self.assertFalse(imports_enabled(self.policy, reference, 5, 1774))

    def test_legacy_spell_uses_original_catalog_without_import_authority(self):
        for reference, level in ((5525, 1), (2616, 100), (999999, 230)):
            with self.subTest(reference=reference, level=level):
                self.assertFalse(imports_enabled(self.policy, reference, level, 7962))

    def test_malformed_policy_is_rejected_instead_of_enabling_everything(self):
        invalid = [
            {},
            {**self.policy, "schema": "unknown"},
            {**self.policy, "legacy_spell_ids": "7962"},
            {**self.policy, "legacy_spell_ids": [True]},
            {**self.policy, "legacy_spell_ids": ["7962"]},
            {**self.policy, "enabled_monsters": []},
            {**self.policy, "enabled_monsters": {"2616": {"spell_ids": [1774]}}},
            {
                **self.policy,
                "enabled_monsters": {
                    "2616": {"min_level": 6, "max_level": 4, "spell_ids": [1774]}
                },
            },
            {
                **self.policy,
                "enabled_monsters": {
                    "2616": {"min_level": True, "max_level": 4, "spell_ids": [1774]}
                },
            },
            {
                **self.policy,
                "enabled_monsters": {
                    "2616": {"min_level": 0, "max_level": 4, "spell_ids": [1774]}
                },
            },
            {
                **self.policy,
                "enabled_monsters": {
                    "2616": {"min_level": 4, "max_level": 6, "spell_ids": [True]}
                },
            },
        ]
        for policy in invalid:
            with self.subTest(policy=policy):
                with self.assertRaises(ValueError):
                    imports_enabled(policy, 2616, 5, 1774)


class NpcOwnedSpellActivationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=-200, controlled=False, hp=50, effective_level=5
        )
        self.fight = SimpleNamespace(current=self.actor)
        self.monsters = {-200: {"id": -200, "ref": 2616, "level": 99}}
        self.abilities = [
            {"spell_id": 1774, "spell_level": 5},
            {"spell_id": 3803, "spell_level": 2},
            {"spell_id": 9999, "spell_level": 5},
        ]
        self.policy = {
            "schema": "native-npc-activation-v1",
            "legacy_spell_ids": [],
            "enabled_monsters": {
                "2616": {"min_level": 4, "max_level": 6, "spell_ids": [1774, 3803]}
            },
        }

    def owned(self, policy, grants=None):
        from wakfu_server.combat.combat_npc_spell import owned_spells

        native = Mock(return_value=self.abilities)
        modules = {
            "wakfu_server.monsters": SimpleNamespace(native_abilities=native),
            "wakfu_server.combat.combat_npc_attack": SimpleNamespace(
                npc_spell_catalog=lambda: {"activation_policy": policy}
            ),
            "wakfu_server.combat.combat_spell_grant": SimpleNamespace(
                granted_spells=lambda fight, actor_id: grants or {}
            ),
        }
        with patch.dict(sys.modules, modules):
            result = owned_spells(self.fight, self.monsters)
        native.assert_called_once_with(
            self.monsters[-200]["ref"], self.actor.effective_level
        )
        return result

    def test_policy_preserves_all_native_ownership_and_fixed_spell_levels(self):
        self.assertEqual(self.owned(self.policy), {1774: 5, 3803: 2, 9999: 5})

    def test_native_temporary_grants_remain_available_with_scoped_imports(self):
        self.assertEqual(
            self.owned(self.policy, {123: {"uid": 123, "level": 3}}),
            {1774: 5, 3803: 2, 9999: 5, 123: 3},
        )

    def test_absent_policy_preserves_existing_native_and_granted_spell_behavior(self):
        self.assertEqual(
            self.owned(None, {123: {"uid": 123, "level": 3}}),
            {1774: 5, 3803: 2, 9999: 5, 123: 3},
        )

    def test_unknown_high_level_monster_keeps_existing_owned_spells_and_grants(self):
        self.monsters[-200]["ref"] = 999999
        self.actor.effective_level = 230
        self.assertEqual(
            self.owned(self.policy, {123: {"uid": 123, "level": 3}}),
            {1774: 5, 3803: 2, 9999: 5, 123: 3},
        )
        self.assertFalse(imports_enabled(self.policy, 999999, 230, 123))

    def test_mismatched_temporary_spell_uid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "temporary spell UID"):
            self.owned(self.policy, {123: {"uid": 456, "level": 3}})

    def test_player_actor_is_rejected_before_any_npc_catalog_read(self):
        from wakfu_server.combat.combat_npc_spell import owned_spells

        self.actor.controlled = True
        catalog = Mock()
        modules = {
            "wakfu_server.monsters": SimpleNamespace(native_abilities=Mock()),
            "wakfu_server.combat.combat_npc_attack": SimpleNamespace(
                npc_spell_catalog=catalog
            ),
        }
        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ValueError, "current owned NPC"):
                owned_spells(self.fight, self.monsters)
        catalog.assert_not_called()


class NpcCatalogPreservationTests(unittest.TestCase):
    def catalog(self, document, imported):
        # Load the actual pure catalog boundary without importing game services.
        import ast
        from functools import lru_cache

        path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/combat/combat_npc_attack.py"
        )
        tree = ast.parse(path.read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "npc_runtime_catalog"
        )
        namespace = {
            "lru_cache": lru_cache,
            "__package__": "wakfu_server.combat",
            "npc_spell_catalog": lambda: document,
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"),
            namespace,
        )
        attack = SimpleNamespace(npc_runtime_catalog=namespace["npc_runtime_catalog"])
        merge_path = path.with_name("combat_effect_runtime.py")
        merge_tree = ast.parse(merge_path.read_text())
        merge_function = next(
            node
            for node in merge_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_merge_effects"
        )
        merge_namespace = {}
        exec(
            compile(
                ast.Module(body=[merge_function], type_ignores=[]),
                str(merge_path),
                "exec",
            ),
            merge_namespace,
        )
        base = SimpleNamespace(
            source_effects={"class-root": {"effect_class": "class"}},
            source_states={"effects": {}},
        )
        modules = {
            "wakfu_server.combat.combat_effect_runtime": SimpleNamespace(
                _merge_effects=merge_namespace["_merge_effects"]
            ),
            "wakfu_server.combat.combat_server_spell": SimpleNamespace(
                compiled_runtime_catalog=lambda: base
            ),
            "wakfu_server.combat.combat_static_catalogs": SimpleNamespace(
                CompiledEffects=lambda effects, states: SimpleNamespace(
                    effects=effects, source_states=states
                )
            ),
        }
        attack.npc_runtime_catalog.cache_clear()
        try:
            with patch.dict(sys.modules, modules):
                return attack.npc_runtime_catalog(imported=imported)
        finally:
            attack.npc_runtime_catalog.cache_clear()

    def test_original_catalog_preserves_class_and_existing_npc_roots(self):
        document = {
            "activation_policy": {},
            "baseline_effects": {"old-npc": {"effect_class": "old"}},
            "effects": {
                "old-npc": {"effect_class": "old"},
                "new-npc": {"effect_class": "new"},
            },
        }
        before = deepcopy(document)
        original = self.catalog(document, False)
        expanded = self.catalog(document, True)
        self.assertEqual(set(original.effects), {"class-root", "old-npc"})
        self.assertEqual(set(expanded.effects), {"class-root", "old-npc", "new-npc"})
        self.assertEqual(document, before)

    def test_pre_policy_catalog_remains_available_without_baseline_field(self):
        original = self.catalog(
            {"effects": {"old-npc": {"effect_class": "old"}}}, False
        )
        self.assertEqual(set(original.effects), {"class-root", "old-npc"})

    def test_scoped_catalog_without_preserved_baseline_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "preserved native NPC baseline"):
            self.catalog({"activation_policy": {}, "effects": {}}, False)


class MonsterActivationCandidateTests(unittest.TestCase):
    def setUp(self):
        self.mob = dict(
            ref=2616,
            min_level=4,
            max_level=6,
            status="covered",
            spell_ids=[1774, 3803],
            data_gaps=[],
            missing_families=[],
        )

    def test_selector_excludes_partial_ranges_high_levels_and_uncertain_coverage(self):
        rejected = [
            dict(self.mob, max_level=10),
            dict(self.mob, min_level=1, max_level=230),
            dict(self.mob, min_level=0),
            dict(self.mob, min_level=7, max_level=6),
            dict(self.mob, status="almost"),
            dict(self.mob, spell_ids=[]),
            dict(self.mob, data_gaps=["unknown effect"]),
            dict(self.mob, missing_families=[330]),
        ]
        edge = dict(self.mob, ref=2, max_level=9)
        coverage = {"monsters": [self.mob, edge, *rejected]}
        original = deepcopy(coverage)
        self.assertEqual(select_candidates(coverage), [self.mob, edge])
        self.assertEqual(coverage, original)

    def test_existing_class_definitions_are_preserved_and_conflicts_rejected(self):
        original = {"class-root": {"selector": [1, 2], "metadata": "class"}}
        before = deepcopy(original)
        merged = merge_records(original, {"npc-root": {"selector": [3]}})
        self.assertEqual(merged["class-root"], before["class-root"])
        self.assertEqual(original, before)
        with self.assertRaisesRegex(ValueError, "Conflicting existing"):
            merge_records(original, {"class-root": {"selector": [9]}})

    def test_first_rollout_keeps_existing_npc_spells_legacy_and_does_not_grant_others(
        self,
    ):
        existing = {
            "schema": "native-trees",
            "spells": {"7962": {"levels": []}},
            "effects": {"old": {"effect_class": 3}},
            "metadata": "preserve",
        }
        exported = {
            "spells": {"1774": {"levels": []}},
            "effects": {"new": {"effect_class": 3}},
        }
        before = deepcopy((existing, exported))
        result = merge_npc(existing, exported, [self.mob])
        self.assertEqual((existing, exported), before)
        self.assertEqual(result["metadata"], "preserve")
        self.assertEqual(result["spells"]["7962"], existing["spells"]["7962"])
        self.assertEqual(result["activation_policy"]["legacy_spell_ids"], [7962])
        self.assertFalse(imports_enabled(result["activation_policy"], 42, 230, 1774))
        self.assertEqual(result["baseline_effects"], existing["effects"])

    def test_incremental_rollout_keeps_previous_policy_without_promoting_imports_to_legacy(
        self,
    ):
        existing = {
            "spells": {"7962": {}, "111": {}},
            "effects": {},
            "activation_policy": {
                "schema": "native-npc-activation-v1",
                "legacy_spell_ids": [7962],
                "enabled_monsters": {
                    "2": {"min_level": 4, "max_level": 8, "spell_ids": [111]}
                },
            },
        }
        before = deepcopy(existing)
        result = merge_npc(existing, {"spells": {}, "effects": {}}, [self.mob])
        self.assertEqual(existing, before)
        self.assertEqual(result["activation_policy"]["legacy_spell_ids"], [7962])
        self.assertEqual(
            set(result["activation_policy"]["enabled_monsters"]), {"2", "2616"}
        )
        self.assertFalse(imports_enabled(result["activation_policy"], 42, 230, 111))

    def test_longer_fresh_native_levels_preserve_exact_existing_spell_and_prefix(self):
        old = {
            "7962": {
                "levels": [[1, 1, [361119]], [2, 1, [361119]]],
                "class_metadata": "keep",
            }
        }
        fresh = {
            "7962": {"levels": [[1, 1, [361119]], [2, 1, [361119]], [3, 1, [361119]]]}
        }
        before = deepcopy((old, fresh))
        merged = merge_records(old, fresh)
        self.assertEqual(merged, old)
        self.assertEqual((old, fresh), before)
        fresh["7962"]["levels"][1][2] = [999]
        with self.assertRaisesRegex(ValueError, "Conflicting existing"):
            merge_records(old, fresh)

    def test_shorter_matching_export_does_not_truncate_existing_levels(self):
        old = {"7962": {"levels": [[1, 1, [361119]], [2, 1, [361119]]]}}
        merged = merge_records(old, {"7962": {"levels": [[1, 1, [361119]]]}})
        self.assertEqual(merged, old)

    def test_effect_merge_preserves_opaque_metadata_and_rejects_semantic_changes(self):
        old = {
            "361119": {
                "effect_class": 3,
                "parameters": [[5, 5]],
                "opaque_native": {"particle": 17},
            }
        }
        extra = deepcopy(old)
        extra["361119"]["opaque_native"]["particle"] = 18
        with self.assertRaisesRegex(ValueError, "Conflicting existing"):
            merge_records(old, extra, effects=True)
        extra = deepcopy(old)
        extra["361119"]["parameters"] = [[6, 6]]
        with self.assertRaisesRegex(ValueError, "Conflicting existing"):
            merge_records(old, extra, effects=True)
        self.assertEqual(merge_records(old, deepcopy(old), effects=True), old)


class ReadOnlyActivationOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.documents = {
            "native-npc-spell-effect-trees.json": {"source": "candidate-npc"},
            "native-class-casting-roots.json": {"source": "candidate-roots"},
            "native-spell-resource-costs.json": {"source": "source-cost-dependency"},
        }

    def write_candidate(self):
        hashes = {}
        for name, document in self.documents.items():
            raw = json.dumps(document).encode()
            (self.directory / name).write_bytes(raw)
            hashes[name] = hashlib.sha256(raw).hexdigest()
        manifest = dict(
            base_revision="base",
            changed_documents=hashes,
            unchanged_documents={"spell-effect-trees.json": "class-sha"},
        )
        (self.directory / "manifest.json").write_text(json.dumps(manifest))

    def run_overlay(self, *, overlay=True, hashes=None):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        self.write_candidate()
        with ExitStack() as stack:
            for name in ("load", "_redis"):
                stack.enter_context(
                    patch.object(native_catalog, name, return_value={"source": "base"})
                )
            stack.enter_context(
                patch.object(
                    native_catalog, "read_bytes", return_value=b'{"source":"base"}'
                )
            )
            stack.enter_context(
                patch.object(native_catalog, "release", return_value="base")
            )
            stack.enter_context(
                patch.object(
                    native_catalog,
                    "document_hashes",
                    return_value=hashes
                    or {
                        "spell-effect-trees.json": "class-sha",
                        "native-npc-spell-effect-trees.json": hashlib.sha256(
                            b'{"source":"base"}'
                        ).hexdigest(),
                        "native-class-casting-roots.json": hashlib.sha256(
                            b'{"source":"base"}'
                        ).hexdigest(),
                    },
                )
            )
            install_overlay(self.directory, overlay=overlay)
            return {
                name: native_catalog.load(DATA_ROOT / name)
                for name in (*self.documents, "spell-effect-trees.json")
            }

    def test_candidate_overlay_preserves_class_catalog_reads(self):
        actual = self.run_overlay()
        self.assertEqual(
            actual["native-npc-spell-effect-trees.json"],
            self.documents["native-npc-spell-effect-trees.json"],
        )
        self.assertEqual(actual["spell-effect-trees.json"], {"source": "base"})

    def test_baseline_applies_only_shared_required_resource_dependency(self):
        actual = self.run_overlay(overlay=False)
        self.assertEqual(
            actual["native-spell-resource-costs.json"],
            self.documents["native-spell-resource-costs.json"],
        )
        self.assertEqual(
            actual["native-npc-spell-effect-trees.json"], {"source": "base"}
        )
        self.assertEqual(actual["native-class-casting-roots.json"], {"source": "base"})

    def test_overlay_rejects_any_other_document_or_changed_class_catalog(self):
        self.documents["spell-effect-trees.json"] = {"source": "forbidden"}
        with self.assertRaisesRegex(ValueError, "overlay scope"):
            self.run_overlay()
        del self.documents["spell-effect-trees.json"]
        with self.assertRaisesRegex(ValueError, "Shared catalog differs"):
            self.run_overlay(hashes={"spell-effect-trees.json": "changed-class-sha"})


class ValidationReceiptFenceTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(
            candidate_manifest_sha256="candidate",
            changed_document_hashes={"npc": "candidate-npc"},
            base_revision="active",
            base_document_hashes={"npc": "old-npc"},
            runtime_code_sha256={"engine": "current"},
            native_monsters_sha256="source-monsters",
            validator_sha256="harness",
            test_code_sha256={"regression": "fixture-authority"},
            test_scope=["selected_regression"],
        )

    def test_unchanged_context_can_resume_without_modifying_evidence(self):
        before = deepcopy(self.context)
        validate_receipt_context(deepcopy(self.context), self.context)
        self.assertEqual(self.context, before)

    def test_every_authority_change_or_missing_fence_rejects_reuse(self):
        for field in self.context:
            for missing in (False, True):
                with self.subTest(field=field, missing=missing):
                    previous = deepcopy(self.context)
                    if missing:
                        del previous[field]
                    else:
                        previous[field] = "different-authority"
                    with self.assertRaisesRegex(ValueError, field):
                        validate_receipt_context(previous, self.context)

    def test_added_deleted_and_modified_runtime_files_are_detected(self):
        before = {"unchanged.py": "same", "changed.py": "old", "deleted.py": "old"}
        after = {"unchanged.py": "same", "changed.py": "new", "added.py": "new"}
        original = deepcopy((before, after))
        self.assertEqual(
            changed_hashes(before, after), ["added.py", "changed.py", "deleted.py"]
        )
        self.assertEqual((before, after), original)
        self.assertEqual(changed_hashes(before, deepcopy(before)), [])

    def test_added_or_removed_test_fixture_prevents_reusing_receipt(self):
        for fixtures in ({}, {"regression": "fixture-authority", "new": "new-fixture"}):
            with self.subTest(fixtures=fixtures):
                current = deepcopy(self.context)
                current["test_code_sha256"] = fixtures
                with self.assertRaisesRegex(ValueError, "test_code_sha256"):
                    validate_receipt_context(self.context, current)


class RegressionDependencyDiscoveryTests(unittest.TestCase):
    def test_transitive_fixtures_tools_and_relative_imports_exclude_unrelated_tests(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests, tools = root / "server/tests", root / "server/tools"
            tests.mkdir(parents=True)
            tools.mkdir(parents=True)
            sources = {
                tests
                / "test_selected.py": "import native_fixture\nfrom helper import prepare\n",
                tests / "native_fixture.py": "from . import deeper_fixture\n",
                tests / "deeper_fixture.py": "VALUE = 1\n",
                tools / "helper.py": "import finalize_helper\n",
                tools / "finalize_helper.py": "VALUE = 2\n",
                tests / "test_unrelated.py": "raise RuntimeError('must not import')\n",
            }
            for path, source in sources.items():
                path.write_text(source)
            found = test_dependency_files(root, ["test_selected"])
            self.assertEqual(set(found), set(sources) - {tests / "test_unrelated.py"})
            (tests / "test_unrelated.py").write_text("changed = True\n")
            self.assertEqual(found, test_dependency_files(root, ["test_selected"]))
            with self.assertRaisesRegex(ValueError, "Missing selected"):
                test_dependency_files(root, ["test_missing"])


if __name__ == "__main__":
    unittest.main()
