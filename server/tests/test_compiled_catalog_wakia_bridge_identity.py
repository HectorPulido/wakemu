"""Unrelated WakIA bridge edits must not regenerate combat publications."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wakfu_server import native_compiled_catalog as compiled


class CompilerBridgeIdentityTests(unittest.TestCase):
    def test_bridge_edits_are_ignored_and_combat_edits_invalidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = Path(temporary)
            package = server / "wakfu_server"
            reader = package / "storage/native_compiled_catalog.py"
            reader.parent.mkdir(parents=True)
            reader.write_text("reader", encoding="utf8")
            combat = package / "combat/combat_spell.py"
            combat.parent.mkdir()
            combat.write_text("combat-v1", encoding="utf8")
            similarly_named = package / "combat/wakia_bridge/fixture.py"
            similarly_named.parent.mkdir()
            similarly_named.write_text("still-gameplay", encoding="utf8")
            bridge = package / "wakia_bridge/wakfu_ai/bridge/jondo_entry.py"
            bridge.parent.mkdir(parents=True)
            bridge.write_text("bridge-v1", encoding="utf8")
            publisher = server / "tools/publish_compiled_combat_catalog.py"
            publisher.parent.mkdir()
            publisher.write_text("publisher", encoding="utf8")
            migration = server / "migrations/320_native_compiled_catalogs.sql"
            migration.parent.mkdir()
            migration.write_text("schema", encoding="utf8")

            def inventory():
                compiled._compiler_source_bytes.cache_clear()
                return compiled._compiler_source_bytes()

            with patch.object(compiled, "__file__", str(reader)):
                try:
                    initial = inventory()
                    paths = json.loads(initial)
                    self.assertIn("wakfu_server/combat/combat_spell.py", paths)
                    self.assertIn("wakfu_server/combat/wakia_bridge/fixture.py", paths)
                    self.assertNotIn(
                        "wakfu_server/wakia_bridge/wakfu_ai/bridge/jondo_entry.py",
                        paths,
                    )
                    bridge.write_text("bridge-v2", encoding="utf8")
                    self.assertEqual(inventory(), initial)
                    combat.write_text("combat-v2", encoding="utf8")
                    self.assertNotEqual(inventory(), initial)
                finally:
                    compiled._compiler_source_bytes.cache_clear()


if __name__ == "__main__":
    unittest.main()
