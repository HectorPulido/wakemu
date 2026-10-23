"""Pure native eZi321 parameter validation shared by admission and execution."""


def state_decurse_parameters(effect, values):
    # Keep the executor's error type without importing the state catalog.
    from .combat_effect_dispatch import UnsupportedEffectExecution

    if effect["effect_class"] != 321:
        raise UnsupportedEffectExecution("Only native state decurse321 is supported")
    parameters = values["parameters"]
    if len(parameters) not in (1, 2) or any(type(v) is not int for v in parameters):
        raise UnsupportedEffectExecution("Unsupported native decurse parameters")
    return parameters
