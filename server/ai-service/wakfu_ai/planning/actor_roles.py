"""Composable tactical roles from actor-bound advisory spell metadata.

A resource-usable role means exported AP/MP/WP costs fit this snapshot. It
never certifies native targeting, conditions, extra-resource costs or legality.
Unknown costs retain explicit uncertainty; estimated utility is discounted.
Allied healing/protection still requires recipient evidence.
"""
from collections.abc import Mapping


def _roles(hint):
    tags = set(hint.get("tags", ()))
    roles = set()
    if tags & {"heal", "healing"}:
        roles.add("healer")
    if "damage" in tags:
        minimum, maximum = hint.get("minimum"), hint.get("maximum")
        if type(minimum) is int and type(maximum) is int and 0 <= minimum <= maximum:
            if minimum <= 1:
                roles.add("damage_melee")
            if maximum >= 2:
                roles.add("damage_ranged")
    if tags & {"armor", "protection"}:
        roles.add("protector")
    if tags & {"control", "debuff", "displacement"}:
        roles.add("controller")
    if tags & {"summon", "summoning"}:
        roles.add("summoner")
    return roles


def _cost_options(spell):
    """Read compact bridge records or existing full repertoire responses."""
    options = spell.get("costOptions")
    if options is not None:
        if (
            not isinstance(options, list)
            or not options
            or type(spell.get("conditionalCosts", False)) is not bool
        ):
            return None
        if any(
            not isinstance(row, Mapping)
            or any(
                type(row.get(key)) is not int or row[key] < 0
                for key in ("ap", "mp", "wp")
            )
            for row in options
        ):
            return None
        return [dict(row) for row in options]
    casting, level = spell.get("casting"), spell.get("level")
    if not isinstance(casting, Mapping) or type(level) is not int or level <= 0:
        return None
    # A level-zero full table needs separate native authority, not row one.
    index = level - 1
    tables = [casting] + list(casting.get("conditional", ()))
    result = []
    for table_index, table in enumerate(tables):
        if not isinstance(table, Mapping):
            return None
        costs = table.get("costs" if table_index == 0 else "levels")
        if not isinstance(costs, (list, tuple)) or index >= len(costs):
            return None
        row = costs[index]
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            return None
        if any(type(value) is not int or value < 0 for value in row):
            return None
        result.append(dict(zip(("ap", "mp", "wp"), row)))
    return result


