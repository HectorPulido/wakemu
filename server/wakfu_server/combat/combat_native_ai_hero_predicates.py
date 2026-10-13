"""eNT account-primary comparison and eIu's explicit ffc/ffb query bridge.

IsHero is not a player-kind test: the native absent primary is zero, so a
fresh NPC with account zero and nonzero identity satisfies the predicate.
AIHasCastSpell requires a genuine AI decision context; ordinary effect casts
must not manufacture that context from unrelated cast-event history.
"""
from collections.abc import Mapping


def native_is_hero(actor_id, account_id, primary_id):
    for value in (actor_id, account_id, primary_id):
        if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
            raise ValueError("Missing native IsHero actor/account/primary identity")
    return primary_id != actor_id


def registered_is_hero(fight, actor, authority):
    if authority.targeting.get("is_eGj") is not True:
        raise ValueError("Native IsHero requires the selected eGj")
    account = authority.native_account_id
    primary = authority.native_primary_character_id
    registry = getattr(fight, "native_account_primary_registry", None)
    if registry is not None:
        if not isinstance(registry, Mapping) or any(
            type(k) is not int
            or type(v) is not int
            or not -(1 << 63) <= k < (1 << 63)
            or not -(1 << 63) <= v < (1 << 63)
            for k, v in registry.items()
        ):
            raise ValueError("Invalid native fkJ account-primary registry")
        if type(account) is not int:
            raise ValueError("Missing native IsHero account identity")
        primary = registry.get(account, 0)  # fkJ.sS Trove no-entry value.
    return native_is_hero(actor.id, account, primary)


def ai_has_cast_spell(context, spell_id):
    if type(spell_id) is not int or not -(1 << 31) <= spell_id < (1 << 31):
        raise ValueError("Invalid native AI spell reference")
    query = getattr(context, "has_cast_spell", None)
    if not callable(query):
        raise ValueError("Missing native ffc/ffb AI spell-query authority")
    result = query(spell_id)
    if type(result) is not bool:
        raise ValueError("Invalid native ffb.TY result")
    return result
