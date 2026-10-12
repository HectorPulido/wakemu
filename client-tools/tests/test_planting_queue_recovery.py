"""Offline recovery behavior and real native transformed bytecode verification."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JAVA_SOURCES = ROOT / "client-tools/java"
TEST_SOURCES = Path(__file__).resolve().parent / "java"
EXPORTS = ["--add-exports", "java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED"]


class PlantingQueueRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.fake = Path(cls.directory.name) / "fake"
        cls.native = Path(cls.directory.name) / "native"
        cls.fake.mkdir()
        cls.native.mkdir()
        subprocess.run(
            [
                "javac",
                "-proc:none",
                "-source",
                "21",
                "-target",
                "21",
                "-d",
                str(cls.fake),
                str(JAVA_SOURCES / "OpenPlantingAgentRecovery.java"),
                str(TEST_SOURCES / "OpenPlantingAgentRecoveryTest.java"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "javac",
                "-proc:none",
                "-source",
                "21",
                "-target",
                "21",
                *EXPORTS,
                "-d",
                str(cls.native),
                str(JAVA_SOURCES / "OpenPlantingAgent.java"),
                str(JAVA_SOURCES / "OpenPlantingAgentRecovery.java"),
                str(TEST_SOURCES / "OpenPlantingAgentNativeVerify.java"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.agent = Path(cls.directory.name) / "open-planting.jar"
        with zipfile.ZipFile(cls.agent, "w") as archive:
            archive.writestr(
                "META-INF/MANIFEST.MF",
                "Manifest-Version: 1.0\nPremain-Class: OpenPlantingAgent\n\n",
            )
            for path in cls.native.glob("OpenPlantingAgent*.class"):
                archive.write(path, path.name)

    def test_offline_queue_recovery_never_duplicates_sent_requests_or_loses_targets(
        self,
    ):
        result = subprocess.run(
            [
                "java",
                "-Xverify:all",
                "-Djava.awt.headless=true",
                "-cp",
                str(self.fake),
                "OpenPlantingAgentRecoveryTest",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertIn("offline planting queue checks", result.stdout)

    def test_real_native_classes_verify_under_actual_javaagent_and_fail_closed_on_version_mismatch(
        self,
    ):
        classpath = str(self.native) + os.pathsep + str(ROOT / "client/lib/*")
        result = subprocess.run(
            [
                "java",
                "-Xverify:all",
                *EXPORTS,
                "-Djava.awt.headless=true",
                "-Dwakfu.local.openPlanting=true",
                "-javaagent:" + str(self.agent),
                "-cp",
                classpath,
                "OpenPlantingAgentNativeVerify",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        for name in ("cYt", "cYv", "dev", "ffY"):
            self.assertIn("VERIFIED native transformed " + name, result.stdout)
        self.assertIn(
            "PASS native class verification and boundary guards", result.stdout
        )
