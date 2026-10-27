"""Explicit company-size selection of the original native6808 state graph.

Only the grade policy is reconstructed. AP, MP, damage, healing, resistance and
HP changes execute the installed native consumers at the selected state grade.
Five/six-member custom companies explicitly preserve their ordinary baseline.
"""

from collections.abc import Mapping

GRADE_POLICY = "wakemu.company-compensation-1-to-4-v1"


def company_actor_ids(fight):
    """Return admitted player roots and registered sidekicks, never summons."""
    from wakfu_server.combat_companions import registered_companion_ids
    from wakfu_server.combat_encounter_roles import assigned_roles

    player_team = assigned_roles(fight).player_team
    companions = registered_companion_ids(fight)
    summons = getattr(fight, "native_summon_registrations", {})
    roots = {
        uid
        for uid, actor in fight.actors.items()
        if actor.team == player_team
        and actor.controlled
        and uid not in summons
        and getattr(actor, "native_summon_source", None) is None
        and getattr(actor, "is_summon", False) is not True
    }
    if any(fight.actors[uid].team != player_team for uid in companions):
        raise ValueError("Rift companion differs from the admitted player team")
    return tuple(sorted(roots | companions))


def install_company_compensation(dispatcher, *, actor_ids):
    """Install the original compensation once on the complete entry company.

    Caller owns the detached preview and RNG; discard both on any exception.
    Existing company members are not reinitialized at later wave boundaries.
    """
    from wakfu_server.rift_native_gameplay import policy, apply_native_carrier

    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None:
        return False
    state = fight.rift_wave_state
    ids = tuple(actor_ids)
    if (
        fight.phase != "active"
        or not ids
        or len(ids) > 6
        or any(type(uid) is not int for uid in ids)
        or len(set(ids)) != len(ids)
        or set(ids) != set(company_actor_ids(fight))
    ):
        raise ValueError("Rift compensation requires the complete admitted company")
    settings = document.get("compensation")
    if (
        not isinstance(settings, Mapping)
        or settings.get("native_state") != 6808
        or settings.get("grade_policy") != GRADE_POLICY
    ):
        raise ValueError("Missing explicit original company-compensation policy")
    kind = state["catalog"]["type"]
    grades = settings.get(
        "ultimate_grade_by_company_size"
        if kind == "ULTIMATE_INFINITE_WAVE"
        else "classic_grade_by_company_size"
    )
    if (
        not isinstance(grades, Mapping)
        or set(grades) != {str(n) for n in range(1, 7)}
        or any(
            type(grade) is not int or not 0 <= grade <= 4 for grade in grades.values()
        )
        or grades["5"] != 0
        or grades["6"] != 0
    ):
        raise ValueError(
            "Compensation grades require explicit native/custom company scope"
        )
    grade = grades[str(len(ids))]
    receipt = dict(
        policy=GRADE_POLICY,
        reference=6808,
        level=grade,
        company_ids=sorted(ids),
        company_size=len(ids),
        rift_type=kind,
    )
    previous = state.get("native_company_compensation")
    if previous is not None:
        if previous != receipt:
            raise ValueError("Rift compensation replay changed the original company")
        return False
    if (
        state.get("pending_wave") is not None
        or state["wave"] != state["policy"]["starting_wave"]
    ):
        raise ValueError("Rift compensation must originate at company entry")
    definition = dispatcher.native_state_handler.catalog["states"].get("6808")
    if definition is None or definition.get("maximum_level") != 4:
        raise ValueError("Missing original four-grade compensation state6808")
    if grade:
        for actor_id in ids:
            apply_native_carrier(
                dispatcher, actor_id=actor_id, reference=6808, grade=grade
            )
    state["native_company_compensation"] = receipt
    return bool(grade)
