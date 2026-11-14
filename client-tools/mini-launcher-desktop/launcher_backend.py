"""Portable launcher persistence, OS credential protection and game startup."""
import argparse
import base64
import ctypes
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(
    os.environ.get("WAKFU_LAUNCHER_ROOT", Path(__file__).resolve().parent.parent)
).expanduser().resolve()
STATE_PATH = ROOT / "profile/launcher-state.json"
BUNDLED_CA = Path(__file__).resolve().parent / "cacert.pem"
if sys.platform == "darwin" and BUNDLED_CA.is_file():
    os.environ.setdefault("SSL_CERT_FILE", str(BUNDLED_CA))


class LauncherError(ValueError):
    """A message safe to display without exposing credentials or server bodies."""


LINUX_STORAGE_ERROR = (
    "Secure password storage is unavailable. Start a Secret Service keyring "
    "or turn off Save account and password."
)
SECRET_SERVICE_NAME = "net.hectorpulido.wakfu.minilauncher"


def secret_service_backend():
    """Use only the secure Secret Service backend, never keyring fallback storage."""
    try:
        from keyring.backends.SecretService import Keyring

        backend = Keyring()
        if backend.priority <= 0:
            raise ValueError()
        return backend
    except Exception:
        # Missing dependencies, an unavailable D-Bus session, or disabled secure
        # storage must not fall back to plaintext or expose system diagnostics.
        raise LauncherError(LINUX_STORAGE_ERROR) from None


def credential_storage_available():
    if sys.platform.startswith("linux"):
        try:
            secret_service_backend()
            return True
        except LauncherError:
            return False
    return sys.platform in ("darwin", "win32")


def secret_service(action, identifier, value=""):
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[a-f0-9]{32,64}", identifier
    ):
        raise LauncherError("The saved credential reference is invalid.")
    backend = secret_service_backend()
    try:
        if action == "set":
            backend.set_password(SECRET_SERVICE_NAME, identifier, value)
            return ""
        if action == "get":
            result = backend.get_password(SECRET_SERVICE_NAME, identifier)
            if not isinstance(result, str):
                raise ValueError()
            return result
        if action == "delete":
            from keyring.errors import PasswordDeleteError

            try:
                backend.delete_password(SECRET_SERVICE_NAME, identifier)
            except PasswordDeleteError:
                pass  # Forgetting an already removed secret is idempotent.
            return ""
        raise ValueError()
    except Exception:
        raise LauncherError(LINUX_STORAGE_ERROR) from None


