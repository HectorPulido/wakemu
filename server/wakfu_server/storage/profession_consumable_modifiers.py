"""Native eXx profession bonuses from owned, active consumable states.

eVi binds each effect class to an eRJ modifier and action kind. eXx reads
parameter zero as amount and optional parameter one as a profession identity;
eRM adds profession-specific and global amounts. No item-name heuristics apply.
"""
import json
from pathlib import Path

_SOURCE = json.loads(
    Path(__file__).with_name("profession_consumable_effects.json").read_text()
)
EFFECTS = {int(key): value for key, value in _SOURCE["effects"].items()}
KINDS = {
    2001: "collect_quantity",
    2002: "craft_speed",
    2003: "plant_speed",
    2004: "collect_speed",
    2006: "craft_xp",
    2007: "plant_xp",
    2008: "collect_xp",
}


def aggregate(states, profession_id, *, is_battleground=None):
    """Resolve installed native effects at state level without advancing clocks.

    Conditional effects require an explicit authoritative environment result;
    unknown context never turns a native criterion into an unconditional buff.
    """
    if type(profession_id) is not int or profession_id <= 0:
        raise ValueError("Invalid profession modifier identity")
    if is_battleground is not None and type(is_battleground) is not bool:
        raise ValueError("Invalid profession battleground context")
    result = dict.fromkeys(KINDS.values(), 0)
    for state in states:
        level = state.get("level")
        if type(level) is not int or not 1 <= level <= 32767:
            raise ValueError("Invalid profession consumable state level")
        for identity in state.get("effect_ids", ()):
            effect = EFFECTS.get(identity)
            if effect is None:
                continue
            contribution = effect_modifiers(
                effect,
                level,
                profession_id,
                is_battleground=is_battleground,
            )
            for kind, amount in contribution.items():
                result[kind] += amount
    return result


def effect_modifiers(
    effect, level, profession_id, *, is_battleground=None, beta_mode=None
):
    """Interpret one original eXx leaf for consumables or actual guild effects."""
    if type(profession_id) is not int or profession_id <= 0:
        raise ValueError("Invalid profession modifier identity")
    if type(level) is not int or not 1 <= level <= 32767:
        raise ValueError("Invalid profession effect level")
    if beta_mode is not None and type(beta_mode) is not bool:
        raise ValueError("Invalid profession beta mode context")
    result = dict.fromkeys(KINDS.values(), 0)
    criterion = effect["criteria"]
    if criterion and not (
        criterion == "not IsBattleground()"
        and is_battleground is False
        or criterion == 'not GetBooleanSystemConfiguration("beta.mode")'
        and beta_mode is False
    ):
        return result
    if (
        effect["variant"] != 0
        or not effect["minimum_level"] <= level <= effect["maximum_level"]
    ):
        raise ValueError("Unsupported native profession effect variant or level")
    parameters = effect["parameters"]
    if (
        effect["parameter_count"] not in (1, 2)
        or len(parameters) != 2 * effect["parameter_count"]
    ):
        raise ValueError("Invalid native profession effect parameters")
    amount = int(parameters[0] + parameters[1] * level)
    scope = (
        0
        if effect["parameter_count"] == 1
        else int(parameters[2] + parameters[3] * level)
    )
    if scope in (0, profession_id):
        result[KINDS[effect["effect_class"]]] = amount
    return result


def modifiers(
    store, db, character_id, profession_id, *, generation=None, is_battleground=None
):
    """Combine owned equipment with durable buffs inside the action transaction."""
    from wakfu_server.consumable_buffs import evaluated_states
    from wakfu_server.profession_equipment_modifiers import (
        modifiers as equipment_modifiers,
    )

    result = aggregate(
        evaluated_states(store, db, character_id, generation=generation),
        profession_id,
        is_battleground=is_battleground,
    )
    equipment = equipment_modifiers(store, db, character_id, profession_id)
    from wakfu_server.characters.guild_member_effects import profession_modifiers

    guild = profession_modifiers(store, db, character_id, profession_id)
    return {
        kind: amount + equipment[kind] + guild[kind] for kind, amount in result.items()
    }


def duration_ms(base, percent):
    """Original collect/plant speed ratio with Java Math.round semantics."""
    if (
        type(base) is not int
        or not 0 <= base < 2**63
        or type(percent) is not int
        or percent <= -100
    ):
        raise ValueError("Invalid profession duration modifier")
    if base == 0:
        return 0
    denominator = 100 + percent
    return max(1, (2 * base * 100 + denominator) // (2 * denominator))


def collected_quantity(base, percent, *, operation):
    """Server policy: preserve fractional gathering yield with stochastic rounding.

    The percentage and profession scope are native; fractional rounding is an
    explicit server policy, shared with recycling. A server-generated durable
    occupation token seeds a private RNG so transaction retry cannot reroll it.
    Successful action receipts already fence repeated completion deliveries.
    """
    if (
        type(base) is not int
        or not 1 <= base <= 32767
        or type(percent) is not int
        or percent < 0
        or not isinstance(operation, str)
        or not 1 <= len(operation) <= 200
    ):
        raise ValueError("Invalid profession quantity modifier")
    if percent == 0:
        return base
    from random import Random
    from wakfu_server.recycling import stochastic_round

    amount = base * (100 + percent) / 100
    quantity = stochastic_round(
        amount, Random("profession-yield:" + operation).random()
    )
    if not 1 <= quantity <= 32767:
        raise ValueError("Modified profession yield exceeds inventory quantity width")
    return quantity
