"""Damage qualification for the reconstructed Rii distance lesson.

The event producer must bind an authenticated, owner-specific encounter and
invoke this inside the spell preview transaction at the instant of impact.
Four alternating zones and the fixed damage are reconstructions; they are not
evidence of the original encounter script. This module does not start fights,
grant spells, or award quest progress.
"""

from .lesson_distance import SPELL, REQUIRED_HITS, observe

# Native damage effect belonging to the installed version of spell 7967.
DAMAGE_EFFECT = 361204

# The lesson alternates a close zone (one or two cells) and a far zone (three
# or more), matching the captured casts from two, three, two and three cells.
CLOSE_MESSAGE = "Hit the sack from 1 or 2 cells away."
FAR_MESSAGE = "Hit the sack from 3 or more cells away."

# Four qualifying casts of the 25-damage lesson spell end the encounter.
LESSON_MAXIMUM_HP = 25 * REQUIRED_HITS


def hint(hits):
    """Return the guide notice shown after a qualifying hit, if any."""
    if type(hits) is not int or not 0 < hits < 4:
        return None
    return FAR_MESSAGE if hits % 2 else CLOSE_MESSAGE


def initialize(fight, packets, *, action_id):
    """Install the distance spell only into this owned combat preview."""
    contract = getattr(fight, "rii_distance_lesson_contract", None)
    if contract is None:
        return False
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return True
    if (
        not isinstance(contract, dict)
        or fight.phase != "active"
        or contract.get("initialized") is not None
    ):
        raise ValueError("Invalid distance lesson start")
    owner, target = contract.get("owner"), contract.get("target")
    if (
        owner not in fight.actors
        or target not in fight.actors
        or fight.actors[owner].team == fight.actors[target].team
    ):
        raise ValueError("Invalid distance lesson participants")
    from wakfu_server.rii_lesson_grants import install

    contract["grant_uids"] = install(
        fight,
        owner,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
        lesson="distance",
    )
    contract["initialized"] = True
    # The captured lesson ends with the sack destroyed after four 25-damage
    # casts, so the bound prop must own exactly that much life; a scaled monster
    # would survive the qualified fourth hit and then take no damage at all.
    from wakfu_server.combat_hp_raw import set_hp_raw_current, set_hp_raw_maximum

    sack = fight.actors[target]
    if getattr(sack, "max_hp", None) == getattr(sack, "hp", None) is None:
        pass
    elif sack.max_hp != LESSON_MAXIMUM_HP:
        set_hp_raw_maximum(sack, LESSON_MAXIMUM_HP)
        set_hp_raw_current(sack, LESSON_MAXIMUM_HP)
    from wakfu_server.ecology_feedback import information

    packets.append(information("Distance lesson: hit the sack from 1 or 2 cells away."))
    return True


def hit(fight, *, source_id, target_id, effect_reference, damage):
    """Return tutorial HP damage or None when this is not a bound target.

    The caller uses the returned value for the actual native damage operation.
    Calling with unqualified damage cannot advance or kill the tutorial sack.
    Fight preview/commit owns all mutations, including the hit counter.
    """
    contract = getattr(fight, "rii_distance_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return None
    if not isinstance(contract, dict) or target_id != contract.get("target"):
        return None
    owner = contract.get("owner")
    if effect_reference != DAMAGE_EFFECT or source_id != owner or damage <= 0:
        return 0
    attacker = fight.actors.get(source_id)
    target = fight.actors.get(target_id)
    if attacker is None or target is None:
        raise ValueError("Missing distance lesson combatant")
    previous = {"hits": contract.get("hits", 0)}
    updated = observe(
        previous,
        owner_id=owner,
        target_id=target_id,
        source_id=source_id,
        hit_target_id=target_id,
        spell_id=SPELL,
        source_xy=attacker.position[:2],
        target_xy=target.position[:2],
        damage=damage,
    )
    contract.update(updated)
    return 25 if updated["hits"] > previous["hits"] else 0


def qualified(fight):
    """Identify completion without granting a victory or mission reward."""
    contract = getattr(fight, "rii_distance_lesson_contract", None)
    return isinstance(contract, dict) and contract.get("hits") == REQUIRED_HITS
