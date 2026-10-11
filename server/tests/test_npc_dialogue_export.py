import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile


_TOOL = Path(__file__).resolve().parents[1] / "tools/export_npc_dialogues.py"
_SPEC = importlib.util.spec_from_file_location("npc_dialogue_export", _TOOL)
exporter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(exporter)


class NpcDialogueExportTests(unittest.TestCase):
    def test_preserves_native_text_and_scenario_without_inventing_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts = Path(directory) / "scripts.jar"
            language = Path(directory) / "language.jar"
            source = "function event_1()\n UI.openRewardsDialog(20)\nend\n"
            with zipfile.ZipFile(scripts, "w") as archive:
                archive.writestr("scenario/1.lua", source)
                archive.writestr("interactiveDialogs/npc1.lua", "Sound.playSound(1)")
                archive.writestr("other/ignored.lua", "ignored")
            with zipfile.ZipFile(language, "w") as archive:
                archive.writestr(
                    "texts_es.properties",
                    "content.75.1=Hola=amigo\ncontent.76.2=Adiós\nother=ignore\n",
                )
            nodes = [{"id": 1, "choices": [{"id": 2, "criteria": "quest=1"}]}]
            catalog = exporter.extract_catalog(nodes, scripts, {"es": language})
        self.assertEqual(catalog["nodes"], nodes)
        self.assertNotIn("target", catalog["nodes"][0]["choices"][0])
        self.assertEqual(catalog["translations"]["es"]["content.75.1"], "Hola=amigo")
        self.assertEqual(catalog["scripts"]["scenario/1.lua"]["source"], source)
        self.assertEqual(catalog["scripts"]["scenario/1.lua"]["functions"], ["event_1"])
        self.assertEqual(
            catalog["scripts"]["scenario/1.lua"]["quest_calls"],
            ["UI.openRewardsDialog(20)"],
        )
        self.assertEqual(len(catalog["scripts"]), 2)
