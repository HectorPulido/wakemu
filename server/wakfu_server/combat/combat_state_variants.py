"""Native guW selection and explicit Wakemu paired-state variant policy.

ExportStateDecurseRules exhaustively exports states for which guW is true.
For the others eZk iterates every child, even during a critical spell. Selective
states use the carrier's actual rHA (Additional19), never the outer cast flag.
Wakemu additionally partitions structurally paired normal/critical root groups
by the actual causing execution branch. This is server policy, not a recovered
original fyW.ox caller; unrelated and mixed state roots preserve native ALL.
"""
from .combat_state_decurse import RULES
from .combat_native_container import resolve_state_container, resolve_state_wire_payload
from .combat_effect_removal import _identity_fields


def paired_state_variants(state, definitions):
    """Recognize two equivalent eYg roots carrying native dd(1) alternatives."""
    roots = getattr(state, "effect_ids", None)
    if (
        not isinstance(definitions, dict)
        or not isinstance(roots, (list, tuple))
        or len(roots) != 2
    ):
        return False
    rows = [definitions.get(str(reference)) for reference in roots]
    if any(not isinstance(row, dict) for row in rows):
        return False
    variants = [row.get("variant") for row in rows]
    if any(
        type(variant) is not int or variant not in (0, 1) for variant in variants
    ) or set(variants) != {0, 1}:
        return False
    fields = (
        "effect_class",
        "criteria",
        "parameters",
        "parameter_count",
        "target_masks",
        "native_target_selector",
        "native_effect_flags",
        "native_execution_mode",
        "native_timing_definition",
        "area_class",
        "area_native",
        "probability_base",
        "probability_per_level",
        "minimum_level",
        "maximum_level",
        "application_flag",
        "removal_flag",
        "native_localization_enabled",
        "native_hmi_actions",
    )
    if any(any(field not in row for field in fields) for row in rows):
        return False
    # eYg selects one successful child from each ordered alternative. Matching
    # root contracts distinguish this pair from independent cumulative effects.
    if any(
        row["effect_class"] != 330
        or not isinstance(row.get("children"), (list, tuple))
        or not row["children"]
        or any(type(child) is not int or child <= 0 for child in row["children"])
        for row in rows
    ):
        return False
    return all(rows[0][field] == rows[1][field] for field in fields)


def state_child_variant_mode(
    fight, state_uid, *, effect_definitions=None, causing_critical=None
):
    state = resolve_state_container(fight, state_uid)
    if state.reference not in RULES["selective_child_states"]:
        if not paired_state_variants(state, effect_definitions):
            return "ALL"
        if type(causing_critical) is not bool:
            raise ValueError("Missing actual causing branch for paired state variants")
        return "CRITICALS_ONLY" if causing_critical else "EFFECTS_ONLY"
    payload = resolve_state_wire_payload(fight, state_uid)
    if not isinstance(payload, str):
        raise ValueError("Missing selective state carrier critical authority")
    messages = {}
    _identity_fields(bytes.fromhex(payload), messages=messages)
    flags = _identity_fields(messages.get(8, b""), integer_fields=(19,))
    if flags.get(19) not in (0, 1):
        raise ValueError("Missing native state rHA critical flag")
    return "CRITICALS_ONLY" if flags[19] else "EFFECTS_ONLY"
