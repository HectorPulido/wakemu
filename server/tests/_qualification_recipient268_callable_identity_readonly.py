"""Describe existing decorated callable chains without replacing any code."""
import importlib, json, unittest
from pathlib import Path


def qualify():
    from wakfu_server.combat_effect_dispatch import EffectDispatcher
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory

    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    out = {}
    for name, fn in [
        ("init", EffectDispatcher.__init__),
        ("execute", EffectDispatcher._execute),
        ("factory", NativeEffectRuntimeFactory.__call__),
        ("roles", roles.bind_roles),
    ]:
        chain = []
        while True:
            chain.append(
                dict(
                    qualname=fn.__qualname__,
                    name=fn.__name__,
                    file=fn.__code__.co_filename,
                    line=fn.__code__.co_firstlineno,
                    kwdefaults=fn.__kwdefaults__,
                )
            )
            if not hasattr(fn, "__wrapped__"):
                break
            fn = fn.__wrapped__
        out[name] = chain
    Path(
        ".runtime/parallel-readiness-20261021/recipient268-existing-callable-chains-readonly.json"
    ).write_text(json.dumps(out, indent=2, default=str) + "\n")
    return unittest.TestSuite()
