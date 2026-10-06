"""Local account API; no upstream game calls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
import json
from wakfu_server.command_permissions import authorize_command, is_admin


class AuthenticationError(ValueError):
    pass


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
            def encode(value):
                if isinstance(value, datetime):
                    return value.isoformat()
                raise TypeError("Unsupported API response value")

            body = json.dumps(value, default=encode).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def test_access(self):
            header = self.headers.get("Authorization", "")
            if not header.startswith("Bearer ") or not header[7:]:
                raise AuthenticationError("Acceso inválido o caducado")
            token = header[7:]
            try:
                access = store.token(token, "api")
            except ValueError:
                try:
                    access = store.token(token, "scheduler")
                except ValueError:
                    raise AuthenticationError("Acceso inválido o caducado") from None
            if access["kind"] != "scheduler" and not is_admin(
                store, access["account_id"]
            ):
                raise PermissionError("Esta API requiere un administrador")
            return token, access

        def submit_command(self, token, access, character_id, command, request_id):
            if access["kind"] == "scheduler":
                raise PermissionError(
                    "El scheduler solo puede ejecutar tareas globales"
                )

            def authorize():
                current = store.token(token, "api")
                if not is_admin(store, current["account_id"]):
                    raise PermissionError("Permiso administrativo revocado")
                if type(character_id) is not int:
                    raise ValueError("Personaje inválido")
                # Ownership is enforced separately from the administrative role.
                with store.connection() as db:
                    owner = db.execute(
                        "SELECT account_id FROM characters WHERE id=%s", (character_id,)
                    ).fetchone()
                if owner is None or owner["account_id"] != current["account_id"]:
                    raise PermissionError("El personaje pertenece a otra cuenta")
                authorize_command(store, current["account_id"], command)

            authorize()
            return live_console.submit(
                character_id,
                command,
                request_id=request_id,
                requester_account_id=access["account_id"],
                authorize=authorize,
            )

        def do_POST(self):
            try:
                test = self.path.startswith("/test/")
                token, access = self.test_access() if test else (None, None)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Petición inválida.")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Objeto JSON requerido")
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
                    if access["kind"] == "scheduler":
                        raise PermissionError("Tarea fuera del scope del scheduler")
                    task = test_tasks[self.path.rsplit("/", 1)[1]]
                    # Registry entries enqueue session-owned commands, never execute game actions here.
                    result = self.submit_command(
                        token,
                        access,
                        task["character_id"],
                        task["command"],
                        body.get("request_id"),
                    )
                    return self.reply(
                        202 if result["status"] in ("pending", "running") else 200,
                        result,
                    )
                if self.path == "/test/command" and live_console is not None:
                    result = self.submit_command(
                        token,
                        access,
                        body["character_id"],
                        body["command"],
                        body.get("request_id"),
                    )
                    return self.reply(
                        202 if result["status"] in ("pending", "running") else 200,
                        result,
                    )
                if test:
                    return self.reply(404, {"error": "Ruta desconocida."})
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
            except AuthenticationError:
                self.reply(401, {"error": "Acceso inválido o caducado."})
            except PermissionError:
                self.reply(403, {"error": "Operación no autorizada."})
            except (ValueError, KeyError, TypeError):
                self.reply(400, {"error": "Datos o acceso inválidos."})
            except Exception:
                self.reply(
                    503, {"error": "La tarea o almacenamiento no está disponible."}
                )

        def get_test(self, access):
            if self.path == "/test/tasks" and (
                test_tasks is not None or global_tasks is not None
            ):
                return self.reply(
                    200,
                    [
                        {"name": name, "character_id": task["character_id"]}
                        for name, task in (test_tasks or {}).items()
                        if access["kind"] != "scheduler"
                    ]
                    + [
                        dict(name=name, scope="global")
                        for name in (
                            global_tasks.names() if global_tasks is not None else []
                        )
                    ],
                )
            if self.path == "/test/sessions" and live_console is not None:
                if access["kind"] == "scheduler":
                    raise PermissionError("Scope no autorizado")
                return self.reply(
                    200,
                    [
                        session
                        for session in live_console.list_sessions()
                        if session["account_id"] == access["account_id"]
                    ],
                )
            if self.path.startswith("/test/command/") and live_console is not None:
                if access["kind"] == "scheduler":
                    raise PermissionError("Scope no autorizado")
                try:
                    receipt = live_console.poll(self.path.rsplit("/", 1)[1])
                    if receipt.get("requester_account_id") != access["account_id"]:
                        raise PermissionError("Resultado de otra cuenta")
                    return self.reply(200, receipt)
                except ValueError as error:
                    return self.reply(404, {"error": str(error)})
            return self.reply(404, {"error": "Ruta desconocida."})

        def do_GET(self):
            if self.path.startswith("/test/"):
                try:
                    _, access = self.test_access()
                    return self.get_test(access)
                except AuthenticationError:
                    return self.reply(401, {"error": "Acceso inválido o caducado."})
                except PermissionError:
                    return self.reply(403, {"error": "Operación no autorizada."})
                except Exception:
                    return self.reply(503, {"error": "Almacenamiento no disponible."})
            if self.path == "/health":
                try:
                    with store.connection() as db:
                        db.execute("SET LOCAL statement_timeout = '1s'")
                        db.execute("SELECT 1 AS healthy").fetchone()
                except Exception:
                    return self.reply(503, {"ok": False, "storage": "postgresql"})
                return self.reply(
                    200,
                    {
                        "ok": True,
                        "storage": "postgresql",
                        "protocol": "local prototype",
                    },
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
