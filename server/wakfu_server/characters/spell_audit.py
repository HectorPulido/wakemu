"""Structural spell audit; eligibility never claims unresolved effects work.

This intentionally does not enable spell execution. Even a lone damage effect
needs targeting, critical, passive and conditional cost/range rules verified.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
from functools import lru_cache
import json
from .combat_definitions import effect_profile, state_profile
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("spell_audit.catalog")

    from wakfu_server.combat_common_spell_catalog import merge_effect_catalog

    return merge_effect_catalog(
        protocol_catalog.load(DATA_ROOT / "spell-effect-trees.json")
    )


@lru_cache(maxsize=1)
def costs_catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("spell_audit.costs_catalog")

    from wakfu_server.combat_common_spell_catalog import merge_cost_records

    return merge_cost_records(
        protocol_catalog.load(DATA_ROOT / "spell-costs.json")["spells"]
    )


@lru_cache(maxsize=1)
def states_catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("combat-state-definitions.json")

    return protocol_catalog.load(DATA_ROOT / "combat-state-definitions.json")


def inspect_spell(spell_id, level):
    if type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL:
        raise ValueError("Unsupported spell audit level")
    data = catalog()
    spell = data["spells"].get(str(spell_id))
    if spell is None:
        raise ValueError("Unknown spell audit reference")
    if level > len(spell["levels"]):
        raise ValueError("Missing native spell audit level")
    minimum, maximum, roots = spell["levels"][level - 1]
    output = []
    linked_states = []
    state_blockers = set()
    state_data = None

    def visit_state(reference, state_level, path):
        nonlocal state_data
        if reference in path:
            state_blockers.add("recursive_state_application")
            return
        if state_data is None:
            state_data = states_catalog()
        definition = state_data["states"].get(str(reference))
        if definition is None:
            state_blockers.add("unknown_applied_state")
            return
        if not 0 <= state_level <= 32767:
            state_blockers.add("invalid_native_state_level")
            return
        native = state_profile(state_data, reference, state_level)
        linked_states.append(
            dict(
                reference=reference,
                level=native["level"],
                duration=native["duration"],
                clock_actor=definition["clock_actor"],
                tick_at_turn_end=definition["tick_at_turn_end"],
            )
        )
        for root in native["effects"]:
            visit(root, (), native["level"], state_data["effects"], (*path, reference))

    def visit(
        reference, ancestors, evaluation_level=level, effect_data=None, state_path=()
    ):
        if reference in ancestors:
            raise ValueError("Cyclic native effect tree")
        effect = (effect_data or data["effects"])[str(reference)]
        values = effect_profile(effect, evaluation_level)
        parameters = values["parameters"]
        output.append(
            dict(
                reference=reference,
                effect_class=effect["effect_class"],
                variant=effect["variant"],
                criteria=effect["criteria"],
                probability=values["probability"],
                parameter0=parameters[0] if parameters else None,
                parameters=parameters,
                evaluation_level=evaluation_level,
                state_path=list(state_path),
                native_hmi_actions=effect.get("native_hmi_actions", {}),
                target_masks=effect.get("target_masks"),
                children=effect["children"],
                ancestors=list(ancestors),
            )
        )
        for child in effect["children"]:
            visit(
                child,
                (*ancestors, reference),
                evaluation_level,
                effect_data,
                state_path,
            )
        if effect["effect_class"] == 304:
            if len(parameters) < 2:
                state_blockers.add("missing_state_application_parameters")
            else:
                visit_state(parameters[0], parameters[1], state_path)

    for root in roots:
        visit(root, ())
    blockers = []
    normal = [e for e in output if e["variant"] == 0]
    if any(e["variant"] not in (0, 1) for e in output):
        blockers.append("unknown_effect_variants")
    if any(e["criteria"] for e in normal):
        blockers.append("native_conditions")
    if any(e["target_masks"] and any(e["target_masks"]) for e in normal):
        blockers.append("native_masks_require_evaluation")
    if any(e["effect_class"] not in (1, 2, 3, 4, 5) for e in normal):
        blockers.append("extra_effects_or_groups")
    if len(normal) != 1:
        blockers.append("multiple_or_absent_normal_effects")
    if any(e["probability"] != 100 for e in normal):
        blockers.append("probabilistic_effects")
    costs = costs_catalog()[str(spell_id)]
    if costs["conditional"]:
        blockers.append("conditional_costs_or_range")
    blockers.extend(sorted(state_blockers))
    return dict(
        spell_id=spell_id,
        level=level,
        minimum=minimum,
        maximum=maximum,
        line_of_sight=spell["line_of_sight"],
        linear=spell["linear"],
        free_cell=spell["free_cell"],
        effects=output,
        linked_states=linked_states,
        blockers=blockers,
        structurally_simple=not blockers,
        execution_verified=False,
    )
