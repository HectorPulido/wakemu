"""Bounded native support intents for advisory candidate generation only."""
from collections.abc import Mapping

from ..native.native_deadline import check

MAX_NODES = 128
MAX_EMPTY_AIMS = 12


def _benefit(tags):
    good = bool({"heal", "buff", "armor"}.intersection(tags))
    bad = bool({"damage", "control", "debuff"}.intersection(tags))
    if "unknown" in tags or good == bad:
        return "unknown"
    return "beneficial" if good else "harmful"


def _stat_benefit(name, operation, amount):
    # Only named, monotone combat characteristics establish a benefit. Native
    # characteristic numbers remain data, never guessed Dofus properties.
    useful = name in {
        "AP",
        "MP",
        "WP",
        "HP",
        "RANGE",
        "DMG_IN_PERCENT",
        "CRITICAL_HIT",
        "LOCK",
        "DODGE",
        "ARMOR",
    } or (
        isinstance(name, str)
        and name.startswith(("RES_", "DMG_"))
        and "RECEIVED" not in name
    )
    if not useful or amount < 0:
        return "unknown"
    return "beneficial" if operation == "gain_current" else "harmful"


def _facts(fight, actor, context, actors):
    native = getattr(context, "actors", {}).get("caster")
    characteristics = getattr(native, "characteristics", None) or {}
    leadership = characteristics.get("LEADERSHIP")
    count = getattr(native, "summon_count", None)
    counts = getattr(native, "summon_counts_by_breed", None)
    return dict(
        leadership=leadership if type(leadership) is int else None,
        summonCount=count if type(count) is int else None,
        summonCountsByBreed={str(key): value for key, value in counts.items()}
        if isinstance(counts, Mapping)
        else None,
        summonCountsComplete=getattr(native, "summon_counts_complete", False) is True,
        # Observed ownership is not a uniqueness restriction or weighted cap.
        ownedLiving=[
            dict(
                id=row["id"],
                reference=row.get("monsterRef", 0),
                level=row.get("level", 0),
            )
            for row in actors
            if row.get("hp", 0) > 0
            and row.get("registeredSummon") is True
            and row.get("summonerId") == actor.id
        ],
    )


def state_increases(
    fight, actors, catalog, reference, requested_level, *, request_cache=None
):
    """Use the actual native pure application plan for existing state carriers."""
    from wakfu_server.combat_state_application import (
        existing_state_from_definition,
        plan_state_application,
    )

    cache_key = "state_increases", reference, requested_level
    if request_cache is not None and cache_key in request_cache:
        cached = request_cache[cache_key]
        return dict(increaseOn=list(cached[0]), increaseTo=dict(cached[1]))
    definition = catalog.get("states", {}).get(str(reference))
    increases = {}
    if not isinstance(definition, Mapping):
        return dict(increaseOn=[], increaseTo={})
    for observed in actors:
        check()
        target = getattr(fight, "actors", {}).get(observed["id"])
        ledger = getattr(target, "state_ledger", None)
        entries = [
            entry
            for entry in getattr(ledger, "entries", ())
            if entry.reference == reference
        ]
        if not entries:
            continue
        try:
            policies = [
                existing_state_from_definition(
                    dict(
                        maximum_level=definition["maximum_level"],
                        additive=definition["additive"],
                        replace=definition["replace"],
                        refresh=definition["refresh"],
                        protected=definition["protected"]
                        if entry.protected is None
                        else entry.protected,
                    ),
                    entry.level,
                )
                for entry in entries
            ]
            plan = plan_state_application(
                requested_level, definition["maximum_level"], policies
            )
            if plan.accepted and plan.level > sum(entry.level for entry in entries):
                increases[str(observed["id"])] = plan.level
        except (AttributeError, KeyError, TypeError, ValueError):
            # Missing actual instance flags cannot prove increased benefit.
            continue
    identities = [int(identity) for identity in increases]
    if request_cache is not None:
        request_cache[cache_key] = tuple(identities), tuple(increases.items())
    return dict(increaseOn=identities, increaseTo=increases)


