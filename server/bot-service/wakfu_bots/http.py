"""Authenticated profile management; no remote caller can mutate World directly."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import BOT_ID

MAX_BODY = 16384


def make_server(worker, token, host="127.0.0.1", port=8096):
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError("A separate bot management credential is required")

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def reply(self, status, value):
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def handle_request(self, method):
            if method == "GET" and self.path == "/health":
                return self.reply(200, {"ok": True, "service": "bots"})
            expected = ("Bearer " + token).encode()
            if not hmac.compare_digest(
                self.headers.get("Authorization", "").encode(), expected
            ):
                return self.reply(401, {"error": "Invalid bot management credential"})
            try:
                if self.path == "/v1/bots" and method == "GET":
                    return self.reply(200, worker.inspect())
                prefix = "/v1/bots/"
                if not self.path.startswith(prefix) or not BOT_ID.fullmatch(
                    self.path[len(prefix) :]
                ):
                    return self.reply(404, {"error": "Unknown bot route"})
                bot_id = self.path[len(prefix) :]
                if method == "PUT":
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= MAX_BODY:
                        return self.reply(413, {"error": "Invalid bot profile size"})
                    value = json.loads(self.rfile.read(length))
                    return self.reply(200, worker.profiles.put(bot_id, value))
                if method == "DELETE":
                    worker.profiles.remove(bot_id)
                    return self.reply(200, {"bot_id": bot_id, "removed": True})
                return self.reply(405, {"error": "Unsupported method"})
            except (ValueError, TypeError, UnicodeDecodeError):
                return self.reply(400, {"error": "Invalid bot profile"})
            except KeyError:
                return self.reply(404, {"error": "Unknown bot"})
            except Exception:
                return self.reply(503, {"error": "Bot management unavailable"})

        def do_GET(self):
            self.handle_request("GET")

        def do_PUT(self):
            self.handle_request("PUT")

        def do_DELETE(self):
            self.handle_request("DELETE")

        def do_POST(self):
            self.handle_request("POST")

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