def _crypt(value, decrypt=False):
    if os.name != "nt":
        raise LauncherError("Encrypted password storage requires Windows.")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        method = crypt32.CryptUnprotectData
        method.argtypes = [
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
        args = (ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        method = crypt32.CryptProtectData
        method.argtypes = [
            ctypes.POINTER(Blob),
            wintypes.LPCWSTR,
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
        args = (
            ctypes.byref(source),
            "Wakfu mini launcher",
            None,
            None,
            None,
            1,
            ctypes.byref(target),
        )
    method.restype = wintypes.BOOL
    if not method(*args):
        raise LauncherError(
            "Windows could not unlock the saved credentials. Enter your password again."
        )
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def keychain(action, identifier, value=""):
    helper = Path(__file__).resolve().parent / "keychain-helper"
    if not helper.is_file():
        raise LauncherError("The macOS Keychain component is missing.")
    result = subprocess.run(
        [str(helper)],
        input=json.dumps({"action": action, "id": identifier, "value": value}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
    )
    try:
        payload = json.loads(result.stdout)
        if result.returncode or not payload.get("ok"):
            raise ValueError()
        return payload.get("value", "")
    except (ValueError, TypeError):
        raise LauncherError(
            "Could not access Keychain. Allow Wakfu access or turn off password saving."
        ) from None


def remove_protected(encoded):
    if (
        sys.platform == "darwin"
        and isinstance(encoded, str)
        and encoded.startswith("keychain:")
    ):
        keychain("delete", encoded[9:])
    elif (
        sys.platform.startswith("linux")
        and isinstance(encoded, str)
        and encoded.startswith("secretservice:")
    ):
        secret_service("delete", encoded[len("secretservice:"):])


def forget_renewal(folder):
    path = Path(folder) / "remember.json"
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and path.is_file():
        try:
            encoded = json.loads(path.read_text(encoding="utf-8")).get(
                "protected_token"
            )
        except (ValueError, TypeError, AttributeError):
            encoded = None
        remove_protected(encoded)
    path.unlink(missing_ok=True)


def protect(text):
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        identifier = uuid.uuid4().hex
        try:
            secret = json.loads(text)
            if secret.get("scope") and secret.get("username"):
                identifier = hashlib.sha256(
                    (
                        str(ROOT.resolve())
                        + "\0"
                        + secret["scope"]
                        + "\0"
                        + secret["username"]
                    ).encode()
                ).hexdigest()
        except (ValueError, AttributeError, TypeError):
            pass
        if sys.platform == "darwin":
            keychain("set", identifier, text)
            return "keychain:" + identifier
        secret_service("set", identifier, text)
        return "secretservice:" + identifier
    return base64.b64encode(_crypt(text.encode("utf-8"))).decode("ascii")


def unprotect(encoded):
    if sys.platform == "darwin":
        if not isinstance(encoded, str) or not encoded.startswith("keychain:"):
            raise LauncherError(
                "These saved credentials belong to another operating system. Enter your password."
            )
        return keychain("get", encoded[9:])
    if sys.platform.startswith("linux"):
        if not isinstance(encoded, str) or not encoded.startswith("secretservice:"):
            raise LauncherError(
                "These saved credentials belong to another operating system. Enter your password."
            )
        return secret_service("get", encoded[len("secretservice:"):])
    try:
        data = base64.b64decode(encoded, validate=True)
        return _crypt(data, decrypt=True).decode("utf-8")
    except (ValueError, UnicodeError, TypeError):
        raise LauncherError(
            "Could not unlock the saved credentials. Enter your password again."
        ) from None


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            staged = Path(output.name)
            if hasattr(os, "fchmod"):
                os.fchmod(output.fileno(), 0o600)
            json.dump(value, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        staged.replace(path)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def host(value):
    value = str(value).strip().lower().rstrip(".")
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError:
        pass
    if (
        not value
        or len(value) > 253
        or re.fullmatch(r"[0-9.]+", value)
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in value.split(".")
        )
    ):
        raise LauncherError("Enter a valid IPv4 address or server hostname.")
    return value


def port(value):
    if isinstance(value, bool):
        raise LauncherError("Ports must be between 1 and 65535.")
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise LauncherError("Ports must be between 1 and 65535.") from None
    if str(result) != str(value).strip() or not 1 <= result <= 65535:
        raise LauncherError("Ports must be between 1 and 65535.")
    return result


def url(value):
    value = str(value).strip().rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError()
        host(parsed.hostname)
        if parsed.port is not None:
            port(parsed.port)
    except (ValueError, TypeError):
        raise LauncherError(
            "Use an http://host:port or https://host:port address without a path or credentials."
        ) from None
    return value


def normalize_server(raw):
    if not isinstance(raw, dict):
        raise LauncherError("The server configuration is invalid.")
    identifier = raw.get("id") or uuid.uuid4().hex
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,64}", identifier
    ):
        raise LauncherError("The server identifier is invalid.")
    game_ports = raw.get("game_ports", [15556])
    if isinstance(game_ports, str):
        game_ports = [p.strip() for p in game_ports.split(",") if p.strip()]
    if not isinstance(game_ports, list) or not 1 <= len(game_ports) <= 16:
        raise LauncherError("Enter one or more game ports, separated by commas.")
    name = str(raw.get("name", "Server")).strip()
    if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise LauncherError("Enter a server name of up to 80 characters.")
    result = dict(
        id=identifier,
        name=name,
        server_host=host(raw.get("server_host", "")),
        dispatch_port=port(raw.get("dispatch_port", 15558)),
        game_ports=list(dict.fromkeys(port(p) for p in game_ports)),
        chat_host=host(raw.get("chat_host") or raw.get("server_host", "")),
        chat_port=port(raw.get("chat_port", 16337)),
        api_url=url(raw.get("api_url", "")),
        http_url=url(raw.get("http_url", "")),
        shop_url=url(raw.get("shop_url", "")),
        certificate=str(raw.get("certificate", "")).strip(),
    )
    if result["certificate"]:
        path = Path(result["certificate"])
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise LauncherError(
                "The selected certificate was not found. Select the file or leave this field empty to use system trust."
            )
    result["achievements_url"] = url(
        raw.get("achievements_url") or "https://wakemu-adventures.p.hectorpulido.net"
    )
    result["install_root"] = str(raw.get("install_root", "")).strip()
    if "\x00" in result["install_root"]:
        raise LauncherError("The client folder is invalid.")
    return internet_server_names(result)


def certificate_path(server):
    value = server.get("certificate", "")
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def fingerprint(server):
    identity = {
        key: value
        for key, value in server.items()
        if key not in ("id", "name", "certificate", "install_root", "achievements_url")
    }
    for field in ("server_host", "chat_host"):
        if identity.get(field) in (
            "wakemu-game.p.hectorpulido.net",
            "wakemu.p.hectorpulido.net",
        ):
            identity[field] = "dashboard.pangolin.hectorpulido.net"
    for field, old_origin in (
        ("api_url", "https://wakemu-auth.p.hectorpulido.net"),
        ("http_url", "https://wakemu-resources.p.hectorpulido.net"),
        ("shop_url", "https://wakemu-shop.p.hectorpulido.net"),
    ):
        if identity.get(field) == "https://wakemu.p.hectorpulido.net":
            identity[field] = old_origin
    achievement_origin = (
        server.get("achievements_url") or "https://wakemu-adventures.p.hectorpulido.net"
    )
    if achievement_origin == "https://wakemu.p.hectorpulido.net":
        achievement_origin = "https://wakemu-adventures.p.hectorpulido.net"
    if achievement_origin != "https://wakemu-adventures.p.hectorpulido.net":
        identity["achievements_url"] = achievement_origin
    cert = certificate_path(server)
    identity["certificate_sha256"] = (
        hashlib.sha256(cert.read_bytes()).hexdigest() if cert else "system"
    )
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def account_key(server, username):
    return hashlib.sha256((fingerprint(server) + "\0" + username).encode()).hexdigest()


def internet_server_names(server):
    # Verified aliases of the same game entrypoint share the existing account
    # identity, while the UI presents one public domain for every service.
    unified = "wakemu.p.hectorpulido.net"
    origin = "https://" + unified
    if server.get("api_url") in ("https://wakemu-auth.p.hectorpulido.net", origin):
        server = dict(server)
        for field in ("server_host", "chat_host"):
            if server.get(field) in (
                "dashboard.pangolin.hectorpulido.net",
                "wakemu-game.p.hectorpulido.net",
            ):
                server[field] = unified
        for field, previous in (
            ("api_url", "https://wakemu-auth.p.hectorpulido.net"),
            ("http_url", "https://wakemu-resources.p.hectorpulido.net"),
            ("shop_url", "https://wakemu-shop.p.hectorpulido.net"),
            ("achievements_url", "https://wakemu-adventures.p.hectorpulido.net"),
        ):
            if server.get(field) == previous:
                server[field] = origin
    return server


def default_state():
    local = dict(
        id="local",
        name="Wakemu Local",
        server_host="127.0.0.1",
        dispatch_port=15558,
        game_ports=[15556],
        chat_host="127.0.0.1",
        chat_port=16337,
        http_url="http://127.0.0.1:18081",
        shop_url="http://127.0.0.1:18083",
        api_url="http://127.0.0.1:18081",
        certificate="",
        achievements_url="http://127.0.0.1:18081",
        install_root="",
    )
    internet = dict(
        id="internet",
        name="Wakemu Internet",
        server_host="wakemu.p.hectorpulido.net",
        dispatch_port=15558,
        game_ports=[15556],
        chat_host="wakemu.p.hectorpulido.net",
        chat_port=16337,
        http_url="https://wakemu.p.hectorpulido.net",
        shop_url="https://wakemu.p.hectorpulido.net",
        api_url="https://wakemu.p.hectorpulido.net",
        certificate="",
        achievements_url="https://wakemu.p.hectorpulido.net",
        install_root="",
    )
    return {
        "version": 1,
        "servers": [local, internet],
        "selected_id": "local",
        "selected_username": "",
        "accounts": {},
    }


def load_state():
    if not STATE_PATH.exists():
        return default_state()
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if (
            value.get("version") != 1
            or not isinstance(value.get("servers"), list)
            or not isinstance(value.get("accounts"), dict)
        ):
            raise ValueError()
        value["servers"] = [
            internet_server_names(server) for server in value["servers"]
        ]
        return value
    except (OSError, ValueError, TypeError, AttributeError):
        raise LauncherError(
            "Could not read the launcher settings. Keep the file and check profile/launcher-state.json."
        ) from None


def selected_server(state, data):
    identifier = data.get("selected_id", state["selected_id"])
    return next(
        (s for s in state["servers"] if s["id"] == identifier), state["servers"][0]
    )


def public_state(state, data=None):
    data = data or {}
    server = selected_server(state, data)
    scope = fingerprint(server)
    accounts = sorted(
        a["username"] for a in state["accounts"].values() if a.get("scope") == scope
    )
    username = str(
        data.get(
            "username",
            state.get("selected_usernames", {}).get(
                server["id"],
                state.get("selected_username", "")
                if state["selected_id"] == server["id"]
                else "",
            ),
        )
    )
    saved = state["accounts"].get(account_key(server, username), {})
    password = ""
    if saved.get("protected"):
        try:
            secret = json.loads(unprotect(saved["protected"]))
            if secret.get("scope") == scope and secret.get("username") == username:
                password = secret.get("password", "")
        except (ValueError, KeyError, TypeError):
            pass
    storage_available = credential_storage_available()
    return {
        "servers": state["servers"],
        "selected_id": server["id"],
        "accounts": accounts,
        "selected_username": username,
        "username": username,
        "password": password,
        "remember": (bool(saved.get("protected", False)) if username else True)
        and storage_available,
        "credential_storage_available": storage_available,
    }


def save(data):
    state = load_state()
    server = normalize_server(data["server"])
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    if (
        len(username) > 128
        or any(ord(c) < 32 for c in username)
        or not isinstance(password, str)
        or len(password) > 256
    ):
        raise LauncherError("Check your username and password.")
    remember = data.get(
        "remember", credential_storage_available() if sys.platform.startswith("linux") else True
    )
    if not isinstance(remember, bool):
        raise LauncherError("The remember credentials option is invalid.")
    previous = next((s for s in state["servers"] if s["id"] == server["id"]), None)
    changed = previous is not None and fingerprint(previous) != fingerprint(server)
    if changed and password and not data.get("password_edited", False):
        password = ""
    state["servers"] = [s for s in state["servers"] if s["id"] != server["id"]] + [
        server
    ]
    state["selected_id"] = server["id"]
    state["selected_username"] = username
    state.setdefault("selected_usernames", {})[server["id"]] = username
    if username:
        key = account_key(server, username)
        scope = fingerprint(server)
        saved = state["accounts"].get(key, {})
        old_secret = {}
        if saved.get("protected"):
            try:
                candidate = json.loads(unprotect(saved["protected"]))
                if (
                    candidate.get("scope") == scope
                    and candidate.get("username") == username
                ):
                    old_secret = candidate
            except (ValueError, TypeError):
                pass
        # Username edits temporarily clear the UI password. Preserve an existing
        # matching access, but never create one for an incomplete username entry.
        if (
            remember
            and not password
            and not data.get("password_edited", False)
            and not changed
        ):
            password = old_secret.get("password", "")
        if remember and password:
            secret = {"scope": scope, "username": username, "password": password}
            if old_secret.get("password") == password:
                secret["remember_token"] = old_secret.get("remember_token", "")
            state["accounts"][key] = {
                "username": username,
                "scope": scope,
                "protected": protect(json.dumps(secret)),
            }
        else:
            removed = state["accounts"].pop(key, {})
            remove_protected(removed.get("protected"))
            forget_renewal(ROOT / "profile/accounts" / key)
    private_write(STATE_PATH, state)
    return state, server, username, password, remember


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LauncherError(
            "The server tried to redirect sign-in to another address. Check the authentication URL."
        )


def api_request(server, route, body):
    context = ssl.create_default_context(
        cafile=str(certificate_path(server)) if certificate_path(server) else None
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
        urllib.request.HTTPSHandler(context=context),
    )
    request = urllib.request.Request(
        server["api_url"] + route,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=12) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except urllib.error.HTTPError as error:
        if route == "/register" and error.code in (400, 409):
            try:
                detail = json.loads(error.read(4096)).get("error")
            except (ValueError, AttributeError, OSError):
                detail = None
            # Match the native server's approved messages without exposing raw
            # upstream text or leaking its language into the English launcher.
            approved = {
                "Ese usuario ya existe.": "That username already exists.",
                "Usuario: 3–32 letras, números, guion o guion bajo.":
                    "Username: 3–32 letters, numbers, hyphens, or underscores.",
                "Contraseña: 8–256 caracteres.": "Password: 8–256 characters.",
            }
            if isinstance(detail, str) and detail in approved:
                raise LauncherError(approved[detail]) from None
            raise LauncherError(
                "The server rejected registration. Check the username or choose another name."
            ) from None
        if error.code == 429:
            raise LauncherError(
                "Too many attempts. Wait a minute and try again."
            ) from None
        if error.code == 401:
            raise LauncherError(
                "The username or password is incorrect, or the saved credentials have expired."
            ) from None
        raise LauncherError(
            "The server rejected sign-in (HTTP %s)." % error.code
        ) from None
    except (urllib.error.URLError, ssl.SSLError):
        raise LauncherError(
            "Could not connect to authentication. Check its address and certificate."
        ) from None
    except (ValueError, KeyError):
        raise LauncherError("The authentication response is invalid.") from None


def game_install(server):
    if server.get("install_root"):
        path = Path(server["install_root"]).expanduser()
        return str(path if path.is_absolute() else (ROOT / path).resolve())
    candidates = [ROOT / "client", ROOT]
    legacy = ROOT / "mini-launcher/config.json"
    if legacy.is_file():
        try:
            configured = json.loads(legacy.read_text()).get("install_root")
            if configured:
                configured = Path(configured).expanduser()
                candidates.append(
                    configured
                    if configured.is_absolute()
                    else legacy.parent / configured
                )
        except (ValueError, OSError, TypeError):
            pass
    for path in candidates:
        for location in (path, path / "Contents/Resources", path / "client"):
            if (location / "lib/wakfu-client.jar").is_file():
                return str(location.resolve())
    return str(ROOT / "client")


def discover(data):
    current = normalize_server(data.get("server"))
    domain = current["server_host"]
    authentication = urllib.parse.urlsplit(current["api_url"])
    try:
        loopback = ipaddress.IPv4Address(domain).is_loopback
    except ipaddress.AddressValueError:
        loopback = domain == "localhost"
    if (
        loopback
        and authentication.scheme == "http"
        and authentication.hostname == domain
    ):
        return {
            "ok": True,
            "server": current,
            "message": "Local server settings loaded. Use Advanced settings to change ports and services.",
        }
    origin = "https://" + domain
    cert = (
        certificate_path(current)
        if urllib.parse.urlsplit(current["api_url"]).hostname == domain
        else None
    )
    context = ssl.create_default_context(cafile=str(cert) if cert else None)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
        urllib.request.HTTPSHandler(context=context),
    )
    request = urllib.request.Request(
        origin + "/launcher/config", headers={"Accept": "application/json"}
    )
    try:
        with opener.open(request, timeout=12) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError()
        manifest = json.loads(raw)
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
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("version")) is not int
            or manifest["version"] != 1
            or any(key not in manifest for key in fields)
        ):
            raise ValueError()
        if (
            manifest.get("certificate", "") != ""
            or manifest["server_host"] != domain
            or manifest["chat_host"] != domain
        ):
            raise ValueError()
        for field in ("api_url", "http_url", "shop_url", "achievements_url"):
            if url(manifest[field]) != origin:
                raise ValueError()
        discovered = dict(current)
        discovered.update({key: manifest[key] for key in fields})
        discovered["certificate"] = current.get("certificate", "")
        discovered = normalize_server(discovered)
    except (urllib.error.URLError, ssl.SSLError, OSError):
        raise LauncherError(
            "Could not detect the server. Check the domain or open Advanced settings."
        ) from None
    except (ValueError, TypeError, KeyError):
        raise LauncherError(
            "The server returned invalid automatic settings."
        ) from None
    return {
        "ok": True,
        "server": discovered,
        "message": "Server detected. Ports and services were configured automatically.",
    }


