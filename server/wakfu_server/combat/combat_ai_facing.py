"""Cheap defensive NPC facing, separate from movement and cast authority.

Certified personal damage forecasts win when available. Otherwise offensive
characteristics provide a relative heuristic, not a simulated legal attack.
No catalogs, opponent clones or extra native projections are loaded here.
"""
import math

from .combat_effective_control import effective_affiliation, effective_server_controlled


def choose(fight, actor, evidence=None):
    if (
        fight.actors.get(actor.id) is not actor
        or actor.hp <= 0
        or not fight._in_play(actor)
    ):
        return None
    evidence = evidence if isinstance(evidence, dict) else {}
    visible = evidence.get("visibleActorIds")
    visible = (
        {value for value in visible if type(value) is int}
        if isinstance(visible, list)
        else None
    )
    snapshots = {
        row["id"]: row
        for row in evidence.get("actors", [])
        if isinstance(row, dict) and type(row.get("id")) is int
    }
    forecasts = {
        row["actorId"]: row
        for row in evidence.get("rivals", [])
        if isinstance(row, dict) and type(row.get("actorId")) is int
    }
    incoming = {}
    # A fixed recent ledger window bounds fallback work on long encounters.
    for event in fight.events[-256:]:
        if event.get("kind") == "damage" and event.get("target_id") == actor.id:
            source, amount = event.get("source_id"), event.get("amount")
            if type(source) is int and type(amount) is int and amount > 0:
                incoming[source] = max(incoming.get(source, 0), amount)
    own_team = effective_affiliation(fight, actor)
    rows = []
    for rival in fight.actors.values():
        if rival.id == actor.id or rival.hp <= 0 or not fight._in_play(rival):
            continue
        affiliation = effective_affiliation(fight, rival)
        if (
            affiliation == own_team
            or affiliation < 0
            or visible is not None
            and rival.id not in visible
            or visible is None
            and hasattr(fight, "native_global_pv_collections")
            and getattr(rival, "native_fight_properties", None) is None
            or {5, 18}.intersection(getattr(rival, "native_fight_properties", ()) or ())
        ):
            continue
        dx, dy = (rival.position[i] - actor.position[i] for i in range(2))
        if dx == dy == 0:
            continue
        distance = abs(dx) + abs(dy)
        forecast = forecasts.get(rival.id, {})
        # End callbacks may move either actor. Old positional forecasts then
        # cease to describe this defensive decision; use fresh native stats.
        same_positions = all(
            identity in snapshots
            and tuple(snapshots[identity].get("position", ()))
            == tuple(current.position)
            for identity, current in ((actor.id, actor), (rival.id, rival))
        )
        hp = forecast.get("actorHpLoss", 0) if same_positions else 0
        armor = forecast.get("actorArmorLoss", 0) if same_positions else 0
        valid_losses = all(
            type(value) in (int, float) and math.isfinite(value)
            for value in (hp, armor)
        )
        personal = (
            forecast.get("actorLoss", max(0, hp) + max(0, armor))
            if same_positions and valid_losses
            else 0
        )
        certified = (
            max(0, personal)
            if all(
                type(value) in (int, float) and math.isfinite(value)
                for value in (hp, armor, personal)
            )
            else 0
        )
        lethal = same_positions and forecast.get("actorLethal") is True
        stats = rival.effect_stats if isinstance(rival.effect_stats, dict) else {}
        own_stats = actor.effect_stats if isinstance(actor.effect_stats, dict) else {}
        maxima = getattr(rival, "effect_maxima", None)
        ap = (
            maxima.get(2, getattr(rival, "max_ap", None))
            if isinstance(maxima, dict)
            else getattr(rival, "max_ap", None)
        )
        mp = (
            maxima.get(3, getattr(rival, "max_mp", None))
            if isinstance(maxima, dict)
            else getattr(rival, "max_mp", None)
        )
        missing = []
        if type(ap) is not int:
            missing.append("next_turn_ap")
        if type(mp) is not int:
            missing.append("next_turn_mp")
        if type(stats.get(20)) is not int:
            missing.append("general_mastery")
        if not all(type(stats.get(key)) is int for key in (9, 52)):
            missing.append("critical_mastery_contribution")
        elemental = [
            (stats[key], resistance)
            for key, resistance in ((21, 28), (22, 29), (23, 30), (24, 31))
            if type(stats.get(key)) is int
        ]
        if not elemental and type(stats.get(20)) is not int:
            missing.append("offensive_mastery")
        potential = 0.0
        if type(ap) is int and (elemental or type(stats.get(20)) is int):
            factors = []
            for mastery, resistance in elemental or [(0, None)]:
                mastery += stats.get(20, 0)
                # Only known critical mastery is averaged; unknown critical
                # base spell branches are not replaced with an invented bonus.
                if type(stats.get(9)) is int and type(stats.get(52)) is int:
                    mastery += max(0, min(100, stats[9])) * stats[52] / 100
                factor = max(0, 1 + mastery / 100)
                if type(stats.get(48)) is int:
                    factor *= (100 + max(-50, stats[48])) / 100
                else:
                    missing.append("final_damage")
                if resistance is not None and all(
                    type(own_stats.get(key)) is int for key in (27, resistance)
                ):
                    # Relative resistance discount only: keep this fallback
                    # independent of equipment/catalog imports and native
                    # damage execution. Clamp numerical extremes explicitly.
                    points = own_stats[27] + own_stats[resistance]
                    factor *= max(0.1, math.pow(0.8, max(-100, min(100, points / 100))))
                else:
                    missing.append("elemental_resistance")
                factors.append(factor)
            # Relative offense per AP, discounted by fresh approach distance.
            # Spell reach, LOS and base damage remain explicitly unproven.
            gap = max(0, distance - (max(0, mp) if type(mp) is int else 0) - 1)
            potential = max(0, ap) * max(factors) / (1 + gap)
        rows.append(
            dict(
                targetId=rival.id,
                certifiedLoss=certified,
                certifiedLethal=lethal,
                offensivePotential=potential,
                observedIncoming=incoming.get(rival.id, 0),
                distance=distance,
                unknownDependencies=sorted(
                    set(missing + ["fallback_spell_base_range_los_unverified"])
                ),
            )
        )
    if not rows:
        return None
    selected = max(
        rows,
        key=lambda row: (
            row["certifiedLethal"],
            row["certifiedLoss"] > 0,
            row["certifiedLoss"],
            row["offensivePotential"],
            row["observedIncoming"],
            -row["distance"],
            -row["targetId"],
        ),
    )
    selected["basis"] = (
        "certified_native_personal_loss"
        if selected["certifiedLoss"] > 0
        else "native_offensive_characteristics_heuristic"
        if selected["offensivePotential"] > 0
        else "observed_damage_and_proximity_fallback"
    )
    return selected


def apply(runtime, actor, evidence=None):
    """Publish a voluntary cardinal turn after end effects, before turn ACK."""
    from .combat_displacement_geometry import cardinal_vector
    from .combat_carrying import set_registered_direction
    from .combat_orientation import response

    if not effective_server_controlled(runtime.fight, actor):
        return []
    selected = choose(runtime.fight, actor, evidence)
    if selected is None:
        return []
    rival = runtime.fight.actors[selected["targetId"]]
    vector = cardinal_vector(
        rival.position[0] - actor.position[0], rival.position[1] - actor.position[1]
    )
    direction = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}.get(vector)
    if direction is None or direction == actor.direction:
        return []
    action = runtime.action_id + 1
    packet = response(runtime.fight.id, action, actor.id, direction)
    set_registered_direction(runtime.fight, actor, direction)
    runtime.action_id = action
    runtime.fight._event(
        "orientation",
        actor_id=actor.id,
        direction=direction,
        cost_ap=0,
        cost_mp=0,
        defensive_facing=selected,
    )
    return [packet, runtime._flush()]
