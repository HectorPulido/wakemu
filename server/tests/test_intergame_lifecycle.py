"""Run the actual World intergame startup and stop AST with socket-free fakes."""
import ast
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "server" / "local_game_server.py"
COMPOSE = ROOT / "compose.yaml"


def _main_node():
    tree = ast.parse(SERVER.read_text(encoding="utf-8"), filename=str(SERVER))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )


def _assigns(node, name):
    return isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in node.targets
    )


def _listener_startup_nodes():
    selected = []
    for node in _main_node().body:
        if _assigns(node, "context"):
            selected.append(node)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "context.load_cert_chain"
        ):
            selected.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module in (
            "wakfu_server.intergame_domain",
            "wakfu_server.intergame_transport",
        ):
            selected.append(node)
        elif _assigns(node, "intergame_server"):
            selected.append(node)
        elif _assigns(node, "intergame_thread"):
            selected.append(node)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "intergame_thread.start"
        ):
            selected.append(node)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "record"
            and {kw.arg: ast.unparse(kw.value) for kw in node.value.keywords}.get(
                "service"
            )
            == "'intergame'"
        ):
            selected.append(node)
    required = {"context", "intergame_server", "intergame_thread"}
    present = {
        target.id
        for node in selected
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    if not required <= present:
        raise AssertionError(
            f"Missing listener startup assignments: {required - present}"
        )
    return selected


def _stop_node():
    return next(
        node
        for node in ast.walk(_main_node())
        if isinstance(node, ast.FunctionDef) and node.name == "stop"
    )


class FakeThread:
    def __init__(self, events, *, target, name, daemon):
        self.events = events
        self.target = target
        self.name = name
        self.daemon = daemon
        self.alive = False

    def start(self):
        self.events.append(("thread-start", self.name, self.daemon))
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.events.append(("thread-join", self.name, timeout))
        self.alive = False


class IntergameLifecycleTests(unittest.TestCase):
    def _run_startup(self, bind_host=None):
        events = []

        class Context:
            def load_cert_chain(self, cert, key):
                events.append(("tls-cert", str(cert), str(key)))

        context = Context()
        threads = []

        def make_server(domain, tls_context, *, host, port):
            server = SimpleNamespace(
                connections=SimpleNamespace(
                    close_all=lambda: events.append("close-all")
                ),
                serve_forever=lambda: None,
                shutdown=lambda: events.append("shutdown"),
                server_close=lambda: events.append("server-close"),
            )
            events.append(("make-server", domain.store, tls_context, host, port))
            return server

        def thread_factory(*, target, name, daemon):
            thread = FakeThread(events, target=target, name=name, daemon=daemon)
            threads.append(thread)
            return thread

        domain_module = ModuleType("wakfu_server.intergame_domain")
        domain_module.Intergame = lambda store: SimpleNamespace(store=store)
        transport_module = ModuleType("wakfu_server.intergame_transport")
        transport_module.make_server = make_server

        world_store = object()
        namespace = {
            "ast": ast,
            "os": os,
            "ssl": SimpleNamespace(
                PROTOCOL_TLS_SERVER="tls-server", SSLContext=lambda protocol: context
            ),
            "threading": SimpleNamespace(Thread=thread_factory),
            "RUNTIME": Path("/runtime"),
            "STORE": world_store,
            "record": lambda **row: events.append(("record", row)),
        }
        statements = _listener_startup_nodes()
        function = ast.FunctionDef(
            name="start_listener",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[
                *map(
                    lambda node: ast.fix_missing_locations(
                        ast.parse(ast.unparse(node)).body[0]
                    ),
                    statements,
                ),
                ast.Return(
                    ast.Tuple(
                        elts=[
                            ast.Name("intergame_server", ast.Load()),
                            ast.Name("intergame_thread", ast.Load()),
                        ],
                        ctx=ast.Load(),
                    )
                ),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        env = {} if bind_host is None else {"WAKFU_BIND_HOST": bind_host}
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.intergame_domain": domain_module,
                "wakfu_server.intergame_transport": transport_module,
            },
        ), patch.dict(os.environ, env, clear=False):
            exec(compile(module, str(SERVER), "exec"), namespace)
            server, thread = namespace["start_listener"]()
        return server, thread, events, threads, world_store

    def test_main_constructs_tls_listener_and_starts_daemon_on_compose_bind(self):
        server, thread, events, threads, world_store = self._run_startup("0.0.0.0")
        self.assertEqual(len(threads), 1)
        self.assertIs(thread, threads[0])
        self.assertEqual(thread.name, "wakfu-intergame-listener")
        self.assertTrue(thread.daemon)
        self.assertIs(thread.target, server.serve_forever)
        make_event = next(
            event
            for event in events
            if isinstance(event, tuple) and event[0] == "make-server"
        )
        self.assertIs(make_event[1], world_store)
        self.assertEqual(make_event[3:], ("0.0.0.0", 16337))
        self.assertIn(
            ("tls-cert", "/runtime/server.crt", "/runtime/server.key"), events
        )
        listening_index = next(
            index
            for index, event in enumerate(events)
            if isinstance(event, tuple)
            and event[0] == "record"
            and event[1].get("event") == "listening"
            and event[1].get("service") == "intergame"
        )
        self.assertLess(
            events.index(("thread-start", "wakfu-intergame-listener", True)),
            listening_index,
        )
        mappings = [
            line.strip()
            for line in COMPOSE.read_text().splitlines()
            if "16337:" in line
        ]
        self.assertEqual(mappings, ['- "127.0.0.1:16337:16337"'])

    def _run_stop(self, *, thread_alive=True, flush_failure=None):
        events = []
        server = SimpleNamespace(
            shutdown=lambda: events.append("intergame-shutdown"),
            connections=SimpleNamespace(
                close_all=lambda: events.append("intergame-close-all")
            ),
            server_close=lambda: events.append("intergame-server-close"),
        )
        listener_thread = SimpleNamespace(is_alive=lambda: thread_alive)

        class ShutdownFlag:
            def set(self):
                events.append("stopping-set")

        class ClientConnections:
            def drain(self):
                events.append("connections-drained")
                return [{"notice_error": None}]

        class Store:
            def close(self):
                events.append("store-close")

        class Diagnostic:
            def close(self, timeout):
                events.append(("diagnostic-close", timeout))

        flush_count = 0

        def flush_positions():
            nonlocal flush_count
            flush_count += 1
            events.append(("flush", flush_count))
            if flush_failure == flush_count:
                raise RuntimeError("flush unavailable")

        globals_ = {
            "STOPPING": ShutdownFlag(),
            "CONNECTIONS": ClientConnections(),
            "STORE": Store(),
            "DIAGNOSTIC_LOG": Diagnostic(),
            "flush_positions": flush_positions,
            "record": lambda **row: events.append(("record", row)),
            "time": SimpleNamespace(monotonic=lambda: 10.0),
            "threading": SimpleNamespace(enumerate=lambda: []),
        }
        stop = ast.fix_missing_locations(_stop_node())
        outer = ast.FunctionDef(
            name="run_stop",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=[
                ast.Assign(
                    targets=[ast.Name("intergame_server", ast.Store())],
                    value=ast.Name("_server", ast.Load()),
                ),
                ast.Assign(
                    targets=[ast.Name("intergame_thread", ast.Store())],
                    value=ast.Name("_thread", ast.Load()),
                ),
                stop,
                ast.Try(
                    body=[
                        ast.Expr(
                            ast.Call(
                                func=ast.Name("stop", ast.Load()),
                                args=[ast.Constant(15), ast.Constant(None)],
                                keywords=[],
                            )
                        )
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name("SystemExit", ast.Load()),
                            name="exit",
                            body=[ast.Return(ast.Name("exit", ast.Load()))],
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                ),
                ast.Return(ast.Constant(None)),
            ],
            decorator_list=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[outer], type_ignores=[]))
        globals_.update({"_server": server, "_thread": listener_thread})
        exec(compile(module, str(SERVER), "exec"), globals_)
        result = globals_["run_stop"]()
        return result, events

    def test_sigterm_drains_and_closes_intergame_before_store(self):
        result, events = self._run_stop()
        self.assertEqual(result.code, 0)
        self.assertLess(events.index(("flush", 1)), events.index("stopping-set"))
        self.assertLess(
            events.index("stopping-set"), events.index("connections-drained")
        )
        self.assertLess(events.index("connections-drained"), events.index(("flush", 2)))
        self.assertLess(events.index(("flush", 2)), events.index("intergame-shutdown"))
        self.assertLess(
            events.index("intergame-shutdown"), events.index("intergame-close-all")
        )
        self.assertLess(
            events.index("intergame-close-all"), events.index("intergame-server-close")
        )
        self.assertLess(
            events.index("intergame-server-close"), events.index("store-close")
        )

    def test_sigterm_during_listener_start_skips_shutdown_but_closes_server_before_store(
        self,
    ):
        result, events = self._run_stop(thread_alive=False)
        self.assertEqual(result.code, 0)
        self.assertNotIn("intergame-shutdown", events)
        self.assertLess(
            events.index("intergame-close-all"), events.index("intergame-server-close")
        )
        self.assertLess(
            events.index("intergame-server-close"), events.index("store-close")
        )

    def test_flush_failure_leaves_listener_and_store_open_for_retry(self):
        result, events = self._run_stop(flush_failure=1)
        self.assertIsNone(result)
        self.assertIn(("flush", 1), events)
        self.assertNotIn("intergame-shutdown", events)
        self.assertNotIn("intergame-close-all", events)
        self.assertNotIn("store-close", events)


if __name__ == "__main__":
    unittest.main()
