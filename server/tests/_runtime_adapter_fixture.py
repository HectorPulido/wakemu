"""Adapter fixtures using the same published definitions as World."""
from collections import ChainMap
from functools import lru_cache

import test_combat_effect_runtime as fixture_module
from wakfu_server.combat_static_catalogs import CompiledEffects


@lru_cache(maxsize=1)
def _compiled_effects():
    return CompiledEffects.from_published("player")


def runtime_fixture():
    compiled = _compiled_effects()
    delta = {}
    fixture = fixture_module.NativeRuntimeFactoryTests()
    fixture.setUp(effects=ChainMap(delta, compiled.source_effects))
    original_factory = fixture.factory

    def factory(**overrides):
        if "effects" in overrides or "states" in overrides:
            raise ValueError("Edit the adapter fixture's explicit effect delta")
        # A deliberately malformed selector stays local to this test. Reuse
        # the qualified immutable base and compile only that explicit delta;
        # the runtime's source object identity checks remain fully enforced.
        current = compiled.with_effect_delta(delta)
        return original_factory(
            effects=current.source_effects,
            states=current.source_states,
            compiled_effects=current,
            **overrides,
        )

    fixture.factory = factory
    return fixture
