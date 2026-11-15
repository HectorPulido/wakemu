"""Bounded build-context contract; no Docker execution or general matcher claim."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATABASE_ROOT = ROOT.parent / "database"


def context_file_is_included(path, rules):
    """Evaluate only this repository's flat ordered glob allowlist grammar.

    Directories are traversal entries, not blanket file exceptions in this
    structural model. Docker remains the authority during the actual build.
    """
    included = False
    for raw in rules:
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        allow = raw.startswith("!")
        pattern = raw[1:] if allow else raw
        if pattern.endswith("/"):
            continue
        expression = ""
        index = 0
        while index < len(pattern):
            if pattern.startswith("**/", index):
                expression += "(?:[^/]+/)*"
                index += 3
            elif pattern.startswith("**", index):
                expression += ".*"
                index += 2
            elif pattern[index] == "*":
                expression += "[^/]*"
                index += 1
            elif pattern[index] == "?":
                expression += "[^/]"
                index += 1
            else:
                expression += re.escape(pattern[index])
                index += 1
        if re.fullmatch(expression, path):
            included = allow
    return included


class InstallationBuildContextTests(unittest.TestCase):
    def test_complete_root_tools_domain_assets_and_seeds_are_present_without_private_artifacts(
        self,
    ):
        rules = (ROOT / ".dockerignore").read_text().splitlines()
        database_rules = (DATABASE_ROOT / ".dockerignore").read_text().splitlines()
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("FROM rust:1.100-slim-bookworm AS spatial-builder", dockerfile)
        self.assertIn(
            "cargo build --release --locked --package wakemu-world-spatial --lib",
            dockerfile,
        )
        self.assertIn(
            "COPY --from=spatial-builder /out/libwakemu_world_spatial.so "
            "/usr/local/lib/wakemu/libwakemu_world_spatial.so",
            dockerfile,
        )
        for source in (
            "rust-services/Cargo.toml",
            "rust-services/Cargo.lock",
            "rust-services/crates/world-spatial/Cargo.toml",
            "rust-services/crates/world-spatial/src/lib.rs",
            "rust-services/crates/world-spatial/src/ffi.rs",
            "rust-services/crates/world-spatial/src/engine.rs",
        ):
            self.assertTrue(context_file_is_included(source, rules), source)
        self.assertFalse(
            context_file_is_included(
                "rust-services/target/release/libwakemu_world_spatial.so", rules
            )
        )
        self.assertRegex(dockerfile, r"(?m)^COPY tools ./tools$")
        self.assertNotRegex(dockerfile, r"(?m)^COPY tools/[^ ]+\.py ")
        self.assertIn("COPY --from=database seeds ./database/seeds", dockerfile)
        tools = sorted(
            [*(ROOT / "tools").glob("*.py"), *(ROOT / "tools").glob("*.json")]
        )
        self.assertTrue(tools)
        self.assertIn(ROOT / "tools/install_dungeon_bulk.py", tools)
        self.assertIn(ROOT / "tools/prepare_admitted_dungeon_rosters.py", tools)
        assets = sorted(
            path
            for path in (ROOT / "wakfu_server").rglob("*")
            if path.is_file()
            and (path.name.endswith(".json") or path.name.endswith(".json.gz"))
        )
        for relative in (
            "wakfu_server/items/native_ranch_building_footprints.json",
            "wakfu_server/items/native_ranch_building_definitions.json",
            "wakfu_server/items/native_ranch_biome_topology.json",
            "wakfu_server/maps/interior-base-partition-geometry.json",
            "wakfu_server/storage/profession_equipment_effects.json",
        ):
            with self.subTest(required_asset=relative):
                self.assertIn(ROOT / relative, assets)
        seeds = sorted((DATABASE_ROOT / "seeds").glob("*.sql"))
        self.assertGreaterEqual(len(seeds), 10)
        for path in [*tools, *assets]:
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(included=relative):
                self.assertTrue(context_file_is_included(relative, rules))
        for path in [*seeds, *(DATABASE_ROOT / "protocol").glob("*")]:
            if path.is_file():
                relative = path.relative_to(DATABASE_ROOT).as_posix()
                with self.subTest(database_included=relative):
                    self.assertTrue(context_file_is_included(relative, database_rules))
        for relative in (
            "data/installation/manifest.json",
            "backups/private.sql",
            "secrets/password",
        ):
            with self.subTest(database_excluded=relative):
                self.assertFalse(context_file_is_included(relative, database_rules))
        for relative in (
            ".runtime/private.json",
            "client/lib/client.jar",
            ".database/secrets/password",
            "tools/PrivateProbe.java",
            "tools/PrivateProbe.jar",
            "tools/__pycache__/helper.pyc",
            "wakfu_server/characters/__pycache__/store.pyc",
            "wakfu_server/cache/private.pyc",
            "wakfu_server/items/._private.json",
        ):
            with self.subTest(excluded=relative):
                self.assertFalse(context_file_is_included(relative, rules))
