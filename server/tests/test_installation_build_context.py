"""Bounded build-context contract; no Docker execution or general matcher claim."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"(?m)^COPY tools ./tools$")
        self.assertNotRegex(dockerfile, r"(?m)^COPY tools/[^ ]+\.py ")
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
        self.assertEqual(len(assets), 35)
        seeds = sorted((ROOT / "seeds").glob("*.sql"))
        self.assertGreaterEqual(len(seeds), 10)
        for path in [*tools, *assets, *seeds]:
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(included=relative):
                self.assertTrue(context_file_is_included(relative, rules))
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
