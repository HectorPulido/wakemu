"""Captured state carriers for explicitly admitted native Rii encounters.

Applications use the retained-effect engine so the original subscriptions and
effect trees remain authoritative.  A caller must discard its preview on error.
"""


def _participants(fight, contract, label, *, owner_is_actor=True):
    """Resolve the carriers' participants.

    The orientation lesson records the character's durable id as its owner, so
    only the bound sack has to be a live fight actor there.
    """
    owner, target = contract.get("owner"), contract.get("target")
    if (
        type(owner) is not int
        or owner <= 0
        or type(target) is not int
        or target >= 0
        or target not in fight.actors
        or (
            owner_is_actor
            and (
                owner not in fight.actors
                or fight.actors[owner].team == fight.actors[target].team
            )
        )
    ):
        raise ValueError(f"Invalid native Rii {label} state participants")
    return owner, target


def install(dispatcher):
    """Install the captured lesson carriers before fight-start events."""
    fight = dispatcher.native_retention.fight
    from wakfu_server.rift_native_gameplay import apply_native_carrier

    applied = False

    # Target carrier must precede the owner carrier: state 8003 chooses its
    # morph, resources and floor program by the target state present at start.
    lessons = (
        ("rii_element_lesson_contract", 8004),
        ("rii_distance_lesson_contract", 7922),
        ("rii_los_lesson_contract", 8005),
        ("rii_area_lesson_contract", 8007),
        ("rii_movement_lesson_contract", 8011),
        ("rii_states_lesson_contract", 8012),
    )
    active = [
        attribute
        for attribute, _state in lessons
        if isinstance(getattr(fight, attribute, None), dict)
        and (
            attribute != "rii_los_lesson_contract"
            or getattr(fight, attribute).get("native_los_areas") is True
        )
    ]
    if isinstance(getattr(fight, "rii_orientation_contract", None), dict):
        active.append("rii_orientation_contract")
    if len(active) > 1:
        raise ValueError("A fight cannot install multiple native Rii lessons")
    for attribute, state in lessons:
        contract = getattr(fight, attribute, None)
        if not isinstance(contract, dict):
            continue
        if (
            attribute == "rii_los_lesson_contract"
            and contract.get("native_los_areas") is not True
        ):
            continue
        if contract.get("native_lesson") is True:
            raise ValueError("Native Rii lesson was already installed")
        if attribute == "rii_area_lesson_contract":
            owner = contract.get("owner")
            targets = contract.get("targets")
            if (
                not isinstance(targets, list)
                or len(targets) != 4
                or len(set(targets)) != 4
            ):
                raise ValueError("Invalid native Rii area targets")
            for target in targets:
                _participants(fight, {"owner": owner, "target": target}, "area")
        else:
            owner, target = _participants(fight, contract, attribute)
            targets = [target]
        contract["native_lesson"] = True
        # Initializers called after native start must not install another deck,
        # force random state order, or move sacks using a reconstructed layout.
        contract["initialized"] = True
        contract["grant_uids"] = []
        source = targets[0]
        if attribute == "rii_area_lesson_contract":
            # Official bootstrap source -1706442036063419 is the south sack.
            source = next(
                identity
                for identity in targets
                if tuple(fight.actors[identity].position) == (0, -12, 0)
            )
        for target in targets:
            apply_native_carrier(
                dispatcher,
                actor_id=target,
                reference=state,
                grade=1,
                caster_id=source,
            )
        # The original sack applies 8003 to the hero. Its original-caster
        # selector must keep the sack identity for the movement marker branch.
        apply_native_carrier(
            dispatcher,
            actor_id=owner,
            reference=8003,
            grade=1,
            caster_id=source,
        )
        applied = True

    contract = getattr(fight, "rii_orientation_contract", None)
    if isinstance(contract, dict):
        _owner, target = _participants(
            fight, contract, "orientation", owner_is_actor=False
        )
        apply_native_carrier(dispatcher, actor_id=target, reference=7884, grade=1)
        applied = True

    return applied


def observe_damage(fight, target_id, amount):
    """Record resolved HP loss; native listeners own qualification and effects.

    Damage blocked by native resistance/state criteria never reaches this
    observer. Four genuine 25-HP reactions consume each 100-HP lesson sack.
    Area progress is the minimum across all four sacks, not a partial cast.
    """
    if type(amount) is not int or amount <= 0:
        return
    for attribute in (
        "rii_element_lesson_contract",
        "rii_distance_lesson_contract",
        "rii_los_lesson_contract",
        "rii_area_lesson_contract",
        "rii_movement_lesson_contract",
        "rii_states_lesson_contract",
    ):
        contract = getattr(fight, attribute, None)
        if not isinstance(contract, dict) or contract.get("native_lesson") is not True:
            continue
        targets = contract.get("targets", [contract.get("target")])
        if target_id not in targets:
            continue
        damage = contract.setdefault("native_resolved_damage", {})
        key = str(target_id)
        damage[key] = damage.get(key, 0) + amount
        contract["hits"] = min(
            4, min(damage.get(str(target), 0) // 25 for target in targets)
        )