def empty_aim_cells(fight, actor, indices, actors):
    """Bounded empty aims; a sole exit for an ally receives a soft penalty."""
    occupied = {row["cell"] for row in actors if row.get("hp", 0) > 0}
    for row in actors:
        if row.get("hp", 0) > 0:
            occupied.update(row.get("extraCells", ()))
    cells = tuple(indices)
    adjacency = {}
    for start, end in getattr(fight, "edges", ()) or ():
        a, b = indices.get(tuple(start)), indices.get(tuple(end))
        if a is not None and b is not None:
            adjacency.setdefault(a, set()).add(b)
    origin = indices[tuple(actor.position)]
    own = next((row for row in actors if row["id"] == actor.id), None)
    if own is None:
        return []
    team = own["team"]
    enemies = [
        row["cell"] for row in actors if row.get("hp", 0) > 0 and row["team"] != team
    ]
    reserved = set()
    for row in actors:
        if row.get("hp", 0) <= 0 or row["team"] != team or row["id"] == actor.id:
            continue
        free = adjacency.get(row["cell"], set()) - occupied
        if len(free) == 1:
            reserved.update(free)

    def distance(a, b):
        return abs(cells[a][0] - cells[b][0]) + abs(cells[a][1] - cells[b][1])

    available = [index for index in indices.values() if index not in occupied]
    near = sorted(
        available, key=lambda cell: (cell in reserved, distance(origin, cell), cell)
    )
    forward = sorted(
        available,
        key=lambda cell: (
            cell in reserved,
            min((distance(cell, enemy) for enemy in enemies), default=0),
            distance(origin, cell),
            cell,
        ),
    )
    result = []
    # Keep both near-caster and useful forward candidates rather than filling
    # the limit with distant cells that no current casting origin can reach.
    for group in (near[: MAX_EMPTY_AIMS // 2], forward, near):
        for cell in group:
            if cell not in result:
                result.append(cell)
                if len(result) >= MAX_EMPTY_AIMS:
                    return result
    return result


def project_support(
    compiled,
    roots,
    level,
    *,
    fight,
    actor,
    rule=None,
    context=None,
    indices=None,
    actors=(),
    request_cache=None
):
    """Read the owned native closure; never construct a hypothetical creature.

    Conditional groups and state consequences retain uncertainty. These facts
    cannot authorize a cast, assert a summon capacity, or mutate native state.
    """
    from wakfu_server.combat_ai_capabilities import classify_roots
    from wakfu_server.combat_ai_capability_projection import selected_state_roots
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_effect_resolver import variant_accepts
    from wakfu_server.combat_effect_targets import native_selector_policy
    from .jondo_area import area_projection
    from .jondo_native_amount import (
        project_native_amount,
        protect_health_geometry,
        source_binding_proof,
        health_eligibility_proof,
        legacy_heal_fallback,
    )
    from wakfu_server.combat_static_catalogs import characteristic_registry
    from wakfu_server.combat_current_stat_parameters import stat_parameters
    from wakfu_server.combat_damage_contracts import HEAL_ELEMENTS
    from wakfu_server.combat_summon import summon_specification
    from wakfu_server.combat_state_parameters import interpret_state_parameters
    from wakfu_server.combat_state_decurse_parameters import state_decurse_parameters
    from wakfu_server.monsters import reference as monster_reference

    registry = characteristic_registry().get("effects", {})
    effects, summons, unknown, intents, aims = [], [], set(), set(), set()
    global_self_effect = False
    pending = [(reference, level, False, 100.0, None, None) for reference in roots]
    seen = set()
    classification_budget = MAX_NODES
    source_bindings = source_binding_proof(compiled.effects, roots, level)
    health_eligibility = health_eligibility_proof(
        compiled.effects, roots, level, source_bindings
    )

    def state_consequences(selected, state_level):
        nonlocal classification_budget
        limit = min(32, classification_budget)
        if limit <= 0:
            unknown.add("state_consequence_node_limit")
            return ["unknown"]
        classification_budget -= limit
        return classify_roots(
            selected,
            compiled.source_states.get("effects", {}),
            states=compiled.source_states,
            registry=registry,
            level=state_level,
            max_nodes=limit,
        )["tags"]

    while pending and len(seen) < MAX_NODES:
        check()
        reference, current_level, inherited, chance, state, value_basis = pending.pop()
        identity = reference, current_level, state
        if identity in seen:
            continue
        seen.add(identity)
        effect = compiled.effects.get(str(reference))
        if effect is None and state is not None:
            effect = compiled.source_states.get("effects", {}).get(str(reference))
        if not isinstance(effect, Mapping):
            unknown.add("missing_effect:" + str(reference))
            continue
        if (
            not effect.get("minimum_level", -32768)
            <= current_level
            <= effect.get("maximum_level", 32767)
        ):
            continue
        if not variant_accepts(effect, "EFFECTS_ONLY"):
            continue
        family = effect.get("effect_class")
        conditional = inherited or bool(effect.get("criteria")) or family in (349, 865)
        source_binding = state is None and source_bindings.get(reference, False)
        try:
            profile = effect_profile(effect, current_level)
            probability = (
                min(100.0, max(0.0, float(profile["probability"]))) * chance / 100.0
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            unknown.add("unknown_effect_profile:" + str(reference))
            profile, probability, conditional = None, chance, True
        if probability <= 0:
            continue
        pending.extend(
            (
                child,
                current_level,
                conditional,
                probability,
                state,
                "native_runner_callback"
                if family == 865 and index == 1
                else value_basis,
            )
            for index, child in enumerate(effect.get("children", ()))
        )
        try:
            policy = native_selector_policy(effect)
            targets = sorted(policy["relations"])
            in_area = policy["in_area"]
        except (ValueError, KeyError, TypeError):
            unknown.add("unknown_selector:" + str(reference))
            targets, conditional, in_area = [], True, None
        masks = effect.get("target_masks", ())
        # Channel6 is a produced-event mask; removal-only index2 does not
        # postpone a fresh state child. Match NativeStateHandler installation.
        triggered = any(masks[index] for index in (0, 1, 3, 4, 5) if index < len(masks))
        try:
            area = area_projection(effect)
        except (ValueError, KeyError, TypeError):
            # Unknown shape never falls through to a guessed point recipient.
            area, conditional = dict(fixedCells=[]), True
        common = dict(
            nativeReference=reference,
            targets=targets,
            probability=probability,
            conditional=conditional,
            confidence="conditional" if conditional or probability < 100 else "known",
            fromState=state is not None,
            triggered=triggered,
        )
        if type(in_area) is bool:
            common["inArea"] = in_area
        common.update(area)
        if state is not None:
            common["stateContainer"] = state
        if family in HEAL_ELEMENTS:
            global_self_effect |= in_area is False and "self" in targets
            intents.add("heal")
            aims.update(set(targets).intersection(("self", "ally")))
        if profile is None:
            continue
        try:
            if family == 307:
                parameters = profile["parameters"]
                if not parameters or type(parameters[0]) is not int:
                    raise ValueError("unknown_summon_reference")
                target_reference = ((parameters[0] + 32768) % 65536) - 32768
                native = monster_reference(target_reference)
                spec = summon_specification(
                    effect,
                    profile,
                    evaluation_level=current_level,
                    container_present=True,
                    caster_level=actor.effective_level,
                    caster_team=next(
                        (row["team"] for row in actors if row["id"] == actor.id),
                        actor.team,
                    ),
                    caster_direction=actor.direction,
                    native_minimum_level=native["min_level"],
                )
                friendly = spec.team == next(
                    (row["team"] for row in actors if row["id"] == actor.id), actor.team
                )
                summons.append(
                    dict(
                        reference=spec.reference,
                        level=spec.level,
                        team=spec.team,
                        selfControlled=spec.self_controlled,
                        friendly=friendly,
                        benefit="beneficial" if friendly else "harmful",
                        **common
                    )
                )
                intents.add("summon")
                aims.add("emptyCell")
            elif family in HEAL_ELEMENTS:
                amount_projection = project_native_amount(
                    effect, current_level, source_binding_known=source_binding
                )
                if legacy_heal_fallback(
                    effect,
                    amount_projection,
                    source_known=source_binding,
                    conditional=conditional,
                    eligibility=state is None
                    and health_eligibility.get(reference, False),
                ):
                    # The original support branch supplied intent, not a numeric effect.
                    continue
                healing_common = {
                    key: value for key, value in common.items() if key not in area
                }
                healing_common.update(protect_health_geometry(area, in_area))
                healing_common["inArea"] = True
                if not source_binding:
                    healing_common.update(conditional=True, confidence="conditional")
                    unknown.add("native_source_binding_unproven:" + str(reference))
                if state is None and health_eligibility.get(reference):
                    healing_common["nativeHealthEligibility"] = dict(
                        version=1, targetNotCarried=True
                    )
                effects.append(
                    dict(
                        kind="heal",
                        benefit="beneficial",
                        **amount_projection,
                        **healing_common
                    )
                )
            elif family == 304:
                if value_basis is not None:
                    raise ValueError("state_requires_native_runner_callback")
                parsed = interpret_state_parameters(profile["parameters"])
                state_roots = selected_state_roots(
                    compiled.source_states, parsed["reference"], parsed["level"]
                )
                consequence = state_consequences(state_roots, parsed["level"])
                effects.append(
                    dict(
                        kind="add_state",
                        stateId=parsed["reference"],
                        stateLevel=parsed["level"],
                        benefit=_benefit(consequence),
                        consequences=consequence,
                        **state_increases(
                            fight,
                            actors,
                            compiled.source_states,
                            parsed["reference"],
                            parsed["level"],
                            request_cache=request_cache,
                        ),
                        **common
                    )
                )
                global_self_effect |= in_area is False and "self" in targets
                intents.add("state")
                aims.update(targets)
                # State-owned callbacks describe consequences, not extra
                # direct casts or cast-aim choices for this owned spell.
            elif family == 321:
                parameters = state_decurse_parameters(effect, profile)
                reference_to_remove = parameters[0]
                if reference_to_remove <= 0:
                    raise ValueError("decurse_requires_specific_native_state")
                present = [
                    (row["id"], entry["level"])
                    for row in actors
                    for entry in row.get("states", ())
                    if entry["reference"] == reference_to_remove
                ]
                benefits = set()
                for state_level in dict.fromkeys(value for _, value in present):
                    selected = selected_state_roots(
                        compiled.source_states, reference_to_remove, state_level
                    )
                    tags = state_consequences(selected, state_level)
                    benefits.add(
                        {
                            "beneficial": "harmful",
                            "harmful": "beneficial",
                            "unknown": "unknown",
                        }[_benefit(tags)]
                    )
                effects.append(
                    dict(
                        kind="remove_state",
                        stateId=reference_to_remove,
                        amount=parameters[1] if len(parameters) > 1 else None,
                        presentOn=[identity for identity, _ in present],
                        benefit=next(iter(benefits))
                        if len(benefits) == 1
                        else "unknown",
                        **common
                    )
                )
                global_self_effect |= in_area is False and "self" in targets
                intents.add("state")
                aims.update(targets)
            else:
                metadata = registry.get(str(family), {})
                operation = metadata.get("operation")
                if operation not in ("gain_current", "lose_current"):
                    continue
                parsed = stat_parameters(
                    effect["parameters"],
                    current_level,
                    registered_stat_id=metadata.get("fixed_stat_id"),
                    percent_default=bool(metadata.get("percent_default", False)),
                    trigger_value=None,
                )
                name = metadata.get("fixed_stat_name", "")
                effects.append(
                    dict(
                        kind="stat_gain"
                        if operation == "gain_current"
                        else "stat_loss",
                        statId=parsed["stat_id"],
                        statName=name,
                        amount=parsed["requested"],
                        percent=parsed["percent"],
                        amountKnown=value_basis is None,
                        valueBasis=value_basis or "native_parameters",
                        benefit=_stat_benefit(name, operation, parsed["requested"]),
                        **common
                    )
                )
                global_self_effect |= in_area is False and "self" in targets
                intents.add("stat")
                aims.update(
                    set(targets).intersection(
                        ("self", "ally") if operation == "gain_current" else ("enemy",)
                    )
                )
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
            unknown.add(str(error))
    if pending:
        unknown.add("support_projection_node_limit")
    anchor_required = bool(
        global_self_effect and rule is not None and rule.get("minimum", 0) > 0
    )
    if anchor_required:
        aims.add("emptyCell")
    if rule is not None:
        if rule.get("free_cell") and intents:
            aims.add("emptyCell")
        if rule.get("maximum", 1) <= 0:
            aims = {"self"} if aims or intents else set()
        elif rule.get("allow_self") is False:
            aims.discard("self")
    candidates = []
    if "emptyCell" in aims and indices is not None:
        if request_cache is not None:
            if "empty_aim_cells" not in request_cache:
                request_cache["empty_aim_cells"] = tuple(
                    empty_aim_cells(fight, actor, indices, actors)
                )
            candidates = list(request_cache["empty_aim_cells"])
        else:
            candidates = empty_aim_cells(fight, actor, indices, actors)
    return dict(
        version=1,
        aimKinds=sorted(aims),
        intents=sorted(intents),
        castAnchorRequired=anchor_required,
        effects=effects,
        summons=summons,
        unknown=sorted(unknown),
        facts=_facts(fight, actor, context, actors),
        candidateCells=candidates,
    )
