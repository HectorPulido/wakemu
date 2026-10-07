import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "check_server_network",
    Path(__file__).resolve().parents[1] / "tools/check_server_network.py",
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ServerNetworkConfigTests(unittest.TestCase):
    def settings(self, content, environment=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(content)
            return tool.configuration(path, environment or {})

    def test_shell_environment_overrides_file_without_disclosing_other_settings(self):
        result = self.settings(
            'WAKFU_ADVERTISE_HOST="192.0.2.5"\nPASSWORD=private\n',
            {"WAKFU_ADVERTISE_HOST": "127.0.0.1", "PASSWORD": "other"},
        )
        self.assertEqual(result["advertised_host"], "127.0.0.1")
        self.assertNotIn("PASSWORD", result)

    def test_wildcard_bind_cannot_be_advertised(self):
        result = self.settings("WAKFU_BIND_HOST=0.0.0.0\n")
        self.assertEqual(result["bind_host"], "0.0.0.0")
        for content in (
            "WAKFU_ADVERTISE_HOST=0.0.0.0",
            "WAKFU_ADVERTISE_HOST=224.0.0.1",
            "WAKFU_ADVERTISE_WORLD_PORT=0",
            "WAKFU_ADVERTISE_WORLD_PORT=65536",
            "WAKFU_ADVERTISE_HOST=$(touch /never-run)",
        ):
            with self.assertRaises(ValueError):
                self.settings(content)

    def test_quoted_addresses_accept_comments_but_reject_trailing_values(self):
        result = self.settings('WAKFU_ADVERTISE_HOST="192.0.2.5" # test address\n')
        self.assertEqual(result["advertised_host"], "192.0.2.5")
        for value in ('"192.0.2.5" extra', '"192.0.2.5', "'192.0.2.5' '127.0.0.1'"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.settings("WAKFU_ADVERTISE_HOST=" + value)
