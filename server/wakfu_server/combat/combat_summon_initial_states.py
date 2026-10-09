"""Fresh bje.aQc -> big.a(eGH.cle) plans, distinct from an action book.

These rows describe initial eWu construction, not ordinary cast304 parameters.
Execution needs the actual detached actor's PN/state manager and Qf authority.
"""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def native_initial_states():
    path = (
        Path(__file__).resolve().parents[2]
        / "protocol"
        / "native-class-summon-initial-states.json"
    )
    from .combat_captured_dependencies import merge_profile_component
    from .combat_copy_dependencies import (
        merge_profile_component as merge_copy_component,
    )

    return merge_copy_component(
        merge_profile_component(
            protocol_catalog.load(path)["profiles"],
            "initial_state_triples",
        ),
        "initial_state_triples",
    )


@dataclass(frozen=True)
class NativeSummonInitialState:
    state_id: int
    level: int
    native_rBq: bool
    native_rBr: bool = True


def initial_state_plan(raw_triples, descriptor_level):
    if type(descriptor_level) is not int or not 0 <= descriptor_level <= 32767:
        raise ValueError("Missing native descriptor level")
    if not isinstance(raw_triples, (list, tuple)) or len(raw_triples) % 3:
        raise ValueError("Malformed native initial-state triples")
    if any(
        type(value) is not int or not -32768 <= value <= 32767 for value in raw_triples
    ):
        raise ValueError("Malformed native initial-state short")
    result = []
    for offset in range(0, len(raw_triples), 3):
        state_id, level, flag = raw_triples[offset : offset + 3]
        result.append(
            NativeSummonInitialState(
                state_id,
                descriptor_level if level == -1 else level,
                flag == 0,
            )
        )
    return tuple(result)
