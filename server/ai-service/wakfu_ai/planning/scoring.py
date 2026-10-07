"""Utility of authoritative outcome deltas, independent of spell IDs/rules."""


def evaluate(root, state, actor_id, weights, team, feature_weights=None):
    friendly = root["actors"][actor_id]["team"]
    values = dict.fromkeys(weights, 0.0)
    victims, healed, killed = [], [], []
    for identity, before in root["actors"].items():
        after = state["actors"].get(identity)
        # Removed actors must be retained as zero HP in the native forecast.
        if after is None:
            raise ValueError("Forecast omitted existing actor")
        ally = before["team"] == friendly
        hp_delta = after["hp"] - before["hp"]
        if ally:
            values["healing"] += hp_delta
            if hp_delta > 0:
                healed.append((hp_delta, identity))
        else:
            values["damage"] -= hp_delta
            if hp_delta < 0:
                victims.append((-hp_delta, identity))
        values["armor"] += (after["armor"] - before["armor"]) * (1 if ally else -1)
        if before["hp"] > 0 and after["hp"] == 0:
            values["kills"] += -1 if ally else 1
            if not ally:
                killed.append(identity)
        resource_delta = sum(after[k] - before[k] for k in ("ap", "mp", "wp"))
        values["resources" if ally else "control"] += resource_delta * (
            1 if ally else -1
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
        min(killed)
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
        if values["armor"] > 0
        else "control"
        if values["control"] > 0
        else "retreat"
        if state["threat"] < root["threat"]
        else "position"
    )
    return sum(components.values()), components, intent, target