def register(data):
    server = normalize_server(data.get("server"))
    raw_username = data.get("username", "")
    if not isinstance(raw_username, str):
        raise LauncherError("Username: 3–32 letters, numbers, hyphens, or underscores.")
    username = raw_username.strip()
    password = data.get("password", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username):
        raise LauncherError("Username: 3–32 letters, numbers, hyphens, or underscores.")
    if not isinstance(password, str) or not 8 <= len(password) <= 256:
        raise LauncherError("Password: 8–256 characters.")
    if password != data.get("password_confirm"):
        raise LauncherError("The passwords do not match.")
    if type(data.get("remember", True)) is not bool:
        raise LauncherError("The remember credentials option is invalid.")
    existing_state = load_state()
    result = api_request(
        server, "/register", {"username": username, "password": password}
    )
    account = result.get("account", result)
    if (
        not isinstance(account, dict)
        or type(account.get("id")) is not int
        or account["id"] <= 0
        or not isinstance(account.get("username"), str)
        or account["username"].casefold() != username.casefold()
    ):
        raise LauncherError(
            "The server did not confirm the account identity. Check the username before registering again."
        )
    selected = dict(
        data, server=server, username=account["username"], password_edited=True
    )
    try:
        state, server, username, _, _ = save(selected)
        visible = public_state(
            state, {"selected_id": server["id"], "username": username}
        )
        message = "Account created. You can now click Play and create your character."
    except (LauncherError, OSError, subprocess.SubprocessError):
        # Account creation already committed on the server. Do not disguise a
        # local Keychain/filesystem failure as a failed remote registration.
        state = existing_state
        state["servers"] = [s for s in state["servers"] if s["id"] != server["id"]] + [
            server
        ]
        state["selected_id"] = server["id"]
        visible = public_state(
            state, {"selected_id": server["id"], "username": account["username"]}
        )
        visible["remember"] = False
        message = "Account created. Could not save credentials on this computer; keep your password and click Play."
    visible["password"] = password
    return {"ok": True, "state": visible, "message": message}


