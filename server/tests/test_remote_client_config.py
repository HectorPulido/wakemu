import importlib.util
import json
import os
import socket
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class RemoteClientConfigTest(unittest.TestCase):
    def test_direct_endpoint_settings_and_auth_proxy_scope(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "client-tools/dropin/portable_config.py"
        spec = importlib.util.spec_from_file_location(
            "portable_config_remote_test", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "server_host": "192.168.1.50",
                        "api_url": "https://192.168.1.50:18443",
                        "dispatch_port": 25558,
                    }
                )
            )
            with patch.dict(os.environ, {"WAKFU_LAUNCHER_CONFIG": str(config)}):
                result = module.settings()
                self.assertEqual(result["server_host"], "192.168.1.50")
                self.assertEqual(result["dispatch_port"], 25558)
                self.assertEqual(result["api_port"], 18443)
                config.write_text(
                    json.dumps(
                        {
                            "server_host": "192.168.1.50",
                            "api_url": "https://192.168.1.51:18443",
                        }
                    )
                )
                with self.assertRaises(ValueError):
                    module.settings()
        proxy = (root / "server/remote-auth/nginx.conf").read_text()
        self.assertIn("^/(login|remember|game-token)$", proxy)
        self.assertIn("limit_except POST { deny all; }", proxy)
        self.assertIn("location / { return 404; }", proxy)
        self.assertNotIn("/register", proxy)

    def test_domain_resolution_pinning_and_api_scope(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "portable_config_domain_test",
            root / "client-tools/dropin/portable_config.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "server_host": "game.example.com",
                        "api_url": "https://game.example.com:18443",
                    }
                )
            )
            with patch.dict(
                os.environ, {"WAKFU_LAUNCHER_CONFIG": str(config)}, clear=True
            ):
                answer = [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0))
                ]
                with patch.object(
                    socket, "getaddrinfo", return_value=answer
                ) as resolve:
                    cfg = module.settings()
                    resolve.assert_called_once_with(
                        "game.example.com", None, socket.AF_INET, socket.SOCK_STREAM
                    )
                self.assertEqual(cfg["server_host"], "192.0.2.10")
                self.assertEqual(cfg["server_name"], "game.example.com")
                self.assertEqual(cfg["api_url"], "https://game.example.com:18443")
                with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror):
                    with self.assertRaisesRegex(ValueError, "Could not resolve"):
                        module.settings()
                with patch.dict(
                    os.environ,
                    {
                        "WAKFU_SERVER_NAME": "game.example.com",
                        "WAKFU_SERVER_IPV4": "192.0.2.10",
                    },
                ):
                    with patch.object(
                        socket, "getaddrinfo", side_effect=AssertionError("DNS used")
                    ):
                        self.assertEqual(module.settings()["server_host"], "192.0.2.10")
                    with patch.dict(
                        os.environ, {"WAKFU_SERVER_NAME": "other.example.com"}
                    ):
                        with self.assertRaises(ValueError):
                            module.settings()
                    config.write_text(
                        json.dumps(
                            {
                                "server_host": "game.example.com",
                                "api_url": "https://other.example.com",
                            }
                        )
                    )
                    with self.assertRaises(ValueError):
                        module.settings()
                with patch.object(socket, "getaddrinfo") as original:
                    module.pin_dns(cfg)
                    socket.getaddrinfo("game.example.com", 443)
                    self.assertEqual(original.call_args.args[:2], ("192.0.2.10", 443))
                    socket.getaddrinfo("unrelated.example.com", 80)
                    self.assertEqual(
                        original.call_args.args[:2], ("unrelated.example.com", 80)
                    )
                for invalid in (
                    "bad host",
                    "-game.example",
                    "https://game.example",
                    "999.1.1.1",
                    "::1",
                ):
                    config.write_text(json.dumps({"server_host": invalid}))
                    with self.assertRaises(ValueError):
                        module.settings()
