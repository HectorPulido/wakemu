"""Static input precision must retain unknowns rather than invent authority."""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.combat_test_impact import (
    _data_path,
    _finite_environment_reads,
    _lexical_bindings,
    build_graph,
    select_changes,
)


class ImpactInputPrecisionTests(unittest.TestCase):
    def parsed(self, source):
        tree = ast.parse(source)
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        bindings = {
            target.id: assignment.value
            for assignment in tree.body
            if isinstance(assignment, ast.Assign)
            for target in assignment.targets
            if isinstance(target, ast.Name)
        }
        call = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("getenv", "get", "read_text")
        )
        return tree, parents, bindings, call

    def test_local_source_path_has_exact_dependency(self):
        tree, parents, bindings, call = self.parsed(
            'def test():\n source=Path(__file__).resolve().parents[1]/"local_game_server.py"\n return source.read_text()\n'
        )
        local = _lexical_bindings(tree, call, parents, bindings)
        self.assertEqual(
            _data_path(call.func.value, "server/tests/test_ready.py", local),
            "server/local_game_server.py",
        )

    def test_branch_reassignment_and_parameter_shadow_stay_unknown(self):
        for source in (
            'source=Path(__file__).parents[1]/"local_game_server.py"\nreader=lambda source:source.read_text()\n',
            'source=Path(__file__).parents[1]/"local_game_server.py"\ndef reader():\n from other import source\n return source.read_text()\n',
            'source=Path(__file__).parents[1]/"local_game_server.py"\ndef reader():\n import other as source\n return source.read_text()\n',
            'source=Path(__file__).parents[1]/"local_game_server.py"\nif flag:\n source=other\nvalue=source.read_text()\n',
            'source=Path(__file__).parents[1]/"local_game_server.py"\ndef test(source):\n return source.read_text()\n',
            'def test():\n source=Path(__file__).parents[1]/"local_game_server.py"\n if flag:\n  source=other\n return source.read_text()\n',
        ):
            with self.subTest(source=source):
                tree, parents, bindings, call = self.parsed(source)
                self.assertIsNone(
                    _data_path(
                        call.func.value,
                        "server/tests/test_ready.py",
                        _lexical_bindings(tree, call, parents, bindings),
                    )
                )

    def finite(self, source, imports=None, root=None):
        tree, parents, bindings, call = self.parsed(source)
        return _finite_environment_reads(
            call, tree, parents, bindings, imports or {}, root or Path.cwd()
        )

    def test_literal_loop_policy_names_expand_without_execution(self):
        self.assertEqual(
            self.finite(
                'for name,default in (("A","1"),("B","0")):\n value=os.getenv(name,default)\n'
            ),
            [("A", "1"), ("B", "0")],
        )
        self.assertEqual(
            self.finite(
                'for name,default in (("world","x"),("shop","y")):\n value=os.getenv("WAKFU_"+name.upper()+"_URL",default)\n'
            ),
            [("WAKFU_SHOP_URL", "y"), ("WAKFU_WORLD_URL", "x")],
        )

    def test_imported_mutable_policy_maps_remain_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policies.py").write_text('POLICIES={"A":"1","B":"0"}\n')
            source = "value={name:os.getenv(name,default) for name,default in POLICIES.items()}\n"
            self.assertIsNone(
                self.finite(source, {"POLICIES": [("policies.py", "POLICIES")]}, root)
            )
            (root / "policies.py").write_text('POLICIES={"A":"1"}\nPOLICIES["B"]="0"\n')
            self.assertIsNone(
                self.finite(source, {"POLICIES": [("policies.py", "POLICIES")]}, root)
            )

    def test_dynamic_mutated_and_reassigned_names_stay_unknown(self):
        for source in (
            "def read(name):\n return os.getenv(name)\n",
            'POLICIES={"A":"1"}\nPOLICIES["B"]="0"\nvalue={name:os.getenv(name,default) for name,default in POLICIES.items()}\n',
            'for name in ("A",):\n name=dynamic()\n value=os.getenv(name)\n',
            "for name in dynamic():\n value=os.getenv(name)\n",
        ):
            with self.subTest(source=source):
                self.assertIsNone(self.finite(source))

    def graphs(self, *, before_environment, after_environment, edit=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(path, source):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)

            write("server/tools/combat_validation_profile.py", "# fixture\n")
            write(
                "server/wakfu_server/private_user.py",
                'import os\nVALUE=os.getenv("WAKFU_FIXTURE_TOKEN_FILE")\n',
            )
            write(
                "server/tests/test_private_user.py",
                "from wakfu_server.private_user import VALUE\n",
            )
            write("server/tests/test_unrelated.py", "VALUE=1\n")
            catalog = dict(
                status="published",
                revision="fixture",
                documents={},
                sha256="a" * 64,
                publication_verified=True,
            )
            with patch(
                "tools.combat_test_impact.environment_manifest",
                return_value={"sha256": "e" * 64},
            ):
                with patch.dict("os.environ", before_environment, clear=True):
                    before = build_graph(root, catalog_inventory=catalog)
                if edit:
                    write(
                        "server/wakfu_server/private_user.py",
                        'import os\nVALUE=os.getenv("WAKFU_FIXTURE_TOKEN_FILE")\nCHANGED=True\n',
                    )
                with patch.dict("os.environ", after_environment, clear=True):
                    after = build_graph(root, catalog_inventory=catalog)
            return before, after

    def test_known_absent_private_key_does_not_select_unchanged_consumers(self):
        before, after = self.graphs(before_environment={}, after_environment={})
        plan = select_changes(before, after)
        self.assertEqual(plan["selected_module_names"], [])
        self.assertEqual(plan["source_impacted_module_names"], [])
        self.assertFalse(plan["source_workflow"]["reuse_qualified"])

    def test_private_presence_change_or_present_values_remain_conservative(self):
        for before_env, after_env in (
            ({}, {"WAKFU_FIXTURE_TOKEN_FILE": "opaque"}),
            ({"WAKFU_FIXTURE_TOKEN_FILE": "old"}, {"WAKFU_FIXTURE_TOKEN_FILE": "new"}),
        ):
            before, after = self.graphs(
                before_environment=before_env, after_environment=after_env
            )
            plan = select_changes(before, after)
            self.assertIn("test_private_user", plan["selected_module_names"])
            self.assertEqual(plan["source_impacted_module_names"], [])
            self.assertTrue(plan["source_workflow"]["environment_uncertainty"])
            self.assertFalse(plan["source_workflow"]["reuse_qualified"])
            rendered = str((before, after, plan))
            self.assertNotIn("'opaque'", rendered)
            self.assertNotIn("'old'", rendered)
            self.assertNotIn("'new'", rendered)

    def test_changed_absent_private_consumer_remains_selected(self):
        before, after = self.graphs(
            before_environment={}, after_environment={}, edit=True
        )
        self.assertIn(
            "test_private_user", select_changes(before, after)["selected_module_names"]
        )

    def test_outer_closure_shadow_and_nested_nonlocal_mutator_stay_unknown(self):
        for source in (
            'source=Path(__file__).parents[1]/"local_game_server.py"\ndef outer(source):\n def inner():\n  return source.read_text()\n',
            'def outer():\n source=Path(__file__).parents[1]/"local_game_server.py"\n def mutate():\n  nonlocal source\n  source=other\n mutate()\n return source.read_text()\n',
        ):
            with self.subTest(source=source):
                tree, parents, bindings, call = self.parsed(source)
                self.assertIsNone(
                    _data_path(
                        call.func.value,
                        "server/tests/test_ready.py",
                        _lexical_bindings(tree, call, parents, bindings),
                    )
                )

    def test_exporter_and_consumer_policy_alias_escapes_stay_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "policies.py"
            imported = {"POLICIES": [("policies.py", "POLICIES")]}
            target.write_text('POLICIES={"A":"1"}\n')
            for prefix in (
                'POLICIES["B"]="0"\n',
                'alias=POLICIES\nalias["B"]="0"\n',
                'holder=[POLICIES]\nholder[0]["B"]="0"\n',
                'holder={"p":POLICIES}\nholder["p"]["B"]="0"\n',
                "mutate(POLICIES)\n",
            ):
                source = (
                    prefix
                    + "value={name:os.getenv(name,default) for name,default in POLICIES.items()}\n"
                )
                self.assertIsNone(self.finite(source, imported, root))
            target.write_text('POLICIES={"A":"1"}\nalias=POLICIES\nalias["B"]="0"\n')
            self.assertIsNone(
                self.finite(
                    "value={name:os.getenv(name,default) for name,default in POLICIES.items()}\n",
                    imported,
                    root,
                )
            )

    def test_comprehension_policy_variables_have_their_own_scope(self):
        source = 'POLICIES=(("A","1"),)\ndef capture():\n before={name:value for name,value in (("other","0"),)}\n return {name:os.getenv(name,default) for name,default in POLICIES}\n'
        self.assertEqual(self.finite(source), [("A", "1")])
