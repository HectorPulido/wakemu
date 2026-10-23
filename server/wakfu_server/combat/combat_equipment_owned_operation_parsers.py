"""Pure adapters for existing owned removal and healing operation parsers.

Parsing never grants execution authority. The caller must separately prove each
returned context against its configured factory and preserve the dispatcher's
live recipient, retained-population, event and transaction checks.
"""


from .combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS


FAMILIES = frozenset((*DAMAGE_FAMILIES, *HEAL_ELEMENTS, 321, 421))
OPERATION_IDS = {
    **dict.fromkeys(DAMAGE_FAMILIES, "damage.apply"),
    **dict.fromkeys(HEAL_ELEMENTS, "healing.apply"),
    321: "state.decurse",
    421: "effect.dispel",
}


def _no_rounding():
    raise ValueError("Static healing parsing cannot draw transaction RNG")


def parse(effect, profile, registry):
    """Return (parameters, required contexts, dependencies, error).

    ``registry`` is accepted for the common parser interface; these operators
    do not derive their semantics from the characteristic registry. A parsed
    removal reference is a selection operand, not a state-application edge.
    Reapplication after partial decurse remains owned by the real state handler.
    """
    family = effect.get("effect_class")
    if family not in FAMILIES:
        return None, (), (), "no owned removal/healing parameter adapter"
    try:
        if family in DAMAGE_FAMILIES:
            from .combat_equipment_damage_capability import parse as parse_damage

            return parse_damage(effect)
        if family == 321:
            from .combat_state_decurse_parameters import state_decurse_parameters

            parameters = state_decurse_parameters(effect, profile)
            parsed = dict(
                reference=parameters[0],
                reduction=parameters[1] if len(parameters) == 2 else None,
            )
            requirements = (
                "owned_state_removal_and_reapplication",
                "native_runner_lifecycle",
            )
        elif family == 421:
            from .combat_dispel import FLAG_SEMANTICS, dispel_flags, select_dispel

            parameters = tuple(profile["parameters"])
            select_dispel((), parameters)
            flags = effect.get("native_effect_flags")
            if (
                not isinstance(flags, (tuple, list))
                or any(type(flag) is not int for flag in flags)
                or len(set(flags)) != len(flags)
                or set(flags) - FLAG_SEMANTICS.keys()
            ):
                raise ValueError("Unaudited native dispel flags")
            # The shared helper requires an actual lifecycle for suppression
            # flags5/6. Never fabricate one during this static parse.
            if not set(flags) & {5, 6}:
                dispel_flags(effect, event_lifecycle=None)
            parsed = dict(selection_parameters=parameters)
            requirements = ("native_dispel_retention", "native_runner_lifecycle")
        else:
            from .combat_healing_parameters import (
                healing_parameter_specification,
                interpret_healing_parameters,
            )

            level = effect.get("_capability_level")
            if type(level) is not int or not -32768 <= level <= 32767:
                raise ValueError("Missing native capability level")
            specification = healing_parameter_specification(effect["parameters"], level)
            requirements = ["native_healing_execution", "native_runner_lifecycle"]
            if specification["base_kind"]:
                # This is a source parameter, not a calculated healing amount.
                # Actual actor HP and stochastic rounding remain runtime-owned.
                parsed = dict(specification)
                parsed["base_parameter"] = parsed.pop("base")
                requirements.append("native_healing_hp_and_rounding")
            else:
                parsed = interpret_healing_parameters(
                    effect["parameters"], level, hp_context=None, rng=_no_rounding
                )
    except (KeyError, TypeError, ValueError) as error:
        return None, (), (), "invalid native owned operation parameters: " + str(error)
    return parsed, tuple(requirements), (), None
