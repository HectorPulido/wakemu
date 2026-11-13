"""Mission-only changes do not require rebuilding combat catalog records."""
import json
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wakfu_server import native_compiled_catalog as compiled


RII_GAMEPLAY_MODULES = (
    "items/crafting.py",
    "maps/mission_transport.py",
    "maps/monster_collect.py",
    "maps/npc_dialogue.py",
    "maps/npc_objective_facts.py",
    "maps/npc_world.py",
    "maps/planting.py",
    "maps/resource_collect.py",
    "maps/rii_conversation_progress.py",
    "maps/rii_ecosystem_dialogue.py",
    "maps/rii_dialogue_gate.py",
)


class MissionCompilerIdentityTests(unittest.TestCase):
    def test_mission_edits_do_not_invalidate_but_combat_edits_do(self):
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory)
            package = server / "wakfu_server"
            files = {
                "storage/native_compiled_catalog.py": "reader",
                "combat/combat_spell.py": "combat",
                "achievements/mission_progress.py": "mission",
                "objectives/environmental_recurring_storage.py": "recurring",
                "characters/guild_daily_quests.py": "guild",
                "maps/quest_npc.py": "quest npc",
            }
            files.update({name: "runtime only" for name in RII_GAMEPLAY_MODULES})
            for name, content in files.items():
                path = package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            for name in (
                "tools/publish_compiled_combat_catalog.py",
                "migrations/320_native_compiled_catalogs.sql",
            ):
                path = server / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)

            def identity():
                compiled._compiler_source_bytes.cache_clear()
                return compiled._compiler_source_bytes()

            with patch.object(
                compiled,
                "__file__",
                str(package / "storage/native_compiled_catalog.py"),
            ):
                try:
                    before = identity()
                    names = json.loads(before)
                    self.assertIn("wakfu_server/combat/combat_spell.py", names)
                    for name in list(files)[2:]:
                        (package / name).write_text("changed")
                    self.assertEqual(identity(), before)
                    # New mission modules and their later edits must not alter
                    # the compiler identity merely because their names change.
                    extra = package / "achievements/new_story/tutorial_flow.py"
                    extra.parent.mkdir(parents=True)
                    extra.write_text("new quest implementation")
                    self.assertEqual(identity(), before)
                    extra.write_text("changed quest implementation")
                    self.assertEqual(identity(), before)
                    extra.unlink()
                    self.assertEqual(identity(), before)
                    (package / "combat/combat_spell.py").write_text("changed")
                    self.assertNotEqual(identity(), before)
                    (package / "combat/combat_spell.py").write_text("combat")
                    (server / "tools/publish_compiled_combat_catalog.py").write_text(
                        "changed"
                    )
                    self.assertNotEqual(identity(), before)
                finally:
                    compiled._compiler_source_bytes.cache_clear()

    def test_compiler_and_combat_do_not_import_excluded_gameplay_modules(self):
        """Catch direct static dependencies; dynamic imports still need review."""
        server = Path(__file__).resolve().parents[1]
        sources = [server / "tools/publish_compiled_combat_catalog.py"]
        sources.extend((server / "wakfu_server/combat").rglob("*.py"))
        sources.extend((server / "wakfu_server/storage").rglob("*.py"))
        excluded = {Path(name).stem for name in RII_GAMEPLAY_MODULES}
        for source in sources:
            tree = ast.parse(source.read_text(), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or "", *(alias.name for alias in node.names)]
                else:
                    continue
                for name in names:
                    with self.subTest(source=str(source), name=name):
                        self.assertFalse(excluded.intersection(name.split(".")))


if __name__ == "__main__":
    unittest.main()
