"""Local operator HTTP API with bounded sessions, CSRF and static assets."""
from collections import deque
from datetime import date, datetime
from decimal import Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
from wakfu_server.admin_settings import SettingsConflict
from urllib.request import urlopen
from psycopg import IntegrityError


def load_credentials(path):
    """Create a local bootstrap secret once, without printing it to logs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        credentials = dict(username="admin", password=secrets.token_urlsafe(24))
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as output:
                json.dump(credentials, output)
                output.write("\n")
    os.chmod(path, 0o600)
    credentials = json.loads(path.read_text())
    if (
        not isinstance(credentials, dict)
        or not isinstance(credentials.get("username"), str)
        or not isinstance(credentials.get("password"), str)
        or not 1 <= len(credentials["username"]) <= 100
        or not 12 <= len(credentials["password"]) <= 256
    ):
        raise ValueError(
            "Admin credentials file requires username and password of at least 12 characters"
        )
    return credentials


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value)
    raise TypeError(type(value).__name__)


def make_server(service, host="127.0.0.1", port=0, credentials=None, static_dir=None):
    if credentials is None:
        credentials = load_credentials(
            os.environ.get(
                "WAKFU_ADMIN_CREDENTIALS_FILE", "/data/admin-credentials.json"
            )
        )
    from wakfu_server.admin_sessions import (
        MemoryAdminSessions,
        PostgresAdminSessions,
        SessionCapacity,
    )

    credential_revision = hashlib.sha256(
        (credentials["username"] + "\0" + credentials["password"]).encode()
    ).hexdigest()
    session_store = (
        PostgresAdminSessions(service.store, credential_revision)
        if getattr(service, "store", None) is not None
        else MemoryAdminSessions()
    )
    failures = {}
    lock = threading.Lock()
    # Keep only a password verifier in the long-lived HTTP closure.
    username = credentials["username"]
    salt = secrets.token_bytes(16)

    def password_hash(password):
        return hashlib.scrypt(
            password.encode(), salt=salt, n=16384, r=8, p=1, maxmem=64 * 1024 * 1024
        )

    verifier = password_hash(credentials["password"])
    static_root = Path(
        static_dir or os.environ.get("WAKFU_ADMIN_STATIC_DIR", "/app/static")
    ).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "WakemuAdmin/1"

        def log_message(self, format, *args):
            # URLs can contain account searches; never write them to access logs.
            pass

        def respond(self, status, payload, cookie=None):
            raw = json.dumps(payload, default=_json, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def body(self, maximum=32768):
            if self.headers.get_content_type() != "application/json":
                raise ValueError("JSON body required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= maximum:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            return data

        def auth(self, mutation=False):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
                token = cookie["wakemu_admin"].value
            except (KeyError, ValueError):
                raise PermissionError("Authentication required")
            result = session_store.get(token)
            if result is None:
                raise PermissionError("Authentication required")
            if mutation and not hmac.compare_digest(
                self.headers.get("X-CSRF-Token", ""), result["csrf_token"]
            ):
                raise CSRFError("Invalid CSRF token")
            return token, result

        def handle_request(self):
            parsed = urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            mutation = self.command != "GET"
            try:
                if path == "/health" and not mutation:
                    self.respond(200, dict(ok=True, service="admin"))
                    return
                if path == "/api/login" and self.command == "POST":
                    data = self.body()
                    peer = self.client_address[0]
                    now = time.monotonic()
                    with lock:
                        attempts = failures.setdefault(peer, deque())
                        while attempts and attempts[0] < now - 300:
                            attempts.popleft()
                        if len(attempts) >= 10:
                            self.respond(
                                429,
                                dict(
                                    error="Too many login attempts; retry in five minutes"
                                ),
                            )
                            return
                        attempts.append(now)
                    password = data.get("password", "")
                    candidate = password_hash(
                        password
                        if isinstance(password, str) and len(password) <= 256
                        else ""
                    )
                    if not hmac.compare_digest(
                        str(data.get("username", "")), username
                    ) or not hmac.compare_digest(candidate, verifier):
                        self.respond(401, dict(error="Invalid credentials"))
                        return
                    token = secrets.token_urlsafe(32)
                    try:
                        session = session_store.create(
                            token, username, secrets.token_urlsafe(32)
                        )
                    except SessionCapacity as error:
                        self.respond(429, dict(error=str(error)))
                        return
                    with lock:
                        failures.pop(peer, None)
                    self.respond(
                        200,
                        dict(username=username, csrf_token=session["csrf_token"]),
                        self.cookie(token),
                    )
                    return
                if not path.startswith("/api/"):
                    if mutation:
                        self.respond(405, dict(error="Method not allowed"))
                    else:
                        self.static(path)
                    return
                token, session = self.auth(mutation)
                if path == "/api/session" and not mutation:
                    self.respond(
                        200,
                        dict(
                            username=session["username"],
                            csrf_token=session["csrf_token"],
                        ),
                    )
                    return
                if path == "/api/logout" and self.command == "POST":
                    session_store.revoke(token)
                    self.respond(200, dict(ok=True), self.cookie("", expired=True))
                    return
                query = parse_qs(parsed.query)
                if path.startswith("/api/objectives/"):
                    from wakfu_server import admin_objectives

                    segments = path.removeprefix("/api/objectives/").split("/")
                    resource = segments[0]
                    if self.command == "POST" and segments == ["player-launch"]:
                        data = self.body()
                        if set(data) != {"character_id"}:
                            raise ValueError("Expected a character identifier")
                        result = admin_objectives.player_launch(
                            service.store, data["character_id"]
                        )
                        code = 200
                    elif (
                        self.command == "GET"
                        and len(segments) == 1
                        and resource
                        in (
                            "health",
                            "definitions",
                            "progress",
                            "events",
                            "rewards",
                            "reward-policies",
                            "rankings",
                            "challenge-profiles",
                        )
                    ):
                        upstream_path = (
                            "/health" if resource == "health" else "/v1/" + resource
                        )
                        code, result = admin_objectives.request(
                            "GET", upstream_path, parsed.query
                        )
                    elif (
                        self.command == "PUT"
                        and len(segments) == 2
                        and resource
                        in ("definitions", "reward-policies", "challenge-profiles")
                    ):
                        key = unquote(segments[1])
                        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}", key):
                            raise ValueError("Invalid objective key")
                        data = self.body(256 * 1024)
                        data["operator"] = session["username"]
                        code, result = admin_objectives.request(
                            "PUT", "/v1/" + resource + "/" + key, payload=data
                        )
                    elif (
                        self.command == "POST"
                        and len(segments) == 3
                        and resource == "events"
                        and segments[2] == "retry"
                    ):
                        if not segments[1].isdigit() or int(segments[1]) < 1:
                            raise ValueError("Invalid event identifier")
                        data = self.body()
                        data["operator"] = session["username"]
                        code, result = admin_objectives.request(
                            "POST", "/v1/events/" + segments[1] + "/retry", payload=data
                        )
                    else:
                        self.respond(405, dict(error="Method not allowed"))
                        return
                    self.respond(code, result)
                    return
                options = dict(
                    q=query.get("q", query.get("search", [""]))[0],
                    limit=int(query.get("limit", ["50"])[0]),
                    offset=int(query.get("offset", ["0"])[0]),
                )
                service.page(options["limit"], options["offset"])
                parts = path.removeprefix("/api/").split("/")
                resource = parts[0]
                identity = None
                if resource == "shop":
                    resource = parts[1] if len(parts) > 1 else ""
                    identity = int(parts[2]) if len(parts) > 2 else None
                elif (
                    resource in ("actions", "settings", "operations")
                    and len(parts) == 2
                ):
                    identity = unquote(parts[1])
                elif len(parts) > 1:
                    identity = int(parts[1])
                if not mutation:
                    if resource == "dashboard":
                        result = service.dashboard()
                        result["services"] = self.services()
                    elif resource == "accounts":
                        result = (
                            service.account(identity)
                            if identity is not None
                            else service.accounts(**options)
                        )
                    elif resource == "maps":
                        result = (
                            service.map(identity)
                            if identity is not None
                            else service.maps(**options)
                        )
                    elif resource == "characters":
                        result = (
                            service.character(identity)
                            if identity is not None
                            else service.characters(**options)
                        )
                    elif resource == "actions" and identity is not None:
                        result = service.action(identity)
                    elif resource == "profiler":
                        result = service.profiler()
                    elif resource == "settings":
                        result = (
                            service.setting(identity)
                            if identity is not None
                            else service.settings(**options)
                        )
                    elif resource == "operations" and identity is not None:
                        result = (
                            service.operation_services()
                            if identity == "services"
                            else service.operation(identity)
                        )
                    elif resource in ("categories", "articles"):
                        result = service.list_catalog(resource, **options)
                    elif resource == "orders":
                        result = service.orders(**options)
                    elif resource == "items":
                        result = service.items(**options)
                    elif resource == "audit":
                        result = service.audit(**options)
                    else:
                        raise LookupError("API route not found")
                else:
                    if self.command not in ("POST", "PATCH", "DELETE"):
                        self.respond(405, dict(error="Method not allowed"))
                        return
                    data = (
                        {"enabled": False}
                        if self.command == "DELETE"
                        else self.body(
                            8 * 1024 * 1024 if resource == "settings" else 32768
                        )
                    )
                    operator = session["username"]
                    if (
                        resource == "settings"
                        and self.command == "PATCH"
                        and identity is not None
                    ):
                        result = service.update_setting(identity, data, operator)
                    elif (
                        resource == "operations"
                        and self.command == "POST"
                        and identity == "restart"
                    ):
                        result = service.restart_service(data, operator)
                    elif (
                        resource == "accounts"
                        and self.command == "POST"
                        and identity is None
                    ):
                        result = service.create_account(data, operator)
                    elif (
                        resource == "accounts"
                        and self.command == "POST"
                        and identity is not None
                        and len(parts) == 3
                        and parts[2] in ("ban", "unban")
                    ):
                        method = (
                            service.ban_account
                            if parts[2] == "ban"
                            else service.unban_account
                        )
                        result = method(identity, data, operator)
                    elif (
                        resource == "accounts"
                        and self.command == "PATCH"
                        and identity is not None
                    ):
                        result = service.update_account(identity, data, operator)
                    elif (
                        resource == "maps"
                        and self.command == "PATCH"
                        and identity is not None
                    ):
                        result = service.update_map(identity, data, operator)
                    elif (
                        resource == "characters"
                        and self.command == "POST"
                        and identity is not None
                        and len(parts) == 3
                    ):
                        if parts[2] == "items":
                            result = service.grant_item(identity, data, operator)
                        elif parts[2] == "teleport":
                            result = service.teleport_character(
                                identity, data, operator
                            )
                        else:
                            raise LookupError("API route not found")
                    elif resource in ("categories", "articles") and (
                        (self.command == "POST" and identity is None)
                        or (
                            self.command in ("PATCH", "DELETE") and identity is not None
                        )
                    ):
                        result = service.save_catalog(
                            resource, identity, data, operator
                        )
                    else:
                        raise LookupError("API route not found")
                self.respond(200, result)
            except SettingsConflict as error:
                self.respond(409, dict(error=str(error)))
            except CSRFError as error:
                self.respond(403, dict(error=str(error)))
            except PermissionError as error:
                self.respond(401, dict(error=str(error)))
            except LookupError as error:
                self.respond(404, dict(error=str(error)))
            except (ValueError, TypeError, UnicodeError) as error:
                self.respond(400, dict(error=str(error)))
            except IntegrityError:
                self.respond(
                    409, dict(error="Conflicting key or invalid database reference")
                )
            except Exception:
                import logging

                logging.exception("Admin request failed")
                self.respond(500, dict(error="Internal administration error"))

        @staticmethod
        def cookie(token, expired=False):
            secure = (
                "; Secure" if os.environ.get("WAKFU_ADMIN_SECURE_COOKIE") == "1" else ""
            )
            return (
                "wakemu_admin="
                + token
                + "; Path=/; HttpOnly; SameSite=Strict; Max-Age="
                + ("0" if expired else "28800")
                + secure
            )

        def services(self):
            from wakfu_server import admin_objectives

            result = {}
            for name, default in (
                ("world", "http://world:18081"),
                ("shop", "http://shop:18083"),
            ):
                address = os.environ.get("WAKFU_" + name.upper() + "_URL", default)
                try:
                    with urlopen(
                        address.rstrip("/") + "/health", timeout=1
                    ) as response:
                        state = json.loads(response.read(32768))
                    result[name] = dict(
                        ok=state.get("ok") is True or state.get("status") == "ok",
                        detail=state,
                    )
                except Exception:
                    result[name] = dict(ok=False)
            code, state = admin_objectives.request("GET", "/health")
            result["objectives"] = dict(
                ok=code == 200
                and (state.get("ok") is True or state.get("status") == "ok")
            )
            return result

        def static(self, path):
            relative = (
                "index.html"
                if path == "/"
                else path.removeprefix("/static/").lstrip("/")
            )
            target = (static_root / relative).resolve()
            if not target.is_relative_to(static_root) or not target.is_file():
                self.respond(404, dict(error="Asset not found"))
                return
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(str(target))[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(raw)

        do_GET = handle_request
        do_POST = handle_request
        do_PATCH = handle_request
        do_PUT = handle_request
        do_DELETE = handle_request

    return ThreadingHTTPServer((host, port), Handler)


class CSRFError(Exception):
    pass
