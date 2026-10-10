import importlib.util, io, json, os, shutil, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DROPIN = ROOT / "client-tools/dropin"
spec = importlib.util.spec_from_file_location(
    "mini_config", DROPIN / "portable_config.py"
)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
spec = importlib.util.spec_from_file_location(
    "mini_package", ROOT / "client-tools/packaging/package-mini-launcher.py"
)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class MiniLauncherTests(unittest.TestCase):
    def test_open_planting_false_is_preserved_and_nonboolean_rejected(self):
        self.cfg["open_planting"] = False
        self.path.write_text(json.dumps(self.cfg))
        self.assertIs(config.settings()["open_planting"], False)
        self.cfg["open_planting"] = "false"
        self.path.write_text(json.dumps(self.cfg))
        with self.assertRaises(ValueError):
            config.settings()

    def test_open_dungeon_missions_defaults_local_only_and_requires_boolean_opt_in(
        self,
    ):
        self.assertIs(config.settings()["open_dungeon_missions"], True)
        self.cfg.update(server_host="192.0.2.20", api_url="https://192.0.2.20")
        self.path.write_text(json.dumps(self.cfg))
        self.assertIs(config.settings()["open_dungeon_missions"], False)
        self.cfg["open_dungeon_missions"] = True
        self.path.write_text(json.dumps(self.cfg))
        self.assertIs(config.settings()["open_dungeon_missions"], True)
        self.cfg["open_dungeon_missions"] = "true"
        self.path.write_text(json.dumps(self.cfg))
        with self.assertRaisesRegex(
            ValueError, "open_dungeon_missions must be boolean"
        ):
            config.settings()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.path = self.base / "mini-launcher/config.json"
        self.path.parent.mkdir()
        self.cfg = dict(package.CONFIG)
        self.path.write_text(json.dumps(self.cfg))
        old = os.environ.get("WAKFU_LAUNCHER_CONFIG")
        os.environ["WAKFU_LAUNCHER_CONFIG"] = str(self.path)
        self.addCleanup(
            lambda: os.environ.pop("WAKFU_LAUNCHER_CONFIG", None)
            if old is None
            else os.environ.__setitem__("WAKFU_LAUNCHER_CONFIG", old)
        )

    def test_detects_existing_client_in_parent_without_repo(self):
        (self.base / "lib").mkdir()
        (self.base / "lib/wakfu-client.jar").touch()
        for n in ("classpath", "config.properties"):
            (self.base / n).touch()
        self.assertEqual(config.client_root(), self.base)
        self.assertEqual(config.profile_root("main"), self.path.parent / "profiles")
        self.assertEqual(
            config.profile_root("alpha"), self.path.parent / "profiles/instances/alpha"
        )

    def test_mismatched_api_cannot_expand_network_allowlist(self):
        for host, api in [
            ("127.0.0.1", "http://ankama.com"),
            ("127.0.0.1", "http://user:password@127.0.0.1"),
        ]:
            self.cfg.update(server_host=host, api_url=api)
            self.path.write_text(json.dumps(self.cfg))
            with self.assertRaises(ValueError):
                config.settings()

    def test_remote_numeric_host_is_configurable(self):
        self.cfg.update(server_host="192.0.2.20", api_url="https://192.0.2.20:8443")
        self.path.write_text(json.dumps(self.cfg))
        self.assertEqual(config.settings()["api_port"], 8443)

    def test_invalid_profile_cannot_escape_directory(self):
        for name in ("../secret", "a/b", "", "x" * 41):
            with self.assertRaises(ValueError):
                config.profile_root(name)

    def test_zip_is_deterministic_and_preserves_executable_mode(self):
        items = {"b": (b"b", 0o644), "Launch.command": (b"a", 0o755)}
        self.assertEqual(
            package.zip_bytes(items),
            package.zip_bytes(dict(reversed(list(items.items())))),
        )
        with zipfile.ZipFile(io.BytesIO(package.zip_bytes(items))) as z:
            self.assertEqual(
                (z.getinfo("Launch.command").external_attr >> 16) & 0o777, 0o755
            )

    def test_distributed_payload_has_no_client_or_runtime_dependencies(self):
        javac = shutil.which("javac")
        java_home = os.environ.get("JAVA_HOME")
        if not java_home and Path("/usr/libexec/java_home").is_file():
            try:
                java_home = subprocess.check_output(
                    ["/usr/libexec/java_home", "-v", "21+"], text=True
                ).strip()
            except (OSError, subprocess.CalledProcessError):
                pass
        if not java_home and javac and Path(javac).resolve() != Path("/usr/bin/javac"):
            java_home = str(Path(javac).resolve().parent.parent)
        if not java_home or not (Path(java_home) / "bin/javac").is_file():
            self.skipTest("JDK 21+ is required to build launcher agent fixtures")
        output = self.base / "wakfu-mini-launcher.zip"
        with patch.dict(os.environ, {"JAVA_HOME": java_home}):
            package.build(output)
        p = output
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            self.assertEqual(len(names), 17)
            self.assertFalse(
                any(
                    part in n.lower()
                    for n in names
                    for part in (
                        "wakfu-client.jar",
                        "capture-agent",
                        "sniffer",
                        "login-session",
                        "remember.json",
                        ".sqlite",
                        "contents/",
                        "jre/",
                    )
                )
            )
            for n in (
                "mini-launcher/agents/network-guard.jar",
                "mini-launcher/agents/desktop-fix.jar",
                "mini-launcher/agents/open-planting.jar",
            ):
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as agent:
                    allowed_policy = n == "mini-launcher/agents/open-planting.jar"
                    self.assertTrue(
                        all(
                            f == "META-INF/MANIFEST.MF"
                            or (
                                allowed_policy
                                and f == "dungeon-entry-overrides.properties"
                            )
                            or f.startswith(
                                (
                                    "DropinNetworkGuard",
                                    "LocalDesktopFix",
                                    "OpenPlantingAgent",
                                )
                            )
                            for f in agent.namelist()
                        )
                    )
                    if allowed_policy:
                        policy = agent.read(
                            "dungeon-entry-overrides.properties"
                        ).decode()
                        self.assertRegex(policy, r"(?m)^native_sha256=[0-9a-f]{64}$")
                        for destination in (720, 4578, 4689, 4714, 4751):
                            self.assertRegex(policy, rf"(?m)^{destination}=.+$")
