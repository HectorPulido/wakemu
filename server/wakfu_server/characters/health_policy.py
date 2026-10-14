"""Reversible server health policy; configuration changes never heal wounds.

This is an explicit server policy, not a claim about native build-save rules.
Death is independent of the temporary maximum. A living character retains at
least one HP when configuration reduces the maximum below its stored wound.
"""


def visible(maximum, damage, dead):
    if (
        type(maximum) is not int
        or not 0 < maximum < 2**31
        or type(damage) is not int
        or not 0 <= damage < 2**63
        or type(dead) is not bool
    ):
        raise ValueError("Invalid canonical health")
    return 0 if dead else max(1, maximum - damage)


def changed(character, hp):
    """Apply actual HP damage/healing, preserving hidden configuration wounds."""
    if type(hp) is not int or not 0 <= hp <= character["max_hp"]:
        raise ValueError("Invalid actual health transition")
    damage = max(0, character["hp_damage"] + character["hp"] - hp)
    return damage, hp == 0


def recover_finished_return(maximum, damage, dead):
    """Explicit Wakemu exploration recovery after an acknowledged fight return.

    A terminal casualty returns with one HP and may regenerate. This does not
    resurrect an in-combat actor, infer a Phoenix position, or recover an active
    disconnect. The caller owns the finished-fight/return and once-only fences.
    """
    visible(maximum, damage, dead)
    return (maximum - 1, False) if dead else (damage, dead)


def reconfigure(db, character, maximum):
    hp = visible(maximum, character["hp_damage"], character["health_dead"])
    db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s WHERE id=%s AND account_id=%s",
        (hp, maximum, character["id"], character["account_id"]),
    )
    return hp


def apply(db, character, hp):
    damage, dead = changed(character, hp)
    return apply_damage(db, character, damage, dead)


def apply_damage(db, character, damage, dead):
    hp = visible(character["max_hp"], damage, dead)
    result = db.execute(
        "UPDATE characters SET hp=%s,hp_damage=%s,health_dead=%s "
        "WHERE id=%s AND account_id=%s AND hp=%s",
        (hp, damage, dead, character["id"], character["account_id"], character["hp"]),
    )
    if result.rowcount != 1:
        raise ValueError("Stale canonical health transition")
    return hp
