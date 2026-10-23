"""Reversible server health policy; configuration changes never heal wounds.

This is an explicit server policy, not a claim about native build-save rules.
Death is independent of the temporary maximum. A living character normally
retains at least one HP when configuration reduces the maximum below its
stored wound; a typed native equipment projection can preserve a legitimate
zero-current PA without setting the independent death bit.
"""
from psycopg.pq import TransactionStatus


def visible(maximum, damage, dead, hp_zero_valid=False):
    if (
        type(maximum) is not int
        or not 0 < maximum < 2**31
        or type(damage) is not int
        or not 0 <= damage < 2**63
        or type(dead) is not bool
        or type(hp_zero_valid) is not bool
        or hp_zero_valid
        and (dead or damage < maximum)
    ):
        raise ValueError("Invalid canonical health")
    return 0 if dead or hp_zero_valid else max(1, maximum - damage)


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
    zero_valid = (
        character.get("hp_zero_valid", False) and character["hp_damage"] >= maximum
    )
    hp = visible(maximum, character["hp_damage"], character["health_dead"], zero_valid)
    db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s,hp_zero_valid=%s WHERE id=%s AND account_id=%s",
        (hp, maximum, zero_valid, character["id"], character["account_id"]),
    )
    _advance_projection_current(db, character, hp)
    return hp


def apply(db, character, hp):
    damage, dead = changed(character, hp)
    return apply_damage(db, character, damage, dead)


def apply_damage(db, character, damage, dead, hp_zero_valid=False):
    hp = visible(character["max_hp"], damage, dead, hp_zero_valid)
    stored_zero_valid = hp == 0 and not dead and hp_zero_valid
    result = db.execute(
        "UPDATE characters SET hp=%s,hp_damage=%s,health_dead=%s,hp_zero_valid=%s "
        "WHERE id=%s AND account_id=%s AND hp=%s",
        (
            hp,
            damage,
            dead,
            stored_zero_valid,
            character["id"],
            character["account_id"],
            character["hp"],
        ),
    )
    if result.rowcount != 1:
        raise ValueError("Stale canonical health transition")
    _advance_projection_current(db, character, hp)
    return hp


def apply_native_equipment_hp(db, character, *, hp, maximum):
    """Persist the exact result of replaying owned native eWO HP operations.

    This deliberately preserves a dead character's separate death state. A
    zero-current live PA is stored with `hp_zero_valid` instead of being turned
    into a casualty or raised to the living-policy floor.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Native equipment HP transition requires caller transaction")
    if (
        not isinstance(character, dict)
        or type(hp) is not int
        or type(maximum) is not int
        or not 0 < maximum < 2**31
        or not 0 <= hp <= maximum
        or type(character.get("health_dead")) is not bool
    ):
        raise ValueError("Invalid native equipment HP result")
    dead = character["health_dead"]
    if dead and hp != 0:
        raise ValueError(
            "Native equipment projection cannot resurrect a dead character"
        )
    # Preserve the canonical max-minus-current wound while both PA bounds and
    # current change. A current-only delta would double-count eWO's max shift.
    damage = max(
        0,
        character.get("hp_damage", character["max_hp"] - character["hp"])
        + maximum
        - character["max_hp"]
        + character["hp"]
        - hp,
    )
    zero_valid = hp == 0 and not dead
    result = db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=%s,health_dead=%s,hp_zero_valid=%s "
        "WHERE id=%s AND account_id=%s AND hp=%s",
        (
            hp,
            maximum,
            damage,
            dead,
            zero_valid,
            character["id"],
            character["account_id"],
            character["hp"],
        ),
    )
    if result.rowcount != 1:
        raise ValueError("Stale native equipment HP transition")
    return dict(
        character,
        hp=hp,
        max_hp=maximum,
        hp_damage=damage,
        health_dead=dead,
        hp_zero_valid=zero_valid,
    )


def _advance_projection_current(db, character, hp):
    """Apply an actual current write through the native effective-HP setter.

    A raw PA above its effective cap survives an untouched fight return. Once
    gameplay or a maximum reconfiguration writes current HP, native ``on``
    clamps that write to the effective bounds; retaining the old over-cap
    offset would make the projection disagree with canonical health.
    Frozen raw pools do not accept current mutations.
    """
    if hp == character["hp"]:
        return
    db.execute(
        "UPDATE character_equipment_hp_projection SET raw_current=%s,revision=revision+1 "
        "WHERE character_id=%s AND NOT frozen",
        (hp, character["id"]),
    )
