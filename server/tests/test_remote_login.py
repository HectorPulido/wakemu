import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "client-tools/dropin/remote-login.py"
DROPIN = SCRIPT.parent


def load_script():
    sys.path.insert(0, str(DROPIN))
    spec = importlib.util.spec_from_file_location("remote_login_test_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class JsonResponse:
    def __init__(self, value):
        self.value = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.value if size < 0 else self.value[:size]


class RemoteLoginTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name) / "runtime"
        self.config = {
            "api_url": "https://192.0.2.4:18443",
            "runtime_root": self.runtime,
        }

    def run_login(self, session):
        with (
            patch.object(self.module, "settings", return_value=self.config),
            patch("builtins.input", return_value="alice"),
            patch.object(
                self.module.getpass, "getpass", return_value="do-not-save-this"
            ),
            patch.object(
                self.module.urllib.request,
                "urlopen",
                return_value=JsonResponse(session),
            ) as urlopen,
            patch("builtins.print"),
        ):
            self.module.main()
        return urlopen

    def test_https_request_shape_and_private_token_file_without_password(self):
        self.runtime.mkdir(parents=True)
        target = self.runtime / "remote-login-session.json"
        target.write_text("stale session")
        target.chmod(0o644)

        urlopen = self.run_login({"api_token": "launcher-token", "account": {"id": 7}})

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://192.0.2.4:18443/login")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data),
            {"username": "alice", "password": "do-not-save-this", "remember": False},
        )
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 15})

        self.assertTrue(target.is_file())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        saved = target.read_text()
        self.assertEqual(
            json.loads(saved), {"api_token": "launcher-token", "account": {"id": 7}}
        )
        self.assertNotIn("do-not-save-this", saved)

    def test_http_endpoint_is_rejected_before_network_access(self):
        self.config["api_url"] = "http://192.0.2.4:18443"
        with (
            patch.object(self.module, "settings", return_value=self.config),
            patch.object(self.module.urllib.request, "urlopen") as urlopen,
        ):
            with self.assertRaisesRegex(ValueError, "requires HTTPS"):
                self.module.main()
        urlopen.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_missing_empty_or_non_string_api_token_is_rejected(self):
        for session in (
            {},
            {"api_token": ""},
            {"api_token": "  "},
            {"api_token": 12},
            [],
        ):
            with self.subTest(session=session):
                with self.assertRaisesRegex(ValueError, "did not return"):
                    self.run_login(session)
                self.assertFalse((self.runtime / "remote-login-session.json").exists())


if __name__ == "__main__":
    unittest.main()
