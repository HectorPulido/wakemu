"""Recovery helper ships as source and executable classes in the portable agent."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "planting_queue_packager", ROOT / "client-tools/packaging/package-mini-launcher.py"
)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PlantingQueuePackagingTests(unittest.TestCase):
    def test_portable_agent_includes_compiled_recovery_and_source_with_valid_hashes(
        self,
    ):
        actual_run = subprocess.run
        compilation_sources = []

        def run(command, **kwargs):
            if command[0] == "/usr/libexec/java_home":
                return actual_run(command, **kwargs)
            if Path(command[0]).name == "javac":
                compilation_sources.extend(
                    str(value) for value in command if str(value).endswith(".java")
                )
                return actual_run(command, **kwargs)
            if any(
                str(value).endswith("build_dungeon_entry_overrides.py")
                for value in command
            ):
                # This packaging test needs no runtime DB or native dungeon policy.
                output = Path(command[command.index("--output") + 1])
                output.write_text(
                    "native_sha256=offline-packaging-fixture\n", encoding="utf-8"
                )
                return subprocess.CompletedProcess(command, 0)
            raise AssertionError(f"Unexpected subprocess: {command}")

        with tempfile.TemporaryDirectory() as directory, patch.object(
            packager.subprocess, "run", side_effect=run
        ), contextlib.redirect_stdout(io.StringIO()):
            archive_path = Path(directory) / "mini-launcher.zip"
            packager.build(archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                source = "mini-launcher/sources/OpenPlantingAgentRecovery.java"
                self.assertEqual(
                    archive.read(source),
                    (
                        ROOT / "client-tools/java/OpenPlantingAgentRecovery.java"
                    ).read_bytes(),
                )
                agent_bytes = archive.read("mini-launcher/agents/open-planting.jar")
                manifest = json.loads(archive.read("mini-launcher/manifest.json"))
                for name, digest in manifest["files"].items():
                    self.assertEqual(
                        hashlib.sha256(
                            archive.read("mini-launcher/" + name)
                        ).hexdigest(),
                        digest,
                    )
            with zipfile.ZipFile(io.BytesIO(agent_bytes)) as agent:
                self.assertIn("OpenPlantingAgent.class", agent.namelist())
                self.assertIn("OpenPlantingAgentRecovery.class", agent.namelist())
                self.assertIn(
                    b"Premain-Class: OpenPlantingAgent",
                    agent.read("META-INF/MANIFEST.MF"),
                )
        self.assertIn(
            str(ROOT / "client-tools/java/OpenPlantingAgentRecovery.java"),
            compilation_sources,
        )