def actor_role_profile(state, actor_id, capability_records=None):
    """Recompute intrinsic, resource-usable and useful roles for one forecast.

    No species IDs, role hierarchy, native queries or mutation are involved.
    Useful roles express present tactical demand, not an executable action.
    An exhausted healer retains its intrinsic role; full allies remove its
    healing demand. Conditional or incomplete metadata discounts utility.
    """
    roster = state.get("actors", ())
    actors = (
        roster
        if isinstance(roster, Mapping)
        else {
            row["id"]: row for row in roster if isinstance(row, Mapping) and "id" in row
        }
    )
    actor = actors.get(actor_id)
    result = dict(
        intrinsic_roles=[],
        usable_roles=[],
        useful_roles=[],
        evidence=[],
        data_gaps=[],
        cast_legality_verified=False,
        resource_basis="exported_ap_mp_wp_costs",
        role_utilities={},
        protection_value=0.0,
        tank_capacity=False,
        usefulness_basis="bounded_contextual_estimate_not_native_legality",
    )
    if not isinstance(actor, Mapping):
        result["data_gaps"] = ["missing_actor"]
        return result
    repertoire = None
    if capability_records is None:
        capability_records = state.get("actorRepertoires")
    if isinstance(capability_records, Mapping):
        repertoire = capability_records.get(
            actor_id, capability_records.get(str(actor_id))
        )
    if repertoire is None:
        repertoire = actor.get("advisoryRepertoire")
    if not isinstance(repertoire, Mapping) or repertoire.get("actorId") != actor_id:
        result["data_gaps"] = ["missing_actor_bound_repertoire"]
        return result
    for source, target in (("key", "sourceState"), ("stateRevision", "stateRevision")):
        if (
            source in state
            and target in repertoire
            and state[source] != repertoire[target]
        ):
            result["data_gaps"] = ["stale_actor_repertoire"]
            return result
    spells = repertoire.get("spells")
    if not isinstance(spells, (list, tuple)):
        result["data_gaps"] = ["missing_spell_capabilities"]
        return result
    gaps = set(repertoire.get("unknownDependencies", ()))
    intrinsic, usable, useful = set(), set(), set()
    living = [
        row
        for row in actors.values()
        if isinstance(row, Mapping) and row.get("hp", 0) > 0
    ]
    allies = [row for row in living if row.get("team") == actor.get("team")]
    enemies = [row for row in living if row.get("team") != actor.get("team")]
    wounded = any(
        type(row.get("max_hp")) is int and row["hp"] < row["max_hp"] for row in allies
    )
    has_other_ally = any(row.get("id") != actor_id for row in allies)
    demand = {
        "healer": wounded,
        "damage_melee": bool(enemies),
        "damage_ranged": bool(enemies),
        "protector": bool(enemies) and has_other_ally,
        "controller": bool(enemies),
        "summoner": bool(enemies),
    }
    resources_known = all(
        type(actor.get(key)) is int and actor[key] >= 0 for key in ("ap", "mp", "wp")
    )
    for spell in spells:
        if not isinstance(spell, Mapping):
            gaps.add("invalid_spell_metadata")
            continue
        hint = spell.get("advisoryCapabilities")
        if (
            not isinstance(hint, Mapping)
            or hint.get("spellId") != spell.get("spellId")
            or hint.get("level") != spell.get("level")
            or not isinstance(hint.get("tags"), (list, tuple))
            or any(not isinstance(tag, str) for tag in hint["tags"])
        ):
            gaps.add("missing_spell_bound_capabilities")
            continue
        roles = _roles(hint)
        intrinsic.update(roles)
        reasons = []
        costs = _cost_options(spell)
        if not resources_known:
            reasons.append("unknown_actor_resources")
        if costs is None:
            reasons.append("unknown_spell_costs")
        affordable = False
        if resources_known and costs is not None:
            outcomes = [
                all(actor[key] >= row[key] for key in ("ap", "mp", "wp"))
                for row in costs
            ]
            affordable = any(outcomes)
            if not all(outcomes):
                reasons.append(
                    "conditional_cost_unresolved"
                    if affordable
                    else "insufficient_resources"
                )
        alive = actor.get("hp", 0) > 0
        if alive and affordable:
            usable.update(roles)
        if hint.get("conditional", False):
            reasons.append("conditional_capability")
        if hint.get("unknownDependencies") or "unknown" in hint["tags"]:
            reasons.append("unknown_capability_dependencies")
        if repertoire.get("unknownDependencies"):
            reasons.append("incomplete_repertoire_metadata")
        if spell.get("costUncertainties"):
            reasons.append("unresolved_resource_cost_metadata")
        if not alive:
            reasons.append("actor_not_alive")
        useful_here = (
            {role for role in roles if demand[role]} if alive and affordable else set()
        )
        if "healer" in useful_here and hint.get("allyTarget") is not True:
            useful_here.remove("healer")
            reasons.append("unknown_allied_heal_targeting")
        if "protector" in useful_here and hint.get("allyTarget") is not True:
            useful_here.remove("protector")
            reasons.append("unknown_allied_protection_targeting")
        eligible_heal_deficits = [
            max(0.0, min(1.0, (row["max_hp"] - row["hp"]) / row["max_hp"]))
            for row in allies
            if type(row.get("max_hp")) is int
            and row["max_hp"] > 0
            and (row.get("id") != actor_id or hint.get("selfTarget") is True)
        ]
        healing_demand = min(1.0, sum(eligible_heal_deficits))
        if "healer" in useful_here and healing_demand <= 0:
            useful_here.remove("healer")
        if "summoner" in useful_here:
            reasons.append("summon_capacity_not_certified")
        useful.update(useful_here)
        result["evidence"].append(
            dict(
                spell_id=spell.get("spellId"),
                level=spell.get("level"),
                intrinsic_roles=sorted(roles),
                resource_affordable=affordable,
                useful_roles=sorted(useful_here),
                reasons=reasons,
                cost_basis=spell.get("costBasis", "exported_ap_mp_wp_costs"),
                healing_demand=healing_demand,
            )
        )
        gaps.update(
            reason
            for reason in reasons
            if reason not in ("insufficient_resources", "actor_not_alive")
        )
    # Capacity is a contextual estimate, not a permanent breed archetype.
    hp, maximum, armor = (
        actor.get("hp", 0),
        actor.get("max_hp", 0),
        actor.get("armor", 0),
    )
    tank_capacity = (
        type(maximum) is int
        and maximum > 0
        and type(armor) is int
        and armor > 0
        and hp > 0
        and hp + armor >= maximum * 0.35
    )
    if tank_capacity:
        usable.add("tank")
        if has_other_ally and enemies:
            useful.add("tank")
    enemy_deficit = max(
        (
            max(0.0, min(1.0, (row["max_hp"] - row["hp"]) / row["max_hp"]))
            for row in enemies
            if type(row.get("max_hp")) is int and row["max_hp"] > 0
        ),
        default=0,
    )
    demand_values = dict(
        healer=0.0,
        damage_melee=0.25 + 0.5 * enemy_deficit,
        damage_ranged=0.25 + 0.5 * enemy_deficit,
        controller=0.5 if len(enemies) > len(allies) else 0.25,
        summoner=0.5 if len(enemies) > len(allies) else 0.25,
        protector=0.25,
        tank=0.25,
    )
    utilities = {}
    for role in useful:
        rows = [row for row in result["evidence"] if role in row["useful_roles"]]
        confidence = max((0.5 if row["reasons"] else 1.0 for row in rows), default=1.0)
        if role == "healer":
            utilities[role] = round(
                max(
                    (
                        row["healing_demand"] * (0.5 if row["reasons"] else 1.0)
                        for row in rows
                    ),
                    default=0.0,
                ),
                6,
            )
        else:
            utilities[role] = round(demand_values[role] * confidence, 6)
    result.update(
        intrinsic_roles=sorted(intrinsic),
        usable_roles=sorted(usable),
        useful_roles=sorted(useful),
        data_gaps=sorted(gaps),
        role_utilities=utilities,
        protection_value=max(utilities.values(), default=0.0),
        usefulness_basis="bounded_contextual_estimate_not_native_legality",
        tank_capacity=tank_capacity,
    )
    return result
