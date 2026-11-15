"""Source access for older contracts that compile individual World operations.

This test-only view reverses dependency injection in the actual application
modules. It retains no copy of the retired coordinator. Execution tests for the
new Session and services use those production classes directly.
"""

import ast
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

_PathBase = type(Path())


def _state_attribute(node):
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "self"
        and node.value.attr == "state"
    )


def _binding_alias(node):
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and _state_attribute(node.targets[0])
        and isinstance(node.value, ast.Name)
        and node.targets[0].attr == node.value.id
    )


class _StateWrites(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Attribute(self, node):
        if _state_attribute(node) and isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.attr)
        self.generic_visit(node)

    def visit_Assign(self, node):
        if not _binding_alias(node):
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        pass

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef


class _Bindings(ast.NodeTransformer):
    """Recover the lexical names used by existing extracted-function fixtures."""

    def __init__(self, *, restore_nonlocals=False, class_owner=False):
        self.restore_nonlocals = restore_nonlocals
        self.class_owner = class_owner

    def visit_Attribute(self, node):
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
            and node.value.attr in {"state", "runtime"}
        ):
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        if (
            not self.class_owner
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if _binding_alias(node):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "bind_input"
        ):
            return ast.copy_location(
                ast.NamedExpr(
                    target=ast.Name(id=node.args[0].value, ctx=ast.Store()),
                    value=self.visit(node.args[1]),
                ),
                node,
            )
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "vars"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Attribute)
            and isinstance(node.args[0].value, ast.Name)
            and node.args[0].value.id == "self"
            and node.args[0].attr in {"runtime", "state"}
        ):
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(
                        id="globals" if node.args[0].attr == "runtime" else "locals",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                ),
                node,
            )
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        writes = _StateWrites()
        for statement in node.body:
            writes.visit(statement)
        node = self.generic_visit(node)
        if not self.class_owner and node.args.args and node.args.args[0].arg == "self":
            node.args.args.pop(0)
        if self.restore_nonlocals and writes.names:
            index = int(
                bool(node.body)
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            node.body.insert(index, ast.Nonlocal(names=sorted(writes.names)))
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _application_sources():
    root = Path(__file__).resolve().parents[1] / "wakfu_server" / "application"
    return sorted(root.glob("*.py"))


def _source_fingerprint():
    return tuple(
        (str(path), path.stat().st_mtime_ns) for path in _application_sources()
    )


def _methods(tree):
    return {
        node.name: {
            method.name: method
            for method in node.body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def _plain_body(method):
    """Inline a method into the old socket scope, retaining nested closures."""
    body = deepcopy(method.body)
    result = []
    for statement in body:
        # Nested local callbacks need nonlocals; the inlined outer scope does not.
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            statement = _Bindings(restore_nonlocals=True).visit(statement)
        else:
            statement = _Bindings().visit(statement)
        if statement is not None:
            result.append(statement)
    return result


class _RoutingOutcomes(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        return node

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def visit_Return(self, node):
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "DispatchResult"
        ):
            if node.value.attr == "CONTINUE":
                return ast.copy_location(ast.Continue(), node)
            if node.value.attr == "FALLTHROUGH":
                return ast.copy_location(ast.Return(value=None), node)
        return self.generic_visit(node)


def _without_default_outcome(body):
    body = deepcopy(body)
    if (
        body
        and isinstance(body[-1], ast.Return)
        and isinstance(body[-1].value, ast.Attribute)
        and isinstance(body[-1].value.value, ast.Name)
        and body[-1].value.value.id == "DispatchResult"
        and body[-1].value.attr == "FALLTHROUGH"
    ):
        body.pop()
    return body


def legacy_world_source():
    """Render current production units in their former lexical source shape."""
    return _legacy_world_source(_source_fingerprint())


@lru_cache(maxsize=2)
def _legacy_world_source(fingerprint):
    trees = {
        path.name: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in _application_sources()
    }
    session_class = _methods(trees["session.py"])["Session"]
    domain_methods = {}
    for filename, tree in trees.items():
        if filename.startswith("session_"):
            for methods in _methods(tree).values():
                domain_methods.update(methods)

    class InlineHandlers(ast.NodeTransformer):
        def visit_Return(self, node):
            call = node.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and call.func.attr.startswith("handle_")
            ):
                method = domain_methods[call.func.attr]
                body = _without_default_outcome(method.body)
                return (
                    _RoutingOutcomes()
                    .visit(ast.Module(body=body, type_ignores=[]))
                    .body
                )
            return self.generic_visit(node)

    dispatch_body = (
        InlineHandlers()
        .visit(
            ast.Module(
                body=_without_default_outcome(domain_methods["dispatch_request"].body),
                type_ignores=[],
            )
        )
        .body
    )
    dispatch_body = (
        _RoutingOutcomes().visit(ast.Module(body=dispatch_body, type_ignores=[])).body
    )
    prepare_body = (
        _RoutingOutcomes()
        .visit(
            ast.Module(
                body=_without_default_outcome(domain_methods["prepare_request"].body),
                type_ignores=[],
            )
        )
        .body
    )

    class InlineLifecycle(ast.NodeTransformer):
        def visit_If(self, node):
            if (
                isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Call)
                and isinstance(node.test.left.func, ast.Attribute)
                and isinstance(node.test.left.func.value, ast.Name)
                and node.test.left.func.value.id == "self"
            ):
                name = node.test.left.func.attr
                if name == "prepare_request":
                    return deepcopy(prepare_body)
                if name == "dispatch_request":
                    return deepcopy(dispatch_body)
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == "self"
                and node.value.func.attr == "close"
            ):
                return deepcopy(session_class["close"].body)
            return self.generic_visit(node)

    init = []
    decorators = {}
    for statement in deepcopy(session_class["__init__"].body):
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                if target.attr in {"runtime", "state"}:
                    continue
                if (
                    isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and isinstance(statement.value.func.value, ast.Name)
                    and statement.value.func.value.id == "self"
                ):
                    decorators[target.attr] = ast.Name(
                        id=statement.value.func.attr, ctx=ast.Load()
                    )
                    continue
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and statement.value.func.attr == "_bind_runtime_callbacks"
        ):
            continue
        init.append(statement)

    helper_definitions = []
    for name, method in domain_methods.items():
        if name.startswith("handle_") or name in {
            "prepare_request",
            "dispatch_request",
        }:
            continue
        helper = _Bindings(restore_nonlocals=True).visit(deepcopy(method))
        if name in decorators:
            helper.decorator_list.append(decorators[name])
        helper_definitions.append(helper)
    # The only session-bound decorators must be defined before decorated helpers.
    decorator_names = {value.id for value in decorators.values()}
    helper_definitions.sort(key=lambda helper: helper.name not in decorator_names)

    run = InlineLifecycle().visit(deepcopy(session_class["run"]))
    # Do not declare the outer session's own writes nonlocal.
    run_body = _plain_body(run)
    init_body = _Bindings().visit(ast.Module(body=init, type_ignores=[])).body
    session = ast.FunctionDef(
        name="session",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in ("raw", "peer", "service", "context")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=helper_definitions + init_body + run_body,
        decorator_list=[],
    )

    services = {}
    for filename, tree in trees.items():
        if filename.startswith("session") or filename == "transport.py":
            continue
        for methods in _methods(tree).values():
            services.update(
                {name: method for name, method in methods.items() if name != "__init__"}
            )

    class TopLevelBindings(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                return self.generic_visit(node)
            name = node.targets[0].id
            if name.startswith("_"):
                return None
            if name not in services:
                return self.generic_visit(node)
            value, wrappers = node.value, []
            while isinstance(value, ast.Call) and len(value.args) == 1:
                wrappers.append(deepcopy(value.func))
                value = value.args[0]
            if isinstance(value, ast.Attribute) and value.attr == name:
                function = _Bindings().visit(deepcopy(services[name]))
                function.decorator_list = wrappers + function.decorator_list
                return function
            return self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if node.level:
                if node.module == "transport":
                    return None
                return None
            return node

        def visit_ClassDef(self, node):
            if node.name == "Connection":
                return deepcopy(transport_connection)
            return node

        def visit_FunctionDef(self, node):
            if node.name == "session":
                return deepcopy(session)
            return node

    # The wrapper subclass injects services, but source fixtures require the actual
    # transport class body and its old one-argument construction contract.
    transport = trees["transport.py"]
    transport_connection = deepcopy(
        next(
            n
            for n in transport.body
            if isinstance(n, ast.ClassDef) and n.name == "Connection"
        )
    )
    transport_connection = _Bindings(class_owner=True).visit(transport_connection)
    constructor = next(
        n
        for n in transport_connection.body
        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
    )
    constructor.body = [
        n
        for n in constructor.body
        if not (
            isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Attribute) and t.attr == "runtime" for t in n.targets
            )
        )
    ]
    constructor.args.kwonlyargs = []
    constructor.args.kw_defaults = []
    bootstrap = TopLevelBindings().visit(deepcopy(trees["bootstrap.py"]))
    extra = [
        deepcopy(n)
        for n in transport.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name != "Connection"
    ]
    # Add ordinary imports that moved with top-level helpers (stdlib only).
    imports = [
        deepcopy(n)
        for tree in trees.values()
        for n in tree.body
        if isinstance(n, (ast.Import, ast.ImportFrom))
        and not (isinstance(n, ast.ImportFrom) and n.level)
    ]
    module = ast.Module(body=imports + extra + bootstrap.body, type_ignores=[])
    return ast.unparse(ast.fix_missing_locations(module)) + "\n"


class WorldSourcePath(_PathBase):
    """Only the canonical repository hub gets the extracted-source view."""

    def read_text(self, encoding=None, errors=None):
        canonical = Path(__file__).resolve().parents[1] / "local_game_server.py"
        if self.resolve() == canonical.resolve():
            return legacy_world_source()
        return super().read_text(encoding=encoding, errors=errors)
