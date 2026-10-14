"""Bounded test preparation for native whole-map stochastic cell effects.

This module changes fixture geometry and an ordinary transaction RNG seed only.
It never changes effect definitions, eligibility, cell selection or runtime RNG.
"""
from contextlib import contextmanager
import random
from unittest.mock import patch


def requires_wholemap_cell_scene(roots, effects):
    pending = list(roots)
    seen = set()
    found = False
    while pending:
        identity = pending.pop()
        if type(identity) is not int:
            raise ValueError("Invalid actual native scene effect identity")
        if identity in seen:
            continue
        seen.add(identity)
        if len(seen) > 256:
            raise ValueError("Native cell scene closure exceeds bound")
        effect = effects.get(str(identity))
        if not isinstance(effect, dict):
            raise ValueError("Missing actual native cell scene definition")
        if (
            effect.get("effect_class") == 349
            and effect.get("area_class") == "anA"
            and effect.get("area_native") == "empty"
        ):
            found = True
        children = effect.get("children", ())
        if not isinstance(children, (list, tuple)):
            raise ValueError("Malformed native scene child list")
        pending.extend(children)
    return found


@contextmanager
def wholemap_native_scene_fixture(roots, effects, *, seed=1):
    """Prepare a normal bounded native arena and reproducible ordinary RNG.

    Callers may exercise seeds0..3 within their existing attempt budget. A seed
    selecting an invalid landing is a legitimate no-op, not a missing handler.
    The returned receipt distinguishes fixture preparation from spell success.
    """
    if type(seed) is not int or not 0 <= seed <= 3:
        raise ValueError("Fixture stochastic seed exceeds bounded policy")
    if not requires_wholemap_cell_scene(roots, effects):
        yield {"policy": "unchanged_native_fixture", "prepared": False}
        return
    from wakfu_server import combat_terrain
    from wakfu_server import combat_npc_spell

    original_arena = combat_terrain.local_arena
    original_spell = combat_npc_spell.prepare_npc_spell
    receipt = dict(
        policy="native_wholemap_fixture_v1",
        prepared=True,
        ordinary_transaction_seed=seed,
        forced_random_draws=False,
        scenes=[],
    )

    def bounded_arena(*args, **kwargs):
        result = original_arena(*args, **dict(kwargs, compact=False))
        receipt["scenes"].append(
            dict(
                validated_cell_count=len(result["validated_cells"]),
                native_border_policy=result["native_border_policy"],
            )
        )
        return result

    def seeded_spell(*args, **kwargs):
        return original_spell(*args, **dict(kwargs, rng=random.Random(seed)))

    with patch.object(combat_terrain, "local_arena", bounded_arena), patch.object(
        combat_npc_spell, "prepare_npc_spell", seeded_spell
    ):
        yield receipt
