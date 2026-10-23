"""Typed PL operand for versioned native drop-created area callbacks.

This module never changes callback
caster/target attribution, creates actors or executes a spell/effect.
"""


def callback_program_area_source(fight, invocation, *, state_reference=None):
    """Resolve an owned live Qq from a frozen original drop315 descriptor."""
    from .combat_encounter_area_callback_programs import (
        encounter_area_callback_programs,
    )
    from .combat_state_managers import registered_area_pv

    if (
        getattr(fight, "native_encounter_area_callback_programs", None) is None
        or invocation.state_uid is not None
    ):
        return None
    container = invocation.native_retained_container
    if (
        not isinstance(container, dict)
        or container.get("present") is not True
        or container.get("type") != 3
        or type(container.get("id")) is not int
        or container.get("native_kind") != "effect_area"
    ):
        return None
    row = getattr(fight, "native_effect_areas", {}).get(container["id"])
    if (
        row is None
        or row.get("uid") != container["id"]
        or row.get("owner_id") != invocation.caster_id
        or row.get("executing") is not True
        or row.get("level") != container.get("level")
    ):
        return None
    programs = encounter_area_callback_programs(fight)
    program = next(
        (
            item
            for item in programs
            if item["area_reference"] == row.get("reference")
            and (state_reference is None or item["state_reference"] == state_reference)
            and item["steps"][0]["role"] == "constructor"
            and item["steps"][0]["effect_family"] == 315
            and item["steps"][0]["effect_reference"] == row.get("effect_reference")
        ),
        None,
    )
    if program is None:
        return None
    pv = registered_area_pv(fight, row["uid"])
    if pv is None or not any(
        entry.reference == program["state_reference"]
        for entry in pv.state_ledger.entries
    ):
        return None
    return pv, program, row


def callback_program_level_source(fight, effect, values, invocation):
    """Read a real dropped Qq marker without changing native caster ownership."""
    if effect.get("effect_class") != 844:
        return None
    parameters = values["parameters"]
    if (
        len(parameters) < 8
        or parameters[7] != 1
        or ((parameters[5] + 128) % 256) - 128 in (1, 2)
    ):
        return None
    source = callback_program_area_source(
        fight, invocation, state_reference=parameters[6]
    )
    return None if source is None else source[0]


def callback_program_removal_selection_source(
    fight, effect, invocation, *, effects, definitions
):
    from .combat_encounter_area_seed_source import (
        native_removal_wrapper,
        native_removal_getter_path,
    )

    if not native_removal_wrapper(effect, invocation, effects):
        return None
    source = callback_program_area_source(fight, invocation)
    if source is None:
        return None
    pv, program, row = source
    definition = definitions.get(str(row["reference"]))
    if definition is None or not native_removal_getter_path(
        effect, invocation, effects, definition, program["state_reference"]
    ):
        return None
    return pv
