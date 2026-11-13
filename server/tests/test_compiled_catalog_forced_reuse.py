"""Explicit catalog reuse must never weaken source or config pins."""

from contextlib import contextmanager
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import select_existing_compiled_catalog as selector
from wakfu_server import native_compiled_catalog as catalog


class ForcedCatalogReuseTests(unittest.TestCase):
    def setUp(self):
        self.identity = {
            "policy": catalog.PUBLICATION_POLICY,
            "source_revision": "a" * 64,
            "source_inventory_sha256": "b" * 64,
            "compiler_contract_sha256": "c" * 64,
            "config_sha256": "d" * 64,
        }
        self.generation = "e" * 64
        self.manifest = dict(self.identity, collections={})
        self.manifest["compiler_contract_sha256"] = "f" * 64
        self.queries = []
        owner = self

        class Store:
            @contextmanager
            def connection(self):
                yield self

            def execute(self, query, params):
                owner.queries.append((query, params))
                return self

            def fetchall(self):
                return [{"generation": owner.generation}]

            def header(self, generation):
                owner.assertEqual(generation, owner.generation)
                return owner.manifest

        self.store = Store()

    def resolve(self, flag, **kwargs):
        env = {"WAKFU_COMPILED_CATALOG_REUSE_EXISTING": flag}
        with patch.dict("os.environ", env, clear=True), patch.object(
            catalog, "expected_publication_identity", return_value=self.identity
        ), patch.object(catalog, "_store", return_value=self.store):
            return catalog.resolve_publication(source_revision="a" * 64, **kwargs)

    def test_opt_in_reuses_complete_generation_despite_compiler_change(self):
        self.assertEqual(self.resolve("1")["generation"], self.generation)
        self.assertNotIn("compiler_contract_sha256=%s", self.queries[0][0])

    def test_default_mode_never_accepts_compiler_change(self):
        with self.assertRaisesRegex(ValueError, "Pinned compiled publication differs"):
            self.resolve("0", generation=self.generation)

    def test_unset_flag_keeps_strict_compiler_pin(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(
            catalog, "expected_publication_identity", return_value=self.identity
        ), patch.object(catalog, "_store", return_value=self.store):
            with self.assertRaisesRegex(
                ValueError, "Pinned compiled publication differs"
            ):
                catalog.resolve_publication(
                    source_revision="a" * 64, generation=self.generation
                )

    def test_other_pins_remain_strict_in_reuse_mode(self):
        for field in (
            "policy",
            "source_revision",
            "source_inventory_sha256",
            "config_sha256",
        ):
            with self.subTest(field=field):
                before = self.manifest[field]
                self.manifest[field] = "0" * 64
                with self.assertRaisesRegex(
                    ValueError, "Pinned compiled publication differs"
                ):
                    self.resolve("1", generation=self.generation)
                self.manifest[field] = before

    def test_explicit_compiler_or_config_requirement_cannot_be_bypassed(self):
        for field in ("compiler_contract_sha256", "config_sha256"):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "Expected compiled publication pin differs"
            ):
                self.resolve("1", generation=self.generation, **{field: "0" * 64})

    def test_invalid_flag_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "must be 0 or 1"):
            self.resolve("true")

    def test_missing_publication_fails_closed(self):
        self.store.fetchall = lambda: []
        with self.assertRaisesRegex(
            RuntimeError, "No compatible complete compiled publication"
        ):
            self.resolve("1")


class ExistingCatalogSelectorTests(unittest.TestCase):
    def test_selector_requires_explicit_opt_in(self):
        for flag in ("0", "true", ""):
            with self.subTest(flag=flag), patch.dict(
                "os.environ",
                {"WAKFU_COMPILED_CATALOG_REUSE_EXISTING": flag},
                clear=True,
            ), patch.object(selector, "resolve_publication") as resolve:
                with self.assertRaises(SystemExit):
                    selector.main()
                resolve.assert_not_called()

    def test_selector_emits_existing_generation_and_warning(self):
        out, err = io.StringIO(), io.StringIO()
        generation = "e" * 64
        with patch.dict(
            "os.environ", {"WAKFU_COMPILED_CATALOG_REUSE_EXISTING": "1"}, clear=True
        ), patch.object(
            selector.native_catalog, "release", return_value="a" * 64
        ), patch.object(
            selector, "resolve_publication", return_value={"generation": generation}
        ) as resolve, redirect_stdout(
            out
        ), redirect_stderr(
            err
        ):
            selector.main()
        resolve.assert_called_once_with(source_revision="a" * 64)
        self.assertEqual(out.getvalue().strip(), generation)
        self.assertIn("compiler-code changes may not be reflected", err.getvalue())


class CatalogEntrypointFlagTests(unittest.TestCase):
    def run_selection(self, flag):
        entrypoint = (
            Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"
        ).read_text()
        start = entrypoint.index(
            'case "${WAKFU_COMPILED_CATALOG_REUSE_EXISTING:-0}" in'
        )
        end = entrypoint.index("\nesac", start) + len("\nesac")
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "invocations"
            fake_python = Path(directory) / "python3"
            fake_python.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_INVOCATIONS"\n'
                'case "$*" in *select_existing*|*publish_compiled*) printf "generation\\n";; esac\n'
            )
            fake_python.chmod(0o755)
            env = dict(
                os.environ,
                PATH=directory + os.pathsep + os.environ.get("PATH", ""),
                TEST_INVOCATIONS=str(log),
                WAKFU_COMPILED_CATALOG_REUSE_EXISTING=flag,
            )
            result = subprocess.run(
                ["/bin/sh", "-eu", "-c", entrypoint[start:end]],
                env=env,
                text=True,
                capture_output=True,
            )
            calls = log.read_text() if log.exists() else ""
        return result, calls

    def test_reuse_mode_never_runs_the_publisher(self):
        result, calls = self.run_selection("1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("select_existing_compiled_catalog.py", calls)
        self.assertNotIn("publish_compiled_combat_catalog.py", calls)

    def test_default_path_runs_publisher(self):
        result, calls = self.run_selection("0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("publish_compiled_combat_catalog.py", calls)
        self.assertNotIn("select_existing_compiled_catalog.py", calls)

    def test_invalid_flag_does_not_run_any_catalog_tool(self):
        result, calls = self.run_selection("yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")


if __name__ == "__main__":
    unittest.main()
