"""Local account API; no upstream game calls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


def serve_api(
    store,
    host="127.0.0.1",
    port=18081,
    *,
    live_console=None,
    on_ready=None,
    test_tasks=None,
    global_tasks=None
):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log passwords, authorization headers or tokens.

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Petición inválida.")
                body = json.loads(self.rfile.read(length))
                if self.path.startswith("/test/tasks/") and global_tasks is not None:
                    name = self.path.rsplit("/", 1)[1]
                    if name in global_tasks.names():
                        return self.reply(
                            200, global_tasks.run(name, body.get("request_id"))
                        )
                if (
                    self.path.startswith("/test/tasks/")
                    and test_tasks is not None
                    and live_console is not None
                ):
                    task = test_tasks[self.path.rsplit("/", 1)[1]]
                    # Registry entries enqueue session-owned commands, never execute game actions here.
                    result = live_console.submit(
                        task["character_id"],
                        task["command"],
                        request_id=body.get("request_id"),
                    )
                    return self.reply(
                        202 if result["status"] in ("pending", "running") else 200,
                        result,
                    )
                if self.path == "/test/command" and live_console is not None:
                    result = live_console.submit(
                        body["character_id"],
                        body["command"],
                        request_id=body.get("request_id"),
                    )
                    return self.reply(
                        202 if result["status"] in ("pending", "running") else 200,
                        result,
                    )
                if self.path == "/register":
                    return self.reply(
                        201, store.register(body["username"], body["password"])
                    )
                if self.path == "/login":
                    account = store.authenticate(body["username"], body["password"])
                elif self.path == "/remember":
                    previous = store.token(body["remember_token"], "remember")
                    account = {
                        "id": previous["account_id"],
                        "username": previous["username"],
                    }
                else:
                    token = self.headers.get("Authorization", "").removeprefix(
                        "Bearer "
                    )
                    access = store.token(token, "api")
                    if self.path == "/characters":
                        return self.reply(
                            201, store.create_character(access["account_id"], **body)
                        )
                    if self.path == "/game-token":
                        return self.reply(
                            200,
                            {
                                "game_token": store.issue_token(
                                    access["account_id"], "game"
                                )
                            },
                        )
                    if self.path == "/logout":
                        store.revoke_token(token)
                        if body.get("remember_token"):
                            store.revoke_token(body["remember_token"])
                        return self.reply(200, {"ok": True})
                    return self.reply(404, {"error": "Ruta desconocida."})
                result = {
                    "account": account,
                    "game_token": store.issue_token(account["id"], "game", ttl=300),
                    "api_token": store.issue_token(account["id"], "api", ttl=3600),
                }
                if body.get("remember"):
                    result["remember_token"] = store.issue_token(
                        account["id"], "remember", ttl=30 * 86400
                    )
                self.reply(200, result)
            except (ValueError, KeyError, TypeError):
                self.reply(400, {"error": "Datos o acceso inválidos."})
            except Exception:
                self.reply(
                    503, {"error": "La tarea o almacenamiento no está disponible."}
                )

        def do_GET(self):
            if self.path == "/test/tasks" and (
                test_tasks is not None or global_tasks is not None
            ):
                return self.reply(
                    200,
                    [
                        {"name": name, "character_id": task["character_id"]}
                        for name, task in (test_tasks or {}).items()
                    ]
                    + [
                        dict(name=name, scope="global")
                        for name in (
                            global_tasks.names() if global_tasks is not None else []
                        )
                    ],
                )
            if self.path == "/test/sessions" and live_console is not None:
                return self.reply(200, live_console.list_sessions())
            if self.path.startswith("/test/command/") and live_console is not None:
                try:
                    return self.reply(
                        200, live_console.poll(self.path.rsplit("/", 1)[1])
                    )
                except ValueError as error:
                    return self.reply(404, {"error": str(error)})
            if self.path == "/health":
                return self.reply(
                    200,
                    {"ok": True, "storage": "sqlite", "protocol": "local prototype"},
                )
            try:
                access = store.token(
                    self.headers.get("Authorization", "").removeprefix("Bearer "), "api"
                )
                if self.path == "/characters":
                    return self.reply(200, store.characters(access["account_id"]))
                self.reply(404, {"error": "Ruta desconocida."})
            except ValueError:
                self.reply(401, {"error": "Acceso inválido o caducado."})

    server = ThreadingHTTPServer((host, port), Handler)
    if on_ready is not None:
        on_ready(server)
    server.serve_forever()
