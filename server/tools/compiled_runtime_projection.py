"""Project reviewed runtime-only functions out of mixed compiler modules.

This module provides fingerprints only; it does not grant permission to reuse a
publication. A caller must separately prove that the old source matches the
publication's recorded SHA-256 and compare both projections. Unknown modules,
unsupported syntax and altered public function structure fail closed.
"""

import ast
import hashlib


# These functions are used by the running fight placement/scene machinery, not
# the eager catalog compiler. All imports, module globals, other functions and
# their signatures remain part of the projection. Extend only after review.
RUNTIME_FUNCTIONS = {
    "wakfu_server/combat/combat_placement_policy.py": frozenset({"_arena", "freeze"}),
    "wakfu_server/combat/combat_encounter_scene_layout.py": frozenset(
        {"scene_player_position"}
    ),
    "wakfu_server/combat/combat_terrain.py": frozenset({"local_arena"}),
    "wakfu_server/combat/combat_cell_group.py": frozenset(
        {"native_cell_criterion_presence"}
    ),
}


def masked_fingerprint(path, source):
    """Return a stable hash or None if the source cannot be safely projected."""
    names = RUNTIME_FUNCTIONS.get(path)
    if not names or not isinstance(source, (str, bytes)):
        return None
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, UnicodeDecodeError, ValueError, TypeError):
        return None

    found = set()
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names
        ):
            # A decorator may inspect bytecode or source at import time.
            if (
                node.name in found
                or node.decorator_list
                or isinstance(node, ast.AsyncFunctionDef)
            ):
                return None
            found.add(node.name)
            # Docstrings are observable through reflection and are not masked.
            doc = (
                node.body[:1]
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
                else []
            )
            node.body = doc + [ast.Pass()]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Decorators, annotations and defaults execute while importing the
            # module; they can make the function body externally observable.
            eager = [
                *node.decorator_list,
                *node.args.defaults,
                *(d for d in node.args.kw_defaults if d is not None),
            ]
            if node.returns is not None:
                eager.append(node.returns)
            eager.extend(
                arg.annotation
                for arg in [
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                ]
                if arg.annotation is not None
            )
            if any(
                isinstance(n, ast.Name) and n.id in names
                for expr in eager
                for n in ast.walk(expr)
            ):
                return None
        elif isinstance(node, ast.ClassDef):
            # Class bodies execute at import; reject ambiguous cases rather
            # than attempting to distinguish nested lazy definitions.
            if any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node)):
                return None
        else:
            # An eager top-level reference to the function can make its body
            # relevant even though the catalog compiler never calls it directly.
            if any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node)):
                return None
    if found != names:
        return None
    raw = ast.dump(tree, annotate_fields=True, include_attributes=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
