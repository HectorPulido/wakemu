"""Audited normal Ouginak damage branches; spell side effects are separate.

Native conditions: group alternatives need spell6273 plus caster summons.
Spell6266's close damage339526 requires distance==1; ranged damage339524
requires distance>=2 but follows attraction301 and is unsupported here.
6260/6261 also change MP; selecting damage does not implement those effects.
"""


def bare_damage_selector(*, critical_chance, running_effects, summons, bonuses):
    """Return a selector only for an explicitly bare, zero-critical actor.

    Pass authoritative complete collections, not an absent/unknown state.
    """
    if (
        type(critical_chance) is not int
        or critical_chance != 0
        or running_effects is None
        or tuple(running_effects)
        or summons is None
        or tuple(summons)
        or bonuses is None
        or any(bonuses.values())
    ):
        raise ValueError(
            "Bare damage requires known zero critical/effects/summons/bonuses"
        )

    def select(spell_id, rule, actor, target, fight):
        if spell_id in (6260, 6261):
            expected = {6260: 339483, 6261: 241232}[spell_id]
            return rule["generic_effect"] == expected
        if spell_id == 6266:
            distance = abs(actor.position[0] - target.position[0]) + abs(
                actor.position[1] - target.position[1]
            )
            if distance != 1:
                return False  # Native attraction changes the effect evaluation.
            return dict(
                rule,
                generic_effect=rule["adjacent_generic_effect"],
                damage=rule["adjacent_damage"][actor.effective_level - 1],
            )
        return False

    return select
