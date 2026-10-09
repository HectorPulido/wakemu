"""Native eWu class304 state reference, level, and chance parameters."""

import math

from .combat_parameters import _float32, _integer


def _short(value):
    return ((value + 32768) % 65536) - 32768


def native_float_parameter(parameters, index, level):
    """eVn.w; share the existing float32/Math.round native implementation."""
    from .combat_level_group import _native_float_parameter

    return _native_float_parameter(parameters, index, level)


def interpret_state_parameters(
    parameters, *, owned_spell_level=None, level_factor=None
):
    if (len(parameters) not in (3, 4, 5) and len(parameters) < 6) or any(
        type(v) is not int for v in parameters
    ):
        raise ValueError("Unsupported native state applicator parameter mode")
    reference, requested_level, chance = parameters[:3]
    reference = _short(reference)
    level = _short(requested_level)
    if reference <= 0:
        raise ValueError("Unsupported native state reference")
    if level < 0 and len(parameters) not in (4, 5):
        raise ValueError("Unsupported native state level")
    if len(parameters) not in (4, 5):
        if owned_spell_level is not None or level_factor is not None:
            raise ValueError("Unexpected native dynamic state level authority")
    else:
        spell_reference = parameters[3]
        if type(spell_reference) is not int:
            raise ValueError("Invalid native owned spell reference")
        if owned_spell_level is not None:
            if (
                type(owned_spell_level) is not int
                or not -32768 <= owned_spell_level <= 32767
            ):
                raise ValueError("Invalid native owned spell level")
            level = _short(owned_spell_level)
            if len(parameters) == 5:
                if type(level_factor) is not float:
                    raise ValueError("Missing native state level multiplier")
                product = _float32(_float32(level) * _float32(level_factor))
                level = _short(
                    _integer(math.trunc(product) if math.isfinite(product) else product)
                )
        elif len(parameters) == 5 and level_factor is not None:
            raise ValueError("State multiplier requires an owned spell level")
    if level < 0:
        raise ValueError("Unsupported native negative state level")
    return dict(
        reference=reference,
        level=level,
        chance_parameter=chance,
        application_chance=100 if chance == -1 else 0 if chance == -2 else chance,
    )
