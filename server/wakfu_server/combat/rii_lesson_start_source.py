"""Admitted dojo START participant binding observed in the official capture.

The original sack installs 8003 on the hero; its fight-start replay uses the
hero as caster. This supplies the caller participant without inventing a Qe.
"""

ROOTS = frozenset((361178, 361206, 361215, 367105, 367266, 367288))


def start_caster(fight, source, *, entry, original):
    from .combat_event_replay import NativeExternalEvent
    from .rii_lesson_spellbook import lesson_contract

    if (
        not isinstance(source, NativeExternalEvent)
        or source.event_ids != (1003,)
        or source.channel != 61
        or original.reference not in ROOTS
    ):
        return None
    contract = lesson_contract(fight)
    if not isinstance(contract, dict) or contract.get("native_lesson") is not True:
        return None
    owner = contract.get("owner")
    if (
        source.manager_actor_id != owner
        or entry.manager_id != owner
        or original.target_id != owner
    ):
        return None
    actor = fight.actors.get(owner)
    if actor is None or actor.controlled is not True:
        raise ValueError("Rii START has no owned hero")
    carrier = next(
        (
            state
            for state in actor.state_ledger.entries
            if state.uid == original.state_uid
        ),
        None,
    )
    targets = contract.get("targets", [contract.get("target")])
    if (
        carrier is None
        or carrier.reference != 8003
        or carrier.level != 1
        or carrier.caster_id != original.caster_id
        or original.caster_id not in targets
        or entry.generic_effect != original.reference
    ):
        raise ValueError("Rii START differs from its captured carrier ownership")
    return owner


def permits_movement_marker_population(fight, effect, invocation):
    """Allow the admitted marker program to select its state-qualified sack."""
    if invocation.reference != 409652:
        return False
    contract = getattr(fight, "rii_movement_lesson_contract", None)
    if not isinstance(contract, dict) or contract.get("native_lesson") is not True:
        return False
    owner = contract.get("owner")
    actor = fight.actors.get(owner)
    carrier = (
        next(
            (
                state
                for state in actor.state_ledger.entries
                if state.uid == invocation.state_uid
            ),
            None,
        )
        if actor is not None
        else None
    )
    if (
        invocation.caster_id != owner
        or invocation.target_id != owner
        or carrier is None
        or carrier.reference != 8003
        or carrier.caster_id != contract.get("target")
    ):
        return False
    if (
        effect.get("effect_class") != 330
        or effect.get("parameter_count") != 0
        or tuple(effect.get("parameters", ())) != ()
        or effect.get("criteria") != 'HasState(8011, "target")'
        or effect.get("area_class") != "anD"
        or effect.get("native_target_selector") != {"class": "fcE", "mask": 1 << 47}
    ):
        raise ValueError("Rii marker population differs from its native program")
    return (
        invocation.wakemu_fresh_child_selection is True
        and invocation.native_preselected_target is False
        and invocation.native_explicit_target is True
        and invocation.native_trigger_context is None
    )


def permits_lesson_floor_retirement(fight, effect, invocation):
    """Select area managers for a bound native lesson's retirement leaf.

    Distance swaps its red/green rings. LOS removes the preceding obstacle
    generation before creating its replacement in the same native program.
    Both leaves must enumerate Qq candidates rather than inherit a sack PV.
    """
    rules = {
        367122: (
            "rii_distance_lesson_contract",
            7922,
            "target",
            "IsSpecificArea(1102) or IsSpecificArea(1103)",
            "anA",
            1 << 51,
        ),
        367125: (
            "rii_distance_lesson_contract",
            7922,
            "target",
            "IsSpecificArea(1102) or IsSpecificArea(1103)",
            "anA",
            1 << 51,
        ),
        367610: (
            "rii_los_lesson_contract",
            8003,
            "owner",
            "IsSpecificArea(1808)",
            "anD",
            0,
        ),
    }
    rule = rules.get(invocation.reference)
    if rule is None:
        return False
    attribute, state_reference, manager_role, criteria, area_class, mask = rule
    contract = getattr(fight, attribute, None)
    if not isinstance(contract, dict) or contract.get("native_lesson") is not True:
        return False
    manager = fight.actors.get(contract.get(manager_role))
    carrier = (
        next(
            (
                state
                for state in manager.state_ledger.entries
                if state.uid == invocation.state_uid
            ),
            None,
        )
        if manager is not None
        else None
    )
    if (
        carrier is None
        or carrier.reference != state_reference
        or carrier.caster_id != contract.get("target")
        or invocation.caster_id != contract.get("owner")
        or invocation.target_id != contract.get("target")
    ):
        return False
    if (
        effect.get("effect_class") != 843
        or tuple(effect.get("parameters", ())) != (-1.0, 0.0)
        or effect.get("criteria") != criteria
        or effect.get("area_class") != area_class
        or effect.get("native_target_selector") != {"class": "fcE", "mask": mask}
    ):
        raise ValueError("Rii floor retirement differs from its native program")
    return (
        invocation.wakemu_fresh_child_selection is True
        and invocation.native_preselected_target is False
        and invocation.native_explicit_target is True
    )


# Keep existing callers compatible while the policy now covers both lessons.
permits_distance_floor_retirement = permits_lesson_floor_retirement