def web_login(data):
    _, server, username, password, _ = save(data)
    if not username or not password:
        raise LauncherError("Enter your username and password to open achievements.")
    origin = server["achievements_url"]
    parsed_origin = urllib.parse.urlsplit(origin)
    if parsed_origin.scheme != "https":
        try:
            local = ipaddress.ip_address(parsed_origin.hostname).is_private
        except ValueError:
            local = parsed_origin.hostname == "localhost"
        if not local:
            raise LauncherError("Use HTTPS to access achievements over the Internet.")
    destination = dict(server, api_url=origin)
    if parsed_origin.hostname != urllib.parse.urlsplit(server["api_url"]).hostname:
        destination["certificate"] = ""
    result = api_request(
        destination, "/launcher/login", {"username": username, "password": password}
    )
    parsed = urllib.parse.urlsplit(result.get("url", ""))
    expected = urllib.parse.urlsplit(origin)
    if (parsed.scheme, parsed.netloc, parsed.path, parsed.query) != (
        expected.scheme,
        expected.netloc,
        "/player/",
        "",
    ) or not re.fullmatch(r"token=[A-Za-z0-9_-]{40,128}", parsed.fragment):
        raise LauncherError(
            "The achievements address returned by the server is invalid."
        )
    return {
        "ok": True,
        "url": result["url"],
        "message": "Achievements connected. Actions apply to the character currently online on this account.",
    }


