"""Explicit Wakemu AI predicate policy; not recovered native ffb lifetime.

Every authorized spell is recorded on its transaction preview before effects.
The actor-owned count lasts for this fight, including zero-cost/no-op spells.
Forecasts and failed serialization never adopt that private history.
"""
POLICY = "wakemu.actor-fight-authorized-spell-history-v1"


def fresh_history():
    return {"policy": POLICY, "casts": {}}


def _history(fight):
    history = getattr(fight, "wakemu_ai_cast_history", None)
    if (
        not isinstance(history, dict)
        or set(history) != {"policy", "casts"}
        or history["policy"] != POLICY
    ):
        raise ValueError("Missing owned Wakemu AI spell-history policy")
    rows = history["casts"]
    if not isinstance(rows, dict):
        raise ValueError("Malformed owned AI spell history")
    for actor, spells in rows.items():
        if (
            not isinstance(actor, str)
            or str(int(actor)) != actor
            or not -(1 << 63) <= int(actor) < (1 << 63)
        ):
            raise ValueError("Invalid AI history actor identity")
        if not isinstance(spells, dict):
            raise ValueError("Invalid actor-owned AI spell history")
        for spell, count in spells.items():
            if (
                not isinstance(spell, str)
                or str(int(spell)) != spell
                or not 0 < int(spell) < (1 << 31)
                or type(count) is not int
                or count <= 0
            ):
                raise ValueError("Invalid AI history spell/count")
    return rows


def record_authorized_cast(fight, actor_id, spell_id):
    if (
        type(actor_id) is not int
        or actor_id not in fight.actors
        or type(spell_id) is not int
        or not 0 < spell_id < (1 << 31)
    ):
        raise ValueError("Missing authorized spell actor/reference")
    rows = _history(fight)
    spells = rows.setdefault(str(actor_id), {})
    key = str(spell_id)
    spells[key] = spells.get(key, 0) + 1


def has_cast_spell(fight, actor_id, spell_id):
    from .combat_native_actor_lookup import native_actor

    if type(actor_id) is not int or native_actor(fight, actor_id) is None:
        raise ValueError("Missing owned AI predicate actor")
    if type(spell_id) is not int or not -(1 << 31) <= spell_id < (1 << 31):
        raise ValueError("Invalid AI predicate spell reference")
    return _history(fight).get(str(actor_id), {}).get(str(spell_id), 0) > 0
