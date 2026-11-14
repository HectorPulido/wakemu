"""Verify shared launcher account isolation and embedded web authentication."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import types
import urllib.error
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "launcher_backend.py"
spec = importlib.util.spec_from_file_location("desktop_launcher_backend", SOURCE)
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.secrets = {}
        self.keychain_calls = []

        def keychain(action, identifier, value=""):
            self.keychain_calls.append((action, identifier, value))
            if action == "set":
                self.secrets[identifier] = value
            elif action == "get":
                if identifier not in self.secrets:
                    raise backend.LauncherError("Fixture keychain item missing")
                return self.secrets[identifier]
            elif action == "delete":
                self.secrets.pop(identifier, None)
            return ""

        self.patches = [
            patch.object(backend, "ROOT", self.root),
            patch.object(
                backend, "STATE_PATH", self.root / "profile/launcher-state.json"
            ),
            patch.object(backend.sys, "platform", "darwin"),
            patch.object(backend, "keychain", side_effect=keychain),
        ]
        for item in self.patches:
            item.start()
        self.data = dict(
            server=next(s for s in backend.default_state()["servers"] if s["id"] == "internet"),
            username="fixture_user",
            password="fixture-password",
            password_edited=True,
            remember=True,
        )

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def linux_keyring_modules(self, priority=5):
        secrets = self.secrets

        class PasswordDeleteError(Exception):
            pass

        class SecretServiceKeyring:
            def set_password(self, service, username, password):
                secrets[(service, username)] = password

            def get_password(self, service, username):
                return secrets.get((service, username))

            def delete_password(self, service, username):
                try:
                    del secrets[(service, username)]
                except KeyError:
                    raise PasswordDeleteError() from None

        SecretServiceKeyring.priority = priority
        keyring = types.ModuleType("keyring")
        keyring.get_keyring = Mock(side_effect=AssertionError("No fallback allowed"))
        service = types.ModuleType("keyring.backends.SecretService")
        service.Keyring = SecretServiceKeyring
        errors = types.ModuleType("keyring.errors")
        errors.PasswordDeleteError = PasswordDeleteError
        return {
            "keyring": keyring,
            "keyring.backends": types.ModuleType("keyring.backends"),
            "keyring.backends.SecretService": service,
            "keyring.errors": errors,
        }

    def test_linux_secret_service_save_restore_forget_and_renewal_never_store_plaintext(self):
        modules = self.linux_keyring_modules()
        with patch.object(backend.sys, "platform", "linux"), patch.dict(
            backend.sys.modules, modules
        ):
            backend.dispatch("save", self.data)
            backend.dispatch("save", self.data)
            state = backend.dispatch("state", {})["state"]
            self.assertEqual(state["password"], "fixture-password")
            self.assertTrue(state["credential_storage_available"])
            self.assertTrue(state["remember"])
            self.assertEqual(len(self.secrets), 1)
            serialized = backend.STATE_PATH.read_text()
            self.assertIn("secretservice:", serialized)
            self.assertNotIn("fixture-password", serialized)
            self.assertEqual(backend.STATE_PATH.stat().st_mode & 0o777, 0o600)
            folder = self.root / "renewal"
            folder.mkdir()
            token = backend.protect("private-renewal-fixture")
            backend.private_write(folder / "remember.json", {"protected_token": token})
            self.assertNotIn("private-renewal-fixture", (folder / "remember.json").read_text())
            backend.forget_renewal(folder)
            self.assertFalse((folder / "remember.json").exists())
            self.assertEqual(len(self.secrets), 1)
            result = backend.dispatch("forget", {"username": "fixture_user"})
            self.assertFalse(result["state"]["remember"])
            self.assertEqual(result["state"]["password"], "")
            self.assertEqual(self.secrets, {})
            backend.remove_protected(token)  # Already deleted references are safe.
        modules["keyring"].get_keyring.assert_not_called()

    def test_linux_unavailable_secure_storage_defaults_off_and_never_falls_back(self):
        for priority in (0, -1):
            modules = self.linux_keyring_modules(priority=priority)
            with self.subTest(priority=priority), patch.object(
                backend.sys, "platform", "linux"
            ), patch.dict(backend.sys.modules, modules):
                state = backend.dispatch("state", {})["state"]
                self.assertFalse(state["credential_storage_available"])
                self.assertFalse(state["remember"])
                with self.assertRaisesRegex(backend.LauncherError, "turn off Save account and password"):
                    backend.dispatch("save", self.data)
                self.assertFalse(backend.STATE_PATH.exists())
                self.assertEqual(self.secrets, {})
                modules["keyring"].get_keyring.assert_not_called()
        with patch.object(backend.sys, "platform", "linux"), patch.dict(
            backend.sys.modules, {"keyring.backends.SecretService": None}
        ):
            self.assertFalse(backend.credential_storage_available())
            result = backend.dispatch("save", dict(self.data, remember=False))
            self.assertFalse(result["state"]["remember"])
            self.assertNotIn("fixture-password", backend.STATE_PATH.read_text())

    def test_linux_secret_service_errors_are_safe_and_other_os_references_are_rejected(self):
        modules = self.linux_keyring_modules()
        with patch.object(backend.sys, "platform", "linux"), patch.dict(
            backend.sys.modules, modules
        ):
            for opaque in ("keychain:" + "a" * 64, "d2luZG93cy1maXh0dXJl", None):
                with self.subTest(opaque=opaque), self.assertRaisesRegex(
                    backend.LauncherError, "another operating system"
                ):
                    backend.unprotect(opaque)
            with patch.object(
                modules["keyring.backends.SecretService"].Keyring,
                "set_password",
                side_effect=RuntimeError("sensitive-keyring-fixture"),
            ), self.assertRaises(backend.LauncherError) as failure:
                backend.protect("private-password-fixture")
            self.assertNotIn("sensitive", str(failure.exception))
            self.assertNotIn("private-password", str(failure.exception))
            with self.assertRaisesRegex(backend.LauncherError, "reference is invalid"):
                backend.unprotect("secretservice:invalid")
        with self.assertRaisesRegex(backend.LauncherError, "another operating system"):
            backend.unprotect("secretservice:" + "a" * 64)

    def test_configured_launcher_root_controls_state_path_without_copying_state(self):
        configured = self.root / "configured-root"
        with patch.dict(os.environ, {"WAKFU_LAUNCHER_ROOT": str(configured)}):
            spec = importlib.util.spec_from_file_location("configured_launcher_backend", SOURCE)
            configured_backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(configured_backend)
        self.assertEqual(configured_backend.ROOT, configured.resolve())
        self.assertEqual(configured_backend.STATE_PATH, configured.resolve() / "profile/launcher-state.json")
        self.assertFalse(configured.exists())

    def test_protected_auth_renewal_rotates_secure_reference_without_persisting_token_in_session(self):
        auth_spec = importlib.util.spec_from_file_location(
            "integrated_launcher_auth", SOURCE.parent / "local_launcher_auth.py"
        )
        authentication = importlib.util.module_from_spec(auth_spec)
        auth_spec.loader.exec_module(authentication)
        login = self.root / "login-session.json"
        previous = {"api_token": "previous-api", "account": {"id": 9}}
        login.write_text(json.dumps(previous))
        old_reference = backend.protect("previous-renewal")
        remembered = {"account_id": 9, "protected_token": old_reference}
        backend.private_write(self.root / "remember.json", remembered)
        auth = authentication.LauncherAuthentication(login, opener=Mock())
        renewed = {
            "api_token": "renewed-api",
            "account": {"id": 9},
            "remember_token": "rotated-renewal",
        }
        with patch.dict(backend.sys.modules, {"launcher_backend": backend}), patch.object(
            auth, "_request", return_value=renewed
        ):
            auth._renew(previous)
        session = json.loads(login.read_text())
        self.assertEqual(session["api_token"], "renewed-api")
        self.assertNotIn("remember_token", session)
        replacement = json.loads((self.root / "remember.json").read_text())["protected_token"]
        self.assertNotEqual(replacement, old_reference)
        self.assertEqual(backend.unprotect(replacement), "rotated-renewal")
        self.assertNotIn(old_reference[9:], self.secrets)
        self.assertNotIn("rotated-renewal", (self.root / "remember.json").read_text())
        before_login, before_remember = login.read_bytes(), (self.root / "remember.json").read_bytes()
        with patch.dict(backend.sys.modules, {"launcher_backend": backend}), patch.object(
            auth, "_request", return_value=dict(renewed, account={"id": 10})
        ), self.assertRaises(authentication.LauncherAuthenticationError):
            auth._renew(previous)
        self.assertEqual(login.read_bytes(), before_login)
        self.assertEqual((self.root / "remember.json").read_bytes(), before_remember)

    def test_protected_auth_rotation_preserves_previous_reference_when_atomic_save_fails(self):
        auth_spec = importlib.util.spec_from_file_location(
            "integrated_launcher_auth", SOURCE.parent / "local_launcher_auth.py"
        )
        authentication = importlib.util.module_from_spec(auth_spec)
        auth_spec.loader.exec_module(authentication)
        previous = {"api_token": "previous-api", "account": {"id": 9}}
        login = self.root / "login-session.json"
        login.write_text(json.dumps(previous))
        old_reference = backend.protect("previous-renewal")
        backend.private_write(self.root / "remember.json", {"protected_token": old_reference})
        auth = authentication.LauncherAuthentication(login, opener=Mock())
        before = (self.root / "remember.json").read_bytes()
        with patch.dict(backend.sys.modules, {"launcher_backend": backend}), patch.object(
            auth, "_request", return_value=dict(previous, remember_token="rotated-renewal")
        ), patch.object(backend, "private_write", side_effect=OSError("fixture write failure")), self.assertRaises(
            authentication.LauncherAuthenticationError
        ):
            auth._renew(previous)
        self.assertEqual((self.root / "remember.json").read_bytes(), before)
        self.assertEqual(backend.unprotect(old_reference), "previous-renewal")
        self.assertEqual(len(self.secrets), 1)
        self.assertEqual(json.loads(login.read_text()), previous)

    def discovery_manifest(self):
        server = self.data["server"]
        fields = (
            "server_host",
            "chat_host",
            "dispatch_port",
            "game_ports",
            "chat_port",
            "api_url",
            "http_url",
            "shop_url",
            "achievements_url",
        )
        return dict(version=1, certificate="", **{key: server[key] for key in fields})

    def discovery_opener(self, manifest=None, raw=None):
        opener = Mock()
        payload = (
            raw
            if raw is not None
            else json.dumps(manifest or self.discovery_manifest()).encode()
        )
        opener.open.return_value = io.BytesIO(payload)
        return opener

    def test_discovery_keeps_loopback_http_overrides_without_network_requests(self):
        for hostname in ("127.0.0.1", "127.0.0.2", "localhost"):
            server = dict(
                self.data["server"],
                server_host=hostname,
                chat_host=hostname,
                dispatch_port=25558,
                game_ports=[25556],
                chat_port=26337,
                api_url=f"http://{hostname}:28081",
                http_url=f"http://{hostname}:28082",
                shop_url=f"http://{hostname}:28083",
                achievements_url=f"http://{hostname}:28084",
            )
            with self.subTest(hostname=hostname), patch.object(
                backend.urllib.request, "build_opener"
            ) as build, patch.object(backend.ssl, "create_default_context") as context:
                result = backend.dispatch("discover", {"server": server})
            self.assertTrue(result["ok"])
            self.assertEqual(result["server"], backend.normalize_server(server))
            self.assertEqual(
                result["message"],
                "Local server settings loaded. Use Advanced settings to change ports and services.",
            )
            build.assert_not_called()
            context.assert_not_called()
            self.assertFalse(backend.STATE_PATH.exists())

    def test_discovery_reads_same_origin_manifest_without_credentials_or_local_mutation(
        self,
    ):
        server = dict(
            self.data["server"],
            id="saved-server",
            name="My retained server",
            install_root="/retained/local/game",
        )
        manifest = dict(
            self.discovery_manifest(),
            id="remote-id",
            name="remote-name",
            install_root="/remote/forbidden/path",
        )
        opener = self.discovery_opener(manifest)
        with patch.object(
            backend.urllib.request, "build_opener", return_value=opener
        ) as build, patch.object(backend, "api_request") as auth, patch.object(
            backend.subprocess, "Popen"
        ) as spawn:
            result = backend.dispatch("discover", {"server": server})
        self.assertTrue(result["ok"])
        discovered = result["server"]
        for key in ("id", "name", "install_root"):
            self.assertEqual(discovered[key], server[key])
        request = opener.open.call_args.args[0]
        self.assertEqual(
            request.full_url, "https://" + server["server_host"] + "/launcher/config"
        )
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertNotIn("Authorization", dict(request.header_items()))
        self.assertNotIn("Cookie", dict(request.header_items()))
        self.assertTrue(
            any(isinstance(item, backend.NoRedirect) for item in build.call_args.args)
        )
        auth.assert_not_called()
        spawn.assert_not_called()
        self.assertEqual(self.secrets, {})
        self.assertFalse(backend.STATE_PATH.exists())

    def test_discovery_rejects_foreign_hosts_endpoint_paths_credentials_and_invalid_ports(
        self,
    ):
        origin = self.data["server"]["api_url"]
        cases = [
            dict(version=True),
            dict(version=2),
            dict(server_host="foreign.example"),
            dict(chat_host="foreign.example"),
            dict(dispatch_port=0),
            dict(dispatch_port=True),
            dict(chat_port=65536),
            dict(game_ports=[0]),
            dict(game_ports=[True]),
            dict(game_ports=[]),
            dict(certificate="untrusted.pem"),
        ]
        for field in ("api_url", "http_url", "shop_url", "achievements_url"):
            for value in (
                "https://foreign.example",
                origin + "/extra/path",
                origin + "?token=secret",
                origin.replace("https://", "https://user:secret@"),
                origin.replace("https://", "http://"),
            ):
                cases.append({field: value})
        for overrides in cases:
            opener = self.discovery_opener(dict(self.discovery_manifest(), **overrides))
            with self.subTest(overrides=overrides), patch.object(
                backend.urllib.request, "build_opener", return_value=opener
            ), self.assertRaises(backend.LauncherError):
                backend.dispatch("discover", {"server": self.data["server"]})
            self.assertFalse(backend.STATE_PATH.exists())
        for raw in (b"[]", b"{", b"x" * 65537):
            with self.subTest(raw_size=len(raw)), patch.object(
                backend.urllib.request,
                "build_opener",
                return_value=self.discovery_opener(raw=raw),
            ), self.assertRaises(backend.LauncherError):
                backend.dispatch("discover", {"server": self.data["server"]})

    def test_discovery_refuses_redirect_and_never_sends_saved_credentials(self):
        backend.dispatch("save", self.data)
        before = backend.STATE_PATH.read_bytes()
        opener = Mock()
        opener.open.side_effect = backend.LauncherError("Redirect refused fixture")
        with patch.object(
            backend.urllib.request, "build_opener", return_value=opener
        ), self.assertRaises(backend.LauncherError):
            backend.dispatch("discover", {"server": self.data["server"]})
        request = opener.open.call_args.args[0]
        self.assertIsNone(request.data)
        self.assertNotIn("fixture-password", str(request.header_items()))
        self.assertEqual(backend.STATE_PATH.read_bytes(), before)
        with self.assertRaises(backend.LauncherError):
            backend.NoRedirect().redirect_request(
                None, None, 302, "Moved", {}, "https://foreign.example/launcher/config"
            )

    def test_unified_alias_migration_preserves_exact_legacy_scope_and_saved_identity(
        self,
    ):
        for legacy_host in (
            "dashboard.pangolin.hectorpulido.net",
            "wakemu-game.p.hectorpulido.net",
        ):
            with self.subTest(legacy_host=legacy_host):
                backend.STATE_PATH.unlink(missing_ok=True)
                self.secrets.clear()
                legacy = dict(
                    self.data["server"],
                    server_host=legacy_host,
                    chat_host=legacy_host,
                    api_url="https://wakemu-auth.p.hectorpulido.net",
                    http_url="https://wakemu-resources.p.hectorpulido.net",
                    shop_url="https://wakemu-shop.p.hectorpulido.net",
                    achievements_url="https://wakemu-adventures.p.hectorpulido.net",
                )
                original_identity = {
                    key: value
                    for key, value in legacy.items()
                    if key
                    not in (
                        "id",
                        "name",
                        "certificate",
                        "install_root",
                        "achievements_url",
                    )
                }
                original_identity["server_host"] = "dashboard.pangolin.hectorpulido.net"
                original_identity["chat_host"] = "dashboard.pangolin.hectorpulido.net"
                original_identity["certificate_sha256"] = "system"
                original_digest = hashlib.sha256(
                    json.dumps(
                        original_identity, sort_keys=True, separators=(",", ":")
                    ).encode()
                ).hexdigest()
                self.assertEqual(backend.fingerprint(legacy), original_digest)
                self.assertEqual(
                    backend.fingerprint(self.data["server"]), original_digest
                )
                backend.dispatch("save", dict(self.data, server=legacy))
                stored = json.loads(backend.STATE_PATH.read_text())
                key = next(iter(stored["accounts"]))
                reference = stored["accounts"][key]["protected"]
                result = backend.dispatch("state", {})["state"]
                selected = next(
                    server
                    for server in result["servers"]
                    if server["id"] == result["selected_id"]
                )
                self.assertEqual(result["selected_username"], "fixture_user")
                self.assertEqual(result["password"], "fixture-password")
                self.assertEqual(selected["server_host"], "wakemu.p.hectorpulido.net")
                for field in ("api_url", "http_url", "shop_url", "achievements_url"):
                    self.assertEqual(
                        selected[field], "https://wakemu.p.hectorpulido.net"
                    )
                self.assertEqual(backend.account_key(selected, "fixture_user"), key)
                self.assertEqual(
                    backend.load_state()["accounts"][key]["protected"], reference
                )

    def test_startup_accepts_only_ready_marker_and_cleans_it(self):
        status = self.root / "startup-fixture.json"
        status.write_text('{"status":"ready","bridge_pid":123}')
        process = Mock()
        backend.await_startup(process, status, self.root / "launcher.log", timeout=1)
        process.poll.assert_not_called()
        self.assertFalse(status.exists())

    def test_startup_rejects_early_exit_malformed_markers_and_deadline_without_false_success(
        self,
    ):
        status = self.root / "startup-fixture.json"
        log = self.root / "launcher.log"
        for marker in ("{", "[]", '{"status":"starting"}'):
            status.write_text(marker)
            process = Mock()
            process.poll.return_value = 2
            with self.subTest(marker=marker), self.assertRaisesRegex(
                backend.LauncherError, "closed during startup"
            ):
                backend.await_startup(process, status, log, timeout=1)
            self.assertFalse(status.exists())
        process = Mock()
        process.poll.return_value = None
        with patch.object(
            backend.time, "monotonic", side_effect=[0, 0, 2]
        ), patch.object(backend.time, "sleep") as sleep, self.assertRaisesRegex(
            backend.LauncherError, "has not confirmed startup"
        ):
            backend.await_startup(process, status, log, timeout=1)
        self.assertEqual(sleep.call_count, 1)
        process.terminate.assert_not_called()
        self.assertFalse(status.exists())

    def test_game_launch_discards_stale_dns_and_startup_paths_and_waits_for_client_handshake(
        self,
    ):
        installed = self.root / "installed"
        (installed / "lib").mkdir(parents=True)
        (installed / "lib/wakfu-client.jar").write_bytes(b"fixture-game-jar")
        data = copy.deepcopy(self.data)
        data["server"]["install_root"] = str(installed)
        data["remember"] = False
        login = {
            "account": {"id": 982, "username": "fixture_user"},
            "api_token": "fixture-api-token",
        }
        for failure in (None, backend.LauncherError("Fixture client failed startup")):
            process = Mock(pid=321)
            with self.subTest(failure=bool(failure)), patch.dict(
                os.environ,
                {
                    "WAKFU_RESOLVED_HOSTS": '{"stale.fixture":"192.0.2.9"}',
                    "WAKFU_LAUNCH_STATUS_FILE": "/stale/status.json",
                },
            ), patch.object(backend, "api_request", return_value=login), patch.object(
                backend.subprocess, "Popen", return_value=process
            ) as spawn, patch.object(
                backend, "await_startup", side_effect=failure
            ) as ready:
                if failure:
                    with self.assertRaisesRegex(
                        backend.LauncherError, "failed startup"
                    ):
                        backend.dispatch("play", data)
                else:
                    self.assertEqual(backend.dispatch("play", data)["pid"], 321)
            env = spawn.call_args.kwargs["env"]
            self.assertNotIn("WAKFU_RESOLVED_HOSTS", env)
            status = Path(env["WAKFU_LAUNCH_STATUS_FILE"])
            self.assertEqual(
                status.parent.name,
                backend.account_key(
                    backend.normalize_server(data["server"]), "fixture_user"
                ),
            )
            self.assertTrue(status.name.startswith("startup-"))
            ready.assert_called_once_with(
                process, status, status.parent / "logs/launcher.log"
            )

    def registration_data(self, **changes):
        result = dict(
            self.data,
            username="new_fixture",
            password="new-fixture-password",
            password_confirm="new-fixture-password",
        )
        result.update(changes)
        return result

    def test_registration_validates_confirmation_and_native_rules_before_any_mutation(
        self,
    ):
        backend.dispatch("save", self.data)
        before = backend.STATE_PATH.read_bytes()
        secrets = dict(self.secrets)
        cases = [
            dict(username=None),
            dict(username=123),
            dict(remember=0),
            dict(username="ab"),
            dict(username="x" * 33),
            dict(username="bad user"),
            dict(username="bad@example"),
            dict(password="short", password_confirm="short"),
            dict(password="x" * 257, password_confirm="x" * 257),
            dict(password_confirm="different"),
            dict(password_confirm=None),
            dict(password=123, password_confirm=123),
        ]
        for values in cases:
            with self.subTest(values=values), patch.object(
                backend, "api_request"
            ) as request, patch.object(
                backend.subprocess, "Popen"
            ) as spawn, self.assertRaises(
                backend.LauncherError
            ):
                backend.dispatch("register", self.registration_data(**values))
            request.assert_not_called()
            spawn.assert_not_called()
            self.assertEqual(backend.STATE_PATH.read_bytes(), before)
            self.assertEqual(self.secrets, secrets)

    def test_registration_only_creates_account_then_selects_and_protects_it_without_game_login(
        self,
    ):
        backend.dispatch("save", self.data)
        registration = self.registration_data(username="  New_fixture  ")
        with patch.object(
            backend, "api_request", return_value={"id": 982, "username": "New_fixture"}
        ) as request, patch.object(backend.subprocess, "Popen") as spawn:
            result = backend.dispatch("register", registration)
        self.assertTrue(result["ok"])
        self.assertEqual(request.call_count, 1)
        server, route, body = request.call_args.args
        self.assertEqual(route, "/register")
        self.assertEqual(server["api_url"], self.data["server"]["api_url"])
        self.assertEqual(
            body, {"username": "New_fixture", "password": "new-fixture-password"}
        )
        spawn.assert_not_called()
        state = backend.dispatch("state", {})["state"]
        self.assertEqual(state["selected_username"], "New_fixture")
        self.assertEqual(state["password"], "new-fixture-password")
        self.assertIn("fixture_user", state["accounts"])
        self.assertNotIn("new-fixture-password", backend.STATE_PATH.read_text())
        self.assertEqual(len(self.secrets), 2)
        self.assertFalse(list(self.root.rglob("login-session.json")))
        self.assertFalse(list(self.root.rglob("remember.json")))

    def test_failed_or_malformed_registration_keeps_previous_account_and_password(self):
        backend.dispatch("save", self.data)
        before = backend.STATE_PATH.read_bytes()
        secrets = dict(self.secrets)
        malformed = [
            {},
            {"id": True, "username": "new_fixture"},
            {"id": 0, "username": "new_fixture"},
            {"id": "982", "username": "new_fixture"},
            {"id": 982, "username": "other_fixture"},
            {"id": 982, "username": None},
        ]
        for response in malformed:
            with self.subTest(response=response), patch.object(
                backend, "api_request", return_value=response
            ), self.assertRaises(backend.LauncherError):
                backend.dispatch("register", self.registration_data())
            self.assertEqual(backend.STATE_PATH.read_bytes(), before)
            self.assertEqual(self.secrets, secrets)
        with patch.object(
            backend,
            "api_request",
            side_effect=backend.LauncherError("That username already exists."),
        ), self.assertRaisesRegex(backend.LauncherError, "already exists"):
            backend.dispatch("register", self.registration_data())
        self.assertEqual(backend.STATE_PATH.read_bytes(), before)
        self.assertEqual(self.secrets, secrets)

    def test_registration_reads_state_before_creation_and_reports_committed_creation_despite_save_failure(
        self,
    ):
        backend.dispatch("save", self.data)
        before = backend.STATE_PATH.read_bytes()
        with patch.object(
            backend,
            "load_state",
            side_effect=backend.LauncherError("Fixture unreadable state"),
        ), patch.object(backend, "api_request") as request, self.assertRaises(
            backend.LauncherError
        ):
            backend.dispatch("register", self.registration_data())
        request.assert_not_called()
        for failure in (
            OSError("Fixture disk failure"),
            backend.LauncherError("Fixture keychain failure"),
            subprocess.TimeoutExpired(["fixture-helper"], 1),
        ):
            with self.subTest(failure=type(failure).__name__), patch.object(
                backend, "save", side_effect=failure
            ), patch.object(
                backend,
                "api_request",
                return_value={"id": 982, "username": "new_fixture"},
            ) as request:
                result = backend.dispatch("register", self.registration_data())
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"]["selected_username"], "new_fixture")
            self.assertEqual(result["state"]["password"], "new-fixture-password")
            self.assertFalse(result["state"]["remember"])
            self.assertIn("Account created", result["message"])
            self.assertEqual(request.call_count, 1)
            self.assertEqual(backend.STATE_PATH.read_bytes(), before)

    def test_registration_http_errors_expose_only_approved_duplicate_and_validation_messages(
        self,
    ):
        server = self.data["server"]
        fixtures = [
            ("Ese usuario ya existe.", "That username already exists."),
            ("Contraseña: 8–256 caracteres.", "Password: 8–256 characters."),
            ("sensitive-private-upstream-body", None),
            (["sensitive-private-upstream-body"], None),
        ]
        for detail, expected in fixtures:
            error = urllib.error.HTTPError(
                server["api_url"] + "/register",
                400,
                "Bad Request",
                {},
                io.BytesIO(json.dumps({"error": detail}).encode()),
            )
            opener = Mock()
            opener.open.side_effect = error
            with self.subTest(detail=detail):
                with patch.object(
                    backend.urllib.request, "build_opener", return_value=opener
                ), self.assertRaises(backend.LauncherError) as caught:
                    backend.api_request(
                        server,
                        "/register",
                        {"username": "new_fixture", "password": "new-fixture-password"},
                    )
                if expected:
                    self.assertEqual(str(caught.exception), expected)
                self.assertNotIn("sensitive-private", str(caught.exception))

    def test_registration_without_remember_selects_account_without_persisting_password(
        self,
    ):
        with patch.object(
            backend, "api_request", return_value={"id": 982, "username": "new_fixture"}
        ):
            result = backend.dispatch(
                "register", self.registration_data(remember=False)
            )
        self.assertTrue(result["ok"])
        state = backend.dispatch("state", {})["state"]
        self.assertEqual(state["selected_username"], "new_fixture")
        self.assertEqual(state["password"], "")
        self.assertFalse(state["remember"])
        self.assertEqual(self.secrets, {})
        self.assertNotIn("new-fixture-password", backend.STATE_PATH.read_text())

    def test_keychain_autosave_reuses_scoped_item_and_forget_removes_real_reference(
        self,
    ):
        backend.dispatch("save", self.data)
        backend.dispatch("save", self.data)
        state = backend.dispatch("state", {})["state"]
        self.assertEqual(state["password"], "fixture-password")
        self.assertEqual(len(self.secrets), 1)
        serialized = backend.STATE_PATH.read_text()
        self.assertNotIn("fixture-password", serialized)
        self.assertIn("keychain:", serialized)
        self.assertEqual(backend.STATE_PATH.stat().st_mode & 0o777, 0o600)
        result = backend.dispatch("forget", {"username": "fixture_user"})
        self.assertFalse(result["state"]["remember"])
        self.assertEqual(result["state"]["password"], "")
        self.assertEqual(self.secrets, {})

    def test_account_switch_and_uncheck_cannot_inherit_or_retain_another_secret(self):
        backend.dispatch("save", self.data)
        other = dict(self.data, username="fixture_other", password="other-password")
        backend.dispatch("save", other)
        self.assertEqual(len(self.secrets), 2)
        selected = backend.dispatch("state", {"username": "fixture_user"})["state"]
        self.assertEqual(selected["password"], "fixture-password")
        backend.dispatch("save", dict(self.data, remember=False))
        self.assertEqual(len(self.secrets), 1)
        self.assertEqual(
            backend.dispatch("state", {"username": "fixture_user"})["state"][
                "password"
            ],
            "",
        )
        self.assertEqual(
            backend.dispatch("state", {"username": "fixture_other"})["state"][
                "password"
            ],
            "other-password",
        )

    def test_web_login_uses_only_non_kicking_credential_bridge_and_validates_scoped_url(
        self,
    ):
        expected = (
            self.data["server"]["achievements_url"] + "/player/#token=" + "a" * 43
        )
        with patch.object(
            backend, "api_request", return_value={"url": expected, "valid_days": 30}
        ) as request, patch.object(backend.subprocess, "Popen") as spawn:
            result = backend.dispatch("web-login", self.data)
        self.assertEqual(result["url"], expected)
        server, path, credentials = request.call_args.args
        self.assertEqual(server["api_url"], self.data["server"]["achievements_url"])
        self.assertEqual(path, "/launcher/login")
        self.assertEqual(
            credentials, {"username": "fixture_user", "password": "fixture-password"}
        )
        spawn.assert_not_called()
        self.assertFalse(list(self.root.rglob("login-session.json")))
        self.assertFalse(list(self.root.rglob("remember.json")))

    def test_web_trust_is_independent_and_plain_http_is_limited_to_private_addresses(
        self,
    ):
        certificate = self.root / "native-ca.pem"
        certificate.write_text("fixture-native-ca")
        data = copy.deepcopy(self.data)
        data["server"]["certificate"] = str(certificate)
        data["server"]["api_url"] = "https://native-auth.fixture"
        expected = data["server"]["achievements_url"] + "/player/#token=" + "a" * 43
        with patch.object(
            backend, "api_request", return_value={"url": expected}
        ) as request:
            backend.dispatch("web-login", data)
        self.assertEqual(request.call_args.args[0]["certificate"], "")
        for origin in ("http://public.example", "http://8.8.8.8"):
            data["server"]["achievements_url"] = origin
            with self.subTest(origin=origin), patch.object(
                backend, "api_request"
            ) as request, self.assertRaises(backend.LauncherError):
                backend.dispatch("web-login", data)
            request.assert_not_called()
        for origin in ("http://192.168.0.7:18090", "http://localhost:18090"):
            data["server"]["achievements_url"] = origin
            expected = origin + "/player/#token=" + "a" * 43
            with self.subTest(origin=origin), patch.object(
                backend, "api_request", return_value={"url": expected}
            ):
                self.assertEqual(backend.dispatch("web-login", data)["url"], expected)

    def test_web_login_rejects_foreign_credentials_links_and_malformed_tokens(self):
        origin = self.data["server"]["achievements_url"]
        paths = [
            "https://foreign.example/player/#token=" + "a" * 43,
            origin + ".foreign.example/player/#token=" + "a" * 43,
            origin + "/admin/#token=" + "a" * 43,
            origin + "/player/?token=secret#token=" + "a" * 43,
            origin + "/player/#token=short",
            origin + "/player/#token=" + "a" * 43 + "&account=other",
            "http://" + origin.removeprefix("https://") + "/player/#token=" + "a" * 43,
        ]
        for url in paths:
            with self.subTest(url=url), patch.object(
                backend, "api_request", return_value={"url": url}
            ), self.assertRaises(backend.LauncherError):
                backend.dispatch("web-login", self.data)

    def test_editing_portal_origin_requires_explicit_password_entry(self):
        backend.dispatch("save", self.data)
        changed = copy.deepcopy(self.data)
        changed["server"]["achievements_url"] = "https://custom.example"
        changed["password_edited"] = False
        with patch.object(backend, "api_request") as request, self.assertRaises(
            backend.LauncherError
        ):
            backend.dispatch("web-login", changed)
        request.assert_not_called()
        changed["password_edited"] = True
        expected = "https://custom.example/player/#token=" + "b" * 43
        with patch.object(
            backend, "api_request", return_value={"url": expected}
        ) as request:
            self.assertEqual(backend.dispatch("web-login", changed)["url"], expected)
        self.assertEqual(request.call_args.args[0]["api_url"], "https://custom.example")

    def test_legacy_default_portal_and_install_path_preserve_existing_credential_scope(
        self,
    ):
        normalized = backend.normalize_server(self.data["server"])
        legacy = {
            key: value
            for key, value in normalized.items()
            if key not in ("achievements_url", "install_root")
        }
        self.assertEqual(backend.fingerprint(normalized), backend.fingerprint(legacy))
        alternate = dict(normalized, install_root="/different/game/path")
        self.assertEqual(
            backend.fingerprint(normalized), backend.fingerprint(alternate)
        )
        self.assertNotEqual(
            backend.fingerprint(normalized),
            backend.fingerprint(
                dict(normalized, achievements_url="https://custom.example")
            ),
        )

    def test_game_install_discovers_existing_bundle_and_relative_config_without_changing_assets(
        self,
    ):
        bundle = self.root / "Existing Wakfu.app" / "Contents/Resources"
        (bundle / "lib").mkdir(parents=True)
        (bundle / "lib/wakfu-client.jar").write_bytes(b"fixture-unmodified")
        self.assertEqual(
            backend.game_install({"install_root": "Existing Wakfu.app"}),
            str((self.root / "Existing Wakfu.app").resolve()),
        )
        legacy = self.root / "mini-launcher/config.json"
        legacy.parent.mkdir()
        legacy.write_text(json.dumps({"install_root": "../Existing Wakfu.app"}))
        self.assertEqual(backend.game_install({}), str(bundle.resolve()))
        self.assertEqual(
            (bundle / "lib/wakfu-client.jar").read_bytes(), b"fixture-unmodified"
        )

    def test_keychain_helper_receives_secrets_over_stdin_only_and_fails_closed(self):
        # Restore the real wrapper while the storage backend remains patched elsewhere.
        original = self.patches[-1].temp_original
        with patch.object(backend.Path, "is_file", return_value=True), patch.object(
            backend.subprocess,
            "run",
            return_value=Mock(returncode=0, stdout='{"ok":true,"value":"restored"}'),
        ) as process:
            self.assertEqual(original("set", "a" * 64, "stdin-only-secret"), "restored")
        args, kwargs = process.call_args
        self.assertNotIn("stdin-only-secret", str(args))
        self.assertEqual(json.loads(kwargs["input"])["value"], "stdin-only-secret")
        self.assertTrue(kwargs["capture_output"])
        with patch.object(backend.Path, "is_file", return_value=True), patch.object(
            backend.subprocess,
            "run",
            return_value=Mock(returncode=1, stdout="not-json"),
        ), self.assertRaises(backend.LauncherError):
            original("get", "a" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