def await_startup(process, status_path, log, timeout=30):
    deadline = time.monotonic() + timeout
    try:
        while True:
            if status_path.is_file():
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                    if status.get("status") == "ready":
                        return
                except (ValueError, OSError, AttributeError):
                    pass
            if process.poll() is not None:
                raise LauncherError(
                    "Wakfu closed during startup. Check the log: " + str(log)
                )
            if time.monotonic() >= deadline:
                raise LauncherError(
                    "The client has not confirmed startup yet. Check the log: "
                    + str(log)
                )
            time.sleep(0.1)
    finally:
        status_path.unlink(missing_ok=True)


def launch(data):
    state, server, username, password, remember = save(data)
    if not username or not password:
        raise LauncherError("Enter your username and password to sign in.")
    if (
        sys.platform == "darwin"
        and not (Path(game_install(server)) / "lib/wakfu-client.jar").is_file()
    ):
        raise LauncherError(
            "Select your Wakfu 1.93.1+79 installation under Client folder before playing."
        )
    result = api_request(
        server,
        "/login",
        {"username": username, "password": password, "remember": remember},
    )
    account = result.get("account", {})
    if (
        not isinstance(account.get("username"), str)
        or not isinstance(account.get("id"), int)
        or not isinstance(result.get("api_token"), str)
        or not result["api_token"]
    ):
        raise LauncherError(
            "The authentication response does not contain a valid account."
        )
    # The server may canonicalize account names, but must not switch identities.
    if account["username"].casefold() != username.casefold():
        raise LauncherError(
            "The account returned by the server does not match the requested account."
        )
    key = account_key(server, username)
    folder = ROOT / "profile/accounts" / key
    folder.mkdir(parents=True, exist_ok=True)
    forget_renewal(folder)
    if (
        remember
        and isinstance(result.get("remember_token"), str)
        and result["remember_token"]
    ):
        secret = {
            "scope": fingerprint(server),
            "username": username,
            "password": password,
            "remember_token": result["remember_token"],
        }
        state["accounts"][key]["protected"] = protect(json.dumps(secret))
        private_write(STATE_PATH, state)
        private_write(
            folder / "remember.json",
            {
                "username": account["username"],
                "account_id": account["id"],
                "protected_token": protect(result["remember_token"]),
            },
        )
    else:
        forget_renewal(folder)
    # Persist remember tokens only in the operating system's secure storage.
    session = dict(result)
    session.pop("remember_token", None)
    token_file = folder / "login-session.json"
    private_write(token_file, session)
    config = dict(
        server,
        runtime_root=str(folder),
        install_root=game_install(server),
        runner=str(ROOT / "mini-launcher/run-client.py"),
        open_planting=True,
        open_dungeon_missions=False,
    )
    config["certificate"] = (
        str(certificate_path(server)) if certificate_path(server) else ""
    )
    config_path = folder / "config.json"
    private_write(config_path, config)
    env = dict(os.environ)
    for name in (
        "WAKFU_SERVER_IPV4",
        "WAKFU_SERVER_NAME",
        "WAKFU_AGENT_ROOT",
        "WAKFU_REPOSITORY_BRIDGE",
        "WAKFU_CAPTURE_AGENT",
        "WAKFU_RESOLVED_HOSTS",
        "WAKFU_LAUNCH_STATUS_FILE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    ):
        env.pop(name, None)
    env.update(
        WAKFU_LAUNCHER_CONFIG=str(config_path),
        WAKFU_LOCAL_PROFILE="main",
        PYTHONDONTWRITEBYTECODE="1",
    )
    if certificate_path(server):
        env["SSL_CERT_FILE"] = str(certificate_path(server))
    elif sys.platform == "darwin" and BUNDLED_CA.is_file():
        env["SSL_CERT_FILE"] = str(BUNDLED_CA)
    (folder / "logs").mkdir(exist_ok=True)
    log = folder / "logs/launcher.log"
    status_path = folder / ("startup-" + uuid.uuid4().hex + ".json")
    env["WAKFU_LAUNCH_STATUS_FILE"] = str(status_path)
    with log.open("ab") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(ROOT / "mini-launcher/run-client.py"),
                "--token-file",
                str(token_file),
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    await_startup(process, status_path, log)
    return {
        "ok": True,
        "pid": process.pid,
        "log": str(log),
        "message": "Wakfu started. The client confirmed its connection to the launcher.",
    }


def check(data):
    server = normalize_server(data["server"])
    endpoints = [
        ("Dispatcher", server["server_host"], server["dispatch_port"]),
        ("Chat", server["chat_host"], server["chat_port"]),
    ]
    endpoints += [("Game", server["server_host"], p) for p in server["game_ports"]]
    for name, field in (
        ("Authentication", "api_url"),
        ("Resources", "http_url"),
        ("Shop", "shop_url"),
    ):
        parsed = urllib.parse.urlsplit(server[field])
        endpoints.append(
            (
                name,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
        )
    checks = []
    for name, address, number in endpoints:
        try:
            with socket.create_connection((address, number), timeout=3):
                pass
            available = True
        except OSError:
            available = False
        checks.append(
            {"service": name, "host": address, "port": number, "ok": available}
        )
    good = all(c["ok"] for c in checks)
    return {
        "ok": True,
        "available": good,
        "checks": checks,
        "message": "All configured ports are responding."
        if good
        else "Some ports are not responding. Check the addresses and services.",
    }


def dispatch(action, data):
    if not isinstance(data, dict):
        raise LauncherError("The launcher data is invalid.")
    if action == "state":
        return {"ok": True, "state": public_state(load_state(), data)}
    if action == "save":
        state, server, username, _, _ = save(data)
        return {
            "ok": True,
            "state": public_state(
                state, {"selected_id": server["id"], "username": username}
            ),
        }
    if action == "play":
        return launch(data)
    if action == "check":
        return check(data)
    if action == "web-login":
        return web_login(data)
    if action == "register":
        return register(data)
    if action == "discover":
        return discover(data)
    if action == "forget":
        state = load_state()
        server = selected_server(state, data)
        username = str(data.get("username", state.get("selected_username", "")))
        key = account_key(server, username)
        removed = state["accounts"].pop(key, {})
        remove_protected(removed.get("protected"))
        forget_renewal(ROOT / "profile/accounts" / key)
        (ROOT / "profile/accounts" / key / "login-session.json").unlink(missing_ok=True)
        private_write(STATE_PATH, state)
        result = public_state(
            state, {"selected_id": server["id"], "username": username}
        )
        result["password"] = ""
        result["remember"] = False
        return {"ok": True, "state": result}
    raise LauncherError("Unknown launcher action.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=(
            "state",
            "save",
            "play",
            "check",
            "forget",
            "web-login",
            "register",
            "discover",
        ),
        required=True,
    )
    args = parser.parse_args()
    try:
        raw = sys.stdin.read(1024 * 1024)
        data = json.loads(raw.lstrip("\ufeff")) if raw.strip() else {}
        result = dispatch(args.action, data)
    except LauncherError as error:
        result = {"ok": False, "error": str(error)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result = {
            "ok": False,
            "error": "Could not complete the operation. Check the fields and folder permissions.",
        }
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
