"""Expose native-account Adventures without exposing operator routes or credentials."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import threading
import time
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 8192
MAX_RESPONSE = 4 * 1024 * 1024
PUBLIC_ORIGIN = os.environ.get(
    "PUBLIC_ADVENTURES_ORIGIN", "https://wakemu-adventures.p.hectorpulido.net"
).rstrip("/")
UNIFIED_ORIGIN = os.environ.get(
    "PUBLIC_UNIFIED_ORIGIN", "https://wakemu.p.hectorpulido.net"
).rstrip("/")
AUTH_HOST = os.environ.get("AUTH_HOST", "remote-auth")
AUTH_PORT = int(os.environ.get("AUTH_PORT", "8443"))
AUTH_TLS_NAME = os.environ.get("AUTH_TLS_NAME", "localhost")
AUTH_CA_FILE = os.environ.get("AUTH_CA_FILE", "/run/certificates/auth-ca.pem")
SHOP_HOST = os.environ.get("SHOP_HOST", "dispatcher")
SHOP_PORT = int(os.environ.get("SHOP_PORT", "18089"))
MAX_SHOP_BODY = 1024 * 1024
MAX_SHOP_RESPONSE = 32 * 1024 * 1024
AUTH_PATHS = {"/login", "/register", "/remember", "/game-token"}
SHOP_PATH = re.compile(
    r"(?:/json/(?:Ankama|Wakfu)/[A-Za-z0-9_./:-]+|/[a-z]{2}/shops/WAKFU_INGAME(?:/[A-Za-z0-9_./:-]+)?|/item-icons/[1-9][0-9]{0,9}\.(?:jpg|png)|/shop-icon\.png)\Z"
)
LEGACY_SHOP_ORIGINS = (
    "https://wakemu-shop.p.hectorpulido.net",
    "https://wakemu-resources.p.hectorpulido.net",
    "http://192.168.0.7:18080",
    "http://192.168.0.7:18083",
    "http://127.0.0.1:18083",
)
JSON_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
UPSTREAM_HOST = os.environ.get("OBJECTIVES_HOST", "objectives")
UPSTREAM_PORT = int(os.environ.get("OBJECTIVES_PORT", "8094"))
TOKEN_FILE = os.environ.get("OBJECTIVES_TOKEN_FILE", "/run/secrets/objectives-token")
STATIC = re.compile(r"/player/(?:adventures\.(?:js|css)|fonts/[A-Za-z0-9_.-]+)?\Z")
API = re.compile(
    r"/player-api/(?:config|session|adventures|actions(?:/[a-fA-F0-9-]{36})?)\Z"
)
CAPACITY = threading.BoundedSemaphore(24)


class LoginLimits:
    def __init__(self):
        self.lock = threading.Lock()
        self.global_hits = deque()
        self.accounts = OrderedDict()

    def admit(self, username):
        now = time.monotonic()
        key = hashlib.sha256(username.lower().encode()).digest()
        with self.lock:
            while self.global_hits and self.global_hits[0] <= now - 60:
                self.global_hits.popleft()
            hits = self.accounts.pop(key, deque())
            while hits and hits[0] <= now - 60:
                hits.popleft()
            self.accounts[key] = hits
            while len(self.accounts) > 2048:
                self.accounts.popitem(last=False)
            if len(self.global_hits) >= 60 or len(hits) >= 10:
                return False
            self.global_hits.append(now)
            hits.append(now)
            return True


LIMITS = LoginLimits()


def read_upstream(connection, method, path, body, headers, maximum=MAX_RESPONSE):
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = b"" if method == "HEAD" else response.read(maximum + 1)
        if len(raw) > maximum:
            raise OSError("Upstream response exceeded its bound")
        safe = {
            name: response.getheader(name)
            for name in (
                "Content-Type",
                "Content-Security-Policy",
                "Referrer-Policy",
                "X-Content-Type-Options",
                "Retry-After",
                "Content-Encoding",
            )
            if response.getheader(name)
        }
        return response.status, raw, safe
    finally:
        connection.close()


def upstream(method, path, body, headers):
    return read_upstream(
        http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=12),
        method,
        path,
        body,
        headers,
        MAX_RESPONSE,
    )


def auth_upstream(method, path, body, headers):
    context = ssl.create_default_context(cafile=AUTH_CA_FILE)
    connection = http.client.HTTPConnection(AUTH_HOST, AUTH_PORT, timeout=12)
    transport = socket.create_connection((AUTH_HOST, AUTH_PORT), timeout=12)
    try:
        connection.sock = context.wrap_socket(transport, server_hostname=AUTH_TLS_NAME)
    except BaseException:
        transport.close()
        raise
    return read_upstream(connection, method, path, body, headers, MAX_RESPONSE)


def shop_upstream(method, path, body, headers):
    return read_upstream(
        http.client.HTTPConnection(SHOP_HOST, SHOP_PORT, timeout=12),
        method,
        path,
        body,
        headers,
        MAX_SHOP_RESPONSE,
    )


def rewrite_json_values(payload, public_origin, private_origins=LEGACY_SHOP_ORIGINS):
    """Replace URL string values only, preserving keys and exact numeric tokens."""
    try:
        text = payload.decode("utf-8")
        json.loads(text)
    except (UnicodeError, ValueError, RecursionError):
        return payload
    chunks = []
    previous = 0
    for match in JSON_STRING.finditer(text):
        following = match.end()
        while following < len(text) and text[following] in " \t\r\n":
            following += 1
        if following < len(text) and text[following] == ":":
            continue
        value = json.loads(match.group())
        for origin in private_origins:
            if value == origin or any(
                value.startswith(origin + boundary) for boundary in ("/", "?", "#")
            ):
                changed = public_origin + value[len(origin) :]
                chunks.extend(
                    (
                        text[previous : match.start()],
                        json.dumps(changed, ensure_ascii=False),
                    )
                )
                previous = match.end()
                break
    if not chunks:
        return payload
    chunks.append(text[previous:])
    return "".join(chunks).encode("utf-8")


def launcher_config():
    host = urlsplit(UNIFIED_ORIGIN).hostname
    return dict(
        version=1,
        server_host=host,
        chat_host=host,
        dispatch_port=15558,
        game_ports=[15556],
        chat_port=16337,
        api_url=UNIFIED_ORIGIN,
        http_url=UNIFIED_ORIGIN,
        shop_url=UNIFIED_ORIGIN,
        achievements_url=UNIFIED_ORIGIN,
        certificate="",
    )


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "WakemuAdventures"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        # Request paths can contain credentials; do not log requests or bodies.
        pass

    def reply(self, status, value=None, *, raw=None, headers=None):
        if raw is None:
            raw = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        headers = headers or {}
        self.send_header(
            "Content-Type",
            headers.get("Content-Type", "application/json; charset=utf-8"),
        )
        for name in ("Content-Security-Policy",):
            if name in headers:
                self.send_header(name, headers[name])
        if status == 429:
            self.send_header("Retry-After", "60")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(raw)

    def raw_body(self, maximum=MAX_BODY, required=True):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked requests are not accepted")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) > 1 or required and not lengths:
            raise ValueError("One Content-Length is required")
        size = int(lengths[0]) if lengths else 0
        if not (1 if required else 0) <= size <= maximum:
            raise ValueError("Invalid request size")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Incomplete request")
        return raw

    def body(self):
        if (
            self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise ValueError("JSON is required")
        return self.raw_body()

    def request_origin(self):
        host = self.headers.get("Host", "").lower()
        for origin in (PUBLIC_ORIGIN, UNIFIED_ORIGIN):
            expected = urlsplit(origin).netloc.lower()
            if host in (expected, expected + ":443"):
                return origin
        return None

    def dispatch(self):
        if not CAPACITY.acquire(blocking=False):
            return self.reply(503, {"error": "Adventures is busy; try again shortly"})
        try:
            self.route()
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
            self.reply(400, {"error": "Invalid Adventures request"})
        except (OSError, http.client.HTTPException):
            self.reply(503, {"error": "Adventures is unavailable; try again shortly"})
        finally:
            CAPACITY.release()

    def route(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or len(self.path) > 16384
            or any(c in self.path for c in "\r\n")
        ):
            return self.reply(404, {"error": "Route not found"})
        if path == "/health" and self.command == "GET":
            return self.reply(200, {"status": "ok"})
        public_origin = self.request_origin()
        if public_origin is None:
            return self.reply(421, {"error": "Host is not allowed"})
        if sum(len(key) + len(value) for key, value in self.headers.items()) > 65536:
            raise ValueError("Headers exceed their bound")
        if (
            public_origin == UNIFIED_ORIGIN
            and SHOP_PATH.fullmatch(path)
            and self.command
            in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
        ):
            raw = self.raw_body(MAX_SHOP_BODY, required=False)
            headers = {
                name: self.headers[name]
                for name in (
                    "Authorization",
                    "APIKEY",
                    "Content-Type",
                    "Accept",
                    "Accept-Language",
                )
                if name in self.headers
            }
            headers["Accept-Encoding"] = "identity"
            status, raw, safe = shop_upstream(self.command, self.path, raw, headers)
            content_type = safe.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type == "application/json" or content_type.endswith("+json"):
                if safe.get("Content-Encoding", "identity").lower() not in (
                    "identity",
                    "",
                ):
                    raise OSError("Encoded shop JSON is unsupported")
                raw = rewrite_json_values(raw, public_origin)
            return self.reply(status, raw=raw, headers=safe)
        if parsed.query:
            return self.reply(404, {"error": "Route not found"})
        if path == "/launcher/config" and self.command == "GET":
            return self.reply(200, launcher_config())
        if (
            public_origin == UNIFIED_ORIGIN
            and path in AUTH_PATHS
            and self.command == "POST"
        ):
            origin = self.headers.get("Origin")
            if origin is not None and origin != public_origin:
                return self.reply(403, {"error": "Origin is not allowed"})
            raw = self.body()
            request = json.loads(raw)
            if type(request) is not dict:
                raise ValueError("Expected a JSON object")
            if not LIMITS.admit("auth:" + str(request.get("username", "token"))):
                return self.reply(
                    429, {"error": "Too many login attempts; wait one minute"}
                )
            headers = {
                name: self.headers[name]
                for name in ("Authorization", "Content-Type", "Accept")
                if name in self.headers
            }
            status, raw, safe = auth_upstream(self.command, path, raw, headers)
            return self.reply(status, raw=raw, headers=safe)
        if path == "/launcher/login" and self.command == "POST":
            origin = self.headers.get("Origin")
            if origin is not None and origin != public_origin:
                return self.reply(403, {"error": "Origin is not allowed"})
            request = json.loads(self.body())
            if type(request) is not dict or set(request) != {"username", "password"}:
                raise ValueError("Expected native credentials")
            username, password = request["username"], request["password"]
            if (
                type(username) is not str
                or not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username)
                or type(password) is not str
                or not 8 <= len(password) <= 256
            ):
                raise ValueError("Invalid native credentials")
            if not LIMITS.admit(username):
                return self.reply(
                    429, {"error": "Too many login attempts; wait one minute"}
                )
            token = Path(TOKEN_FILE).read_text().strip()
            if not token:
                raise OSError("Missing bridge credential")
            status, raw, _ = upstream(
                "POST",
                "/v1/player/gamedock-launch",
                json.dumps(request).encode(),
                {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
            if status == 401:
                return self.reply(
                    401, {"error": "Native account credentials were rejected"}
                )
            if status == 400:
                return self.reply(
                    400,
                    {
                        "error": "Create a character on this account before opening Adventures"
                    },
                )
            if status != 200:
                return self.reply(
                    503, {"error": "Adventures authentication is unavailable"}
                )
            result = json.loads(raw)
            launch_token = result.get("token")
            if type(launch_token) is not str or not re.fullmatch(
                r"[A-Za-z0-9_-]{43}", launch_token
            ):
                raise OSError("Invalid bridge response")
            return self.reply(
                200,
                {
                    "url": public_origin + "/player/#token=" + launch_token,
                    "valid_days": 30,
                },
            )
        if path == "/player" and self.command == "GET":
            self.send_response(308)
            self.send_header("Location", "/player/")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        static = STATIC.fullmatch(path) is not None and self.command == "GET"
        api = API.fullmatch(path) is not None
        allowed_api = api and (
            self.command == "GET"
            and (
                path in ("/player-api/config", "/player-api/adventures")
                or path.startswith("/player-api/actions/")
            )
            or self.command == "POST"
            and path in ("/player-api/session", "/player-api/actions")
        )
        if not static and not allowed_api:
            return self.reply(404, {"error": "Route not found"})
        raw = self.body() if self.command == "POST" else None
        headers = {
            name: self.headers[name]
            for name in ("Authorization", "Content-Type", "Accept")
            if name in self.headers
        }
        # Same-origin browser requests go through this trusted bridge. Never forward
        # Origin, cookies, proxy headers or the operator bearer to player routes.
        status, raw, safe = upstream(self.command, path, raw, headers)
        return self.reply(status, raw=raw, headers=safe)

    do_GET = dispatch
    do_POST = dispatch
    do_PUT = dispatch
    do_PATCH = dispatch
    do_DELETE = dispatch
    do_OPTIONS = dispatch
    do_HEAD = dispatch


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 24


if __name__ == "__main__":
    Server(
        (
            os.environ.get("BIND_HOST", "0.0.0.0"),
            int(os.environ.get("BIND_PORT", "18090")),
        ),
        Handler,
    ).serve_forever()
