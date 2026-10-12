"""Private serialized Docker lifecycle broker; no client-supplied commands."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import uuid

SERVICES = ("world", "ecology", "shop", "ai", "profiler")


class DockerControl:
    def __init__(self, root, project, data_dir, runner=subprocess.run):
        self.root = Path(root).resolve()
        self.project = project
        self.data = Path(data_dir)
        self.runner = runner
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", project):
            raise ValueError("Invalid Compose project")
        if (
            not (self.root / "compose.yaml").is_file()
            or not (self.root / "server").is_dir()
        ):
            raise ValueError(
                "Host project source must be mounted at its original absolute path"
            )
        self.env = dict(os.environ)
        self.env["COMPOSE_PROJECT_NAME"] = project
        self.env["PWD"] = str(self.root)
        self.compose = [
            "docker",
            "compose",
            "--project-name",
            project,
            "--project-directory",
            str(self.root),
            "-f",
            str(self.root / "compose.yaml"),
        ]
        if (self.root / "compose.profiler.yaml").is_file():
            self.compose += ["-f", str(self.root / "compose.profiler.yaml")]
        self.compose += ["--profile", "observability"]

    def run(self, args, timeout=600):
        result = self.runner(
            args,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            # Docker output can include environment interpolations; never return it.
            self.data.mkdir(parents=True, exist_ok=True)
            fd = os.open(
                self.data / "last-failure.log",
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            with os.fdopen(fd, "w") as output:
                output.write(result.stdout[-131072:])
            raise RuntimeError("Docker command failed; private diagnostic log retained")
        return result.stdout

    def container(self, name):
        if name not in SERVICES:
            raise ValueError("Unsupported service")
        ids = self.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + self.project,
                "--filter",
                "label=com.docker.compose.service=" + name,
            ],
            timeout=20,
        ).split()
        if not ids:
            return None
        if len(ids) != 1:
            raise RuntimeError("Multiple managed containers for service")
        raw = self.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .State}}|{{json .Config.Labels}}|{{json .Config.Image}}",
                ids[0],
            ],
            timeout=20,
        ).strip()
        state, labels, image = [json.loads(part) for part in raw.split("|", 2)]
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("com.docker.compose.service") != name
        ):
            raise RuntimeError("Container ownership changed")
        return dict(id=ids[0], state=state, image=image)

    def services(self):
        result = []
        for name in SERVICES:
            try:
                item = self.container(name)
                state = item["state"] if item else {}
                status = state.get("Health", {}).get(
                    "Status", state.get("Status", "missing")
                )
                result.append(
                    dict(
                        name=name,
                        status=status,
                        ok=status == "healthy",
                        restartable=item is not None,
                    )
                )
            except Exception:
                result.append(
                    dict(name=name, status="unavailable", ok=False, restartable=False)
                )
        return result

    def fingerprint(self):
        """Include build inputs and tests; any concurrent source change aborts activation."""
        files = [self.root / "compose.yaml"]
        if (self.root / "compose.profiler.yaml").is_file():
            files.append(self.root / "compose.profiler.yaml")
        for path in (self.root / "server").rglob("*"):
            if (
                path.is_file()
                and not any(
                    part in {"__pycache__", ".git", "node_modules", ".venv"}
                    for part in path.parts
                )
                and path.suffix not in {".pyc", ".pyo"}
            ):
                files.append(path)
        digest = hashlib.sha256()
        for path in sorted(files):
            digest.update(str(path.relative_to(self.root)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def active_catalog(self):
        import psycopg
        from psycopg.conninfo import make_conninfo

        password = Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
        dsn = make_conninfo(os.environ["WAKFU_DATABASE_URL"], password=password)
        with psycopg.connect(dsn, connect_timeout=5) as db:
            row = db.execute(
                "SELECT revision FROM native_catalog_active WHERE id=1"
            ).fetchone()
        if not row or not re.fullmatch(r"[0-9a-f]{64}", row[0]):
            raise RuntimeError("No valid active catalog release")
        return row[0]

    def configure_build(self):
        self.env["WAKFU_CATALOG_REVISION"] = self.active_catalog()
        for name, key in (
            ("world", "WAKFU_WORLD_IMAGE"),
            ("ecology", "WAKFU_ECOLOGY_IMAGE"),
        ):
            item = self.container(name)
            if item:
                self.env[key] = item["image"]

    def build(self, names):
        self.run(self.compose + ["build", *names], timeout=1800)

    def image(self, name):
        images = self.run(self.compose + ["config", "--format", "json"], timeout=30)
        config = json.loads(images)
        image = config["services"][name].get("image")
        if not image:
            image = self.project + "-" + name
        return image

    def validate_world(self):
        image = self.image("world")
        self.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "python3",
                image,
                "-m",
                "compileall",
                "-q",
                "/app",
            ],
            timeout=180,
        )
        # Verify every shared domain module, root entry point and migration byte.
        expected = {}
        for relative in ("wakfu_server", "migrations"):
            for path in (self.root / "server" / relative).rglob("*"):
                if (
                    path.is_file()
                    and "__pycache__" not in path.parts
                    and path.suffix not in {".pyc", ".pyo"}
                ):
                    expected[
                        str(path.relative_to(self.root / "server"))
                    ] = hashlib.sha256(path.read_bytes()).hexdigest()
        for relative in (
            "local_game_server.py",
            "protocol_codec.py",
            "docker-entrypoint.sh",
        ):
            expected[relative] = hashlib.sha256(
                (self.root / "server" / relative).read_bytes()
            ).hexdigest()
        script = "import hashlib,json,pathlib,sys; expected=json.loads(sys.argv[1]); bad=[name for name,sha in expected.items() if not (pathlib.Path('/app')/name).is_file() or hashlib.sha256((pathlib.Path('/app')/name).read_bytes()).hexdigest()!=sha]; assert not bad, 'Image differs from shared source'"
        self.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "python3",
                image,
                "-c",
                script,
                json.dumps(expected),
            ],
            timeout=180,
        )
        test_dsn = os.environ.get("WAKFU_POSTGRES_TEST_URL", "")
        from psycopg.conninfo import conninfo_to_dict

        if conninfo_to_dict(test_dsn).get("dbname") in {
            None,
            "wakemu",
            "wakemu_runtime",
        }:
            raise RuntimeError("An isolated test database must be configured")
        secret_host = str(self.root / ".database/secrets/postgres-password")
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            self.project + "_isolated",
            "--entrypoint",
            "python3",
            "-v",
            str(self.root / "server/tests") + ":/validation/tests:ro",
            "-v",
            secret_host + ":/run/secrets/postgres-password:ro",
            "-e",
            "WAKFU_DATABASE_PASSWORD_FILE=/run/secrets/postgres-password",
            "-e",
            "WAKFU_DATABASE_URL=" + os.environ["WAKFU_DATABASE_URL"],
            "-e",
            "WAKFU_REDIS_URL="
            + os.environ.get("WAKFU_REDIS_URL", "redis://redis:6379/0"),
            "-e",
            "WAKFU_CATALOG_REVISION=" + self.env["WAKFU_CATALOG_REVISION"],
            "-e",
            "WAKFU_POSTGRES_TEST_URL=" + test_dsn,
            "-e",
            "WAKFU_MIGRATIONS_TEST_DIR=/app/migrations",
            "-e",
            "PYTHONPATH=/app:/validation/tests",
            image,
            "-m",
            "unittest",
        ]
        self.run(
            command + ["test_live_console", "test_api_authorization"], timeout=1200
        )

    def activate(self, name, force=False):
        if self.container(name) is None:
            raise RuntimeError("Managed container disappeared before activation")
        flags = ["up", "-d", "--no-deps", "--no-build", "--timeout", "60"]
        if force:
            flags.append("--force-recreate")
        self.run(self.compose + flags + [name], timeout=180)
        self.wait_healthy(name)

    def wait_healthy(self, name, timeout=240):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            item = self.container(name)
            if item:
                state = item["state"]
                if state.get("Health", {}).get("Status") == "healthy":
                    return
                if state.get("Status") in ("dead", "exited"):
                    raise RuntimeError("Service exited during health verification")
            time.sleep(2)
        raise RuntimeError("Service health deadline exceeded")

    def restart(self, name, phase):
        if name not in SERVICES or self.container(name) is None:
            raise ValueError("Managed service is unavailable")
        source = self.fingerprint()
        phase("prepare")
        self.configure_build()
        if name == "world":
            attached = [n for n in ("ai", "ecology", "profiler") if self.container(n)]
            phase("build")
            self.build(["world"])
            if any(n != "profiler" for n in attached):
                self.build([n for n in attached if n != "profiler"])
            phase("validate")
            self.validate_world()
            if self.fingerprint() != source:
                raise RuntimeError(
                    "Shared source changed during build; retry after changes settle"
                )
            if self.active_catalog() != self.env["WAKFU_CATALOG_REVISION"]:
                raise RuntimeError(
                    "Active catalog changed during build; retry after changes settle"
                )
            phase("restart_world")
            self.activate("world", force=True)
            for dependent in attached:
                phase("restart_" + dependent)
                self.activate(dependent, force=True)
        else:
            phase("build")
            if name == "ai":
                self.build(["world"])
            self.build([name])
            if name == "ai":
                phase("validate")
                self.validate_world()
            if self.fingerprint() != source:
                raise RuntimeError(
                    "Shared source changed during build; retry after changes settle"
                )
            if self.active_catalog() != self.env["WAKFU_CATALOG_REVISION"]:
                raise RuntimeError(
                    "Active catalog changed during build; retry after changes settle"
                )
            phase("restart_" + name)
            self.activate(name, force=True)
        phase("healthy")


class OperationManager:
    def __init__(self, control, data_dir, start_worker=True):
        self.control = control
        self.root = Path(data_dir) / "operations"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.lock = threading.RLock()
        self.operations = {}
        self.requests = {}
        self.queue = queue.Queue(maxsize=100)
        for path in self.root.glob("*.json"):
            operation = json.loads(path.read_text())
            if operation["status"] == "running":
                operation.update(
                    status="failed",
                    phase="interrupted",
                    error="Broker restarted during operation; inspect service state before retrying",
                )
                self.persist(operation)
            self.operations[operation["handle"]] = operation
            self.requests[operation["request_id"]] = operation["handle"]
            if operation["status"] == "queued":
                self.queue.put_nowait(operation["handle"])
        if start_worker:
            threading.Thread(target=self.worker, daemon=True).start()

    def persist(self, operation):
        temporary = self.root / (operation["handle"] + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(operation, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.root / (operation["handle"] + ".json"))

    def submit(self, data):
        if not isinstance(data, dict) or set(data) != {"service", "request_id"}:
            raise ValueError("Service and request_id are required")
        name, request = data["service"], data["request_id"]
        if (
            name not in SERVICES
            or not isinstance(request, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", request)
        ):
            raise ValueError("Invalid service or request identifier")
        with self.lock:
            if request in self.requests:
                operation = self.operations[self.requests[request]]
                if operation["service"] != name:
                    raise ValueError(
                        "Request identifier already belongs to another service"
                    )
                return dict(operation)
            if self.queue.full():
                raise ValueError("Restart queue is full")
            request_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            operation = dict(
                handle=uuid.uuid4().hex,
                request_id=request,
                request_hash=request_hash,
                service=name,
                status="queued",
                phase="queued",
                error=None,
                created_at=time.time(),
            )
            self.persist(operation)
            self.operations[operation["handle"]] = operation
            self.requests[request] = operation["handle"]
            self.queue.put_nowait(operation["handle"])
            return dict(operation)

    def get(self, handle):
        with self.lock:
            if handle not in self.operations:
                raise LookupError("Operation not found")
            return dict(self.operations[handle])

    def update(self, handle, **values):
        with self.lock:
            self.operations[handle].update(values)
            self.persist(self.operations[handle])

    def worker(self):
        while True:
            handle = self.queue.get()
            self.update(handle, status="running", phase="prepare")
            try:
                self.control.restart(
                    self.get(handle)["service"],
                    lambda value: self.update(handle, phase=value),
                )
                self.update(
                    handle,
                    status="completed",
                    phase="healthy",
                    error=None,
                    completed_at=time.time(),
                )
            except Exception as error:
                # Only our bounded messages cross the trust boundary.
                safe = (
                    str(error)
                    if type(error) in (ValueError, RuntimeError)
                    else "Lifecycle operation failed"
                )
                self.update(
                    handle, status="failed", error=safe[:300], completed_at=time.time()
                )
            finally:
                self.queue.task_done()


def make_server(manager, token, host="0.0.0.0", port=18085):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Control token must contain at least 32 characters")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def route(self):
            try:
                if not hmac.compare_digest(
                    self.headers.get("Authorization", ""), "Bearer " + token
                ):
                    self.reply(401, dict(error="Authentication required"))
                    return
                if self.command == "GET" and self.path == "/services":
                    result = dict(items=manager.control.services())
                elif self.command == "GET" and re.fullmatch(
                    r"/operations/[a-f0-9]{32}", self.path
                ):
                    result = manager.get(self.path.rsplit("/", 1)[1])
                elif self.command == "POST" and self.path == "/restart":
                    length = int(self.headers.get("Content-Length", "0"))
                    if (
                        not 1 <= length <= 4096
                        or self.headers.get_content_type() != "application/json"
                    ):
                        raise ValueError("Bounded JSON body required")
                    result = manager.submit(json.loads(self.rfile.read(length)))
                else:
                    raise LookupError("Route not found")
                self.reply(200, result)
            except LookupError as error:
                self.reply(404, dict(error=str(error)))
            except (ValueError, TypeError) as error:
                self.reply(400, dict(error=str(error)))
            except Exception:
                self.reply(503, dict(error="Lifecycle control unavailable"))

        do_GET = route
        do_POST = route

    return ThreadingHTTPServer((host, port), Handler)
