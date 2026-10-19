"""Contextual team positioning; topology is advice, never native legality.

Holding a cell is useful only when it prevents a living rival from reaching
melee contact with an ally this turn. This deliberately does not claim that
occupancy stops ranged attacks or predicts the rival's intended target.
"""
from collections import deque

from ..native.native_deadline import check


def _reachable(adjacency, origin, blocked, budget):
    reached, queue = {origin}, deque([(origin, 0)])
    while queue:
        check()
        cell, distance = queue.popleft()
        if distance >= budget:
            continue
        for end in adjacency.get(cell, ()):
            if end not in reached and end not in blocked:
                reached.add(end)
                queue.append((end, distance + 1))
    return reached


def decide(
    actors,
    actor_id,
    adjacency,
    *,
    after_attack=True,
    capability_records=None,
    attacked_targets=()
):
    """Return a fresh team assignment from this exact forecast's roster.

    The 35% effective-health reserve is a bounded heuristic, not a damage
    forecast. Certified rival response scoring remains authoritative evidence
    about danger; being healthy never grants immunity or forces an action.
    """
    actor = actors[actor_id]
    result = dict(
        mode="approach", reason="attack_not_yet_performed", protectedAllyIds=[]
    )
    result["riskBasis"] = "effective_health_reserve_and_melee_topology_heuristic"
    if not after_attack:
        return result
    effective_hp = actor["hp"] + max(0, actor.get("armor", 0))
    enemies = [
        other
        for other in actors.values()
        if other["team"] != actor["team"] and other["hp"] > 0
    ]
    primary = [other for other in enemies if other.get("registeredSummon") is not True]
    origin = tuple(actor["position"])
    # Actual damage against a surviving primary opponent preserves existing
    # hit-and-run behavior at range without treating range hints as legality.
    approach_without_contact = (
        adjacency is not None
        and actor["hp"] > 0
        and effective_hp >= max(1, actor["max_hp"] * 0.35)
        and enemies
        and not any(other["id"] in attacked_targets for other in primary or enemies)
        and not any(
            tuple(other["position"]) in adjacency.get(origin, ())
            or origin in adjacency.get(tuple(other["position"]), ())
            for other in primary or enemies
        )
    )
    # An attack on a disposable summon does not imply primary enemy contact.
    # Still inspect useful protection before choosing this approach fallback.
    result.update(
        mode="approach" if approach_without_contact else "retreat",
        reason=(
            "surviving_primary_opponent_not_in_contact"
            if approach_without_contact
            else "no_living_allies"
        ),
    )
    allies = [
        other
        for other in actors.values()
        if other["id"] != actor_id
        and other["team"] == actor["team"]
        and other["hp"] > 0
    ]
    if not allies:
        return result
    if actor["hp"] <= 0 or effective_hp < max(1, actor["max_hp"] * 0.35):
        return dict(result, reason="insufficient_effective_health")
    if adjacency is None:
        return dict(result, reason="unknown_protection_topology")
    if any(
        len(other.get("blockingFootprint") or ()) > 1
        for other in actors.values()
        if other["hp"] > 0
    ):
        # Exported footprints describe LOS blocking, not the exact native
        # movement collider. Do not manufacture a tank assignment from them.
        return dict(result, reason="multi_cell_protection_requires_native_risk")
    origin = tuple(actor["position"])
    occupied = {
        tuple(other["position"]) for other in actors.values() if other["hp"] > 0
    }
    protected = set()
    for enemy in actors.values():
        if enemy["hp"] <= 0 or enemy["team"] == actor["team"]:
            continue
        start = tuple(enemy["position"])
        # Only a defender actually in contact can be assigned to hold melee.
        if origin not in adjacency.get(start, ()):
            continue
        budget = max(0, enemy.get("mp", 0))
        blocked = occupied - {start}
        held = _reachable(adjacency, start, blocked, budget)
        vacated = _reachable(adjacency, start, blocked - {origin}, budget)
        for ally in allies:
            target = tuple(ally["position"])
            # Inspect only bounded reach, not the entire terrain per ally.
            if any(target in adjacency.get(cell, ()) for cell in vacated) and not any(
                target in adjacency.get(cell, ()) for cell in held
            ):
                protected.add(ally["id"])
    if protected:
        from .actor_roles import actor_role_profile

        profiles = {
            identity: actor_role_profile(
                {"actors": actors}, identity, capability_records=capability_records
            )
            for identity, other in actors.items()
            if other["hp"] > 0 and other["team"] == actor["team"]
        }
        protected_value = max(
            profiles[identity]["protection_value"] for identity in protected
        )
        # Holding contact is the tank contribution itself, not a competing
        # action whose usefulness makes tanking an opportunity cost.
        own_value = max(
            (
                value
                for role, value in profiles[actor_id]["role_utilities"].items()
                if role != "tank"
            ),
            default=0.0,
        )
        # A hybrid gains no bonus merely from extra labels. The strongest
        # current contribution sets value; healing has no fixed priority.
        return dict(
            result,
            mode="hold",
            reason="protect_reachable_allies",
            protectedAllyIds=sorted(protected),
            protectedAllyRoles={
                identity: profiles[identity] for identity in sorted(protected)
            },
            defenderRoles=profiles[actor_id],
            roleUtility=dict(
                protected=protected_value,
                defender=own_value,
                basis="current_resource_team_demand_heuristic",
            ),
            holdPreference=2.0 + 0.5 * (protected_value - own_value),
        )
    return dict(
        result,
        reason=(
            "surviving_primary_opponent_not_in_contact"
            if approach_without_contact
            else "holding_does_not_protect_allies"
        ),
    )


def apply_position(
    metrics,
    actor_id,
    adjacency,
    *,
    after_attack,
    allow_approach=True,
    attacked_targets=()
):
    """Apply a small positional preference without overriding native outcomes."""
    posture = decide(
        metrics["actors"],
        actor_id,
        adjacency,
        after_attack=after_attack,
        capability_records=metrics.get("actorRepertoires"),
        attacked_targets=attacked_targets,
    )
    if after_attack and not allow_approach and posture["mode"] == "approach":
        # Compare escape alternatives to a root contact/hold posture using
        # the same retreat objective. Reconsider approach on the next decision.
        posture = dict(posture, mode="retreat", reason="root_contact_escape")
    if posture["mode"] == "hold":
        # Above the bounded retreat distance bonus (1.5), below meaningful
        # damage/healing/rival losses. Never rewards a useless healthy blocker.
        metrics["position"] = posture["holdPreference"]
    elif posture["mode"] == "approach":
        metrics["position"] = metrics.get("approachPosition", metrics["position"])
    elif posture["mode"] == "retreat":
        # Callers compute metrics in retreat mode when after_attack is true.
        pass
    metrics["teamPosture"] = posture
    return posture


def contradicted_hold(actors, actor_id, posture, risk):
    """Remove hold preference when existing native previews contradict it.

    Rival projections have limited coverage. Missing evidence must not be
    presented as a guarantee of survival or protection from ranged spells.
    """
    if posture["mode"] != "hold":
        return None
    if risk.get("observedActorHpLoss", 0) >= actors[actor_id]["hp"]:
        return "native_response_exposes_lethal_damage"
    losses = risk.get("observedAllyHpLoss", {})
    if any(
        losses.get(identity, losses.get(str(identity), 0)) > 0
        for identity in posture["protectedAllyIds"]
    ):
        return "native_response_reaches_protected_ally"
    return None
