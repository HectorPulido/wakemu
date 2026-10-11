"""Utility of authoritative outcome deltas, independent of spell IDs/rules."""

import math


def evaluate(
    root,
    state,
    actor_id,
    weights,
    team,
    feature_weights=None,
    *,
    summon_value=1,
):
    if (
        type(summon_value) not in (int, float)
        or not math.isfinite(summon_value)
        or not 0 <= summon_value <= 1
    ):
        raise ValueError("Invalid registered summon value")
    friendly = root["actors"][actor_id]["team"]
    values = dict.fromkeys(weights, 0.0)
    victims, healed, killed = [], [], []
    for identity, before in root["actors"].items():
        after = state["actors"].get(identity)
        # Removed actors must be retained as zero HP in the native forecast.
        if after is None:
            raise ValueError("Forecast omitted existing actor")
        ally = before["team"] == friendly
        hostile_summon_value = (
            summon_value if not ally and before.get("registeredSummon") is True else 1
        )
        hp_delta = after["hp"] - before["hp"]
        if ally:
            values["healing"] += hp_delta
            if hp_delta > 0:
                healed.append((hp_delta, identity))
        else:
            values["damage"] -= hp_delta * hostile_summon_value
            if hp_delta < 0:
                damage_value = -hp_delta * hostile_summon_value
                if damage_value > 0:
                    victims.append((damage_value, identity))
        values["armor"] += (after["armor"] - before["armor"]) * (
            1 if ally else -hostile_summon_value
        )
        if before["hp"] > 0 and after["hp"] == 0:
            if ally:
                values["kills"] -= 1
            else:
                # The default value preserves historical kill utility. A
                # discounted summon receives no separate finish bonus; its
                # scaled damage already rewards the useful outcome.
                kill_value = (
                    0
                    if before.get("registeredSummon") is True and summon_value < 1
                    else 1
                )
                values["kills"] += kill_value
                if kill_value > 0:
                    killed.append((kill_value, identity))
        resource_delta = sum(after[k] - before[k] for k in ("ap", "mp", "wp"))
        values["resources" if ally else "control"] += resource_delta * (
            1 if ally else -hostile_summon_value
        )
    # Only certified registrations create reinforcement utility. Resources of
    # a new actor are not recovered caster resources, and existing summons
    # must not earn their deployment value again on later turns.
    if "reinforcements" in values:
        for identity, actor in state["actors"].items():
            if (
                identity not in root["actors"]
                and actor.get("registeredSummon") is True
                and actor["hp"] > 0
            ):
                values["reinforcements"] += actor["hp"] * (
                    1 if actor["team"] == friendly else -1
                )
    values["threat"] = root["threat"] - state["threat"]
    values["position"] = state["position"] - root["position"]
    values["uncertainty"] = root["uncertainty"] - state["uncertainty"]
    focus = team.get("focusId")
    if focus is not None:
        values["coordination"] += next(
            (damage * 0.05 for damage, i in victims if i == focus), 0
        )
    # JSON transports positions as lists; actor metrics use tuples. Keep the
    # native XYZ identity rather than silently losing reservations in v3.
    reserved = {tuple(cell) for cell in team.get("reservedCells", [])}
    reserved_xy = {cell[:2] for cell in reserved}

    def occupying_reserved(actor):
        if actor.get("blocksNativeLos") is False:
            return False
        footprint = actor.get("blockingFootprint")
        if footprint is not None:
            return bool({tuple(cell) for cell in footprint} & reserved_xy)
        return actor["position"] in reserved

    values["coordination"] += 5 * (
        int(occupying_reserved(root["actors"][actor_id]))
        - int(occupying_reserved(state["actors"][actor_id]))
    )
    components = {k: round(v * weights[k], 6) for k, v in values.items()}
    for name, weight in (feature_weights or {}).items():
        # World supplies cumulative outcome measurements relative to a common
        # reference. Subtract root to avoid rewarding pre-existing conditions.
        delta = state.get("features", {}).get(name, 0) - root.get("features", {}).get(
            name, 0
        )
        components["feature:" + name] = round(delta * weight, 6)
    target = (
        min(killed, key=lambda item: (-item[0], item[1]))[1]
        if killed
        else sorted(victims or healed, key=lambda p: (-p[0], p[1]))[0][1]
        if victims or healed
        else None
    )
    intent = (
        "finish"
        if killed
        else "damage"
        if victims
        else "heal"
        if healed
        else "protect"
        if values["armor"] > 0 or values.get("reinforcements", 0) > 0
        else "control"
        if values["control"] > 0
        else "retreat"
        if state["threat"] < root["threat"]
        else "position"
    )
    return sum(components.values()), components, intent, target
