"""Rank bounded, world-certified rival responses without spell simulation.

Alternatives for one rival share an initial projection and are mutually
exclusive. Different rivals are projected independently; their sum is a risk
estimate, not a jointly executable future combat state.
"""


def validate_forecasts(raw, source, actor_id, cells, edges, helpers, budget):
    actors, action, text = helpers
    if not isinstance(raw, list) or len(raw) > 16:
        raise ValueError("Invalid rival forecasts")
    result, seen = [], set()
    friendly = source[actor_id]["team"]

    def count_roster(value):
        if not isinstance(value, list):
            raise ValueError("Invalid rival forecast roster")
        budget["actors"] += len(value)
        if budget["actors"] > 8192:
            raise ValueError("Too many rival forecast actor records")

    def roster(value):
        parsed = actors(value, cells)
        if set(parsed) != set(source):
            raise ValueError("Rival forecast changed roster identities")
        for identity, before in source.items():
            after = parsed[identity]
            if any(after[k] != before[k] for k in ("team", "controlled")):
                raise ValueError("Rival forecast changed ownership")
        return parsed

    for rival in raw:
        if not isinstance(rival, dict) or set(rival) - {
            "actorId",
            "mode",
            "unknownDependencies",
            "rootActors",
            "plans",
        }:
            raise ValueError("Invalid rival forecast fields")
        identity = rival.get("actorId")
        if (
            type(identity) is not int
            or identity not in source
            or identity in seen
            or source[identity]["hp"] <= 0
            or source[identity]["team"] == friendly
        ):
            raise ValueError("Invalid rival forecast actor")
        seen.add(identity)
        mode = rival.get("mode")
        if mode not in ("native", "approximate"):
            raise ValueError("Invalid rival projection mode")
        unknown = rival.get("unknownDependencies", [])
        if (
            not isinstance(unknown, list)
            or len(unknown) > 32
            or any(
                not isinstance(item, str) or not 1 <= len(item) <= 512
                for item in unknown
            )
            or mode == "approximate"
            and not unknown
        ):
            raise ValueError("Invalid rival projection dependencies")
        if "rootActors" in rival:
            count_roster(rival["rootActors"])
            initial = roster(rival["rootActors"])
        else:
            initial = source
        if initial[identity]["hp"] <= 0:
            raise ValueError("Dead projected rival cannot act")
        plans = rival.get("plans")
        if not isinstance(plans, list) or len(plans) > 16:
            raise ValueError("Invalid rival response plans")
        outcomes, ids, unsupported = [], set(), 0
        for plan in plans:
            if not isinstance(plan, dict) or set(plan) != {"id", "supported", "steps"}:
                raise ValueError("Invalid rival response plan")
            plan_id = text(plan.get("id"), "rival plan ID")
            if plan_id in ids:
                raise ValueError("Duplicate rival response plan")
            ids.add(plan_id)
            if type(plan.get("supported")) is not bool:
                raise ValueError("Missing rival response support evidence")
            steps = plan.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 16:
                raise ValueError("Invalid rival response steps")
            budget["steps"] += len(steps)
            if budget["steps"] > 512:
                raise ValueError("Too many rival response steps")
            for step in steps:
                if not isinstance(step, dict) or set(step) != {"action", "actors"}:
                    raise ValueError("Invalid rival response step")
                count_roster(step["actors"])
            if not plan["supported"]:
                unsupported += 1
                continue
            before = initial
            for index, step in enumerate(steps):
                if before[identity]["hp"] <= 0:
                    raise ValueError("Dead rival has outgoing action")
                after = roster(step["actors"])
                typed = action(step["action"], before, after, identity, cells, edges)
                if typed["type"] == "end_turn" and index != len(steps) - 1:
                    raise ValueError("Rival response continued after end_turn")
                before = after
            outcomes.append((plan_id, before))
        result.append(
            dict(
                actorId=identity,
                mode=mode,
                unknownDependencies=list(unknown),
                outcomes=outcomes,
                unsupportedPlans=unsupported,
            )
        )
    return result


def estimate(source, actor_id, forecasts, weights):
    friendly = source[actor_id]["team"]
    total, details = 0.0, []
    for rival in forecasts:
        best, selected = 0.0, None
        for plan_id, outcome in sorted(rival["outcomes"]):
            loss = 0.0
            for identity, before in source.items():
                after = outcome[identity]
                ally = before["team"] == friendly
                sign = 1 if ally else -1
                hp_loss = (before["hp"] - after["hp"]) * sign
                loss += hp_loss * weights["healing" if ally else "damage"]
                loss += (before["armor"] - after["armor"]) * sign * weights["armor"]
                if before["hp"] > 0 and after["hp"] == 0:
                    loss += sign * weights["kills"]
                if ally:
                    loss += (
                        sum(before[k] - after[k] for k in ("ap", "mp", "wp"))
                        * weights["control"]
                    )
            if loss > best:
                best, selected = loss, plan_id
        total += best
        details.append(
            dict(
                actorId=rival["actorId"],
                mode=rival["mode"],
                unknownDependencies=rival["unknownDependencies"],
                planId=selected,
                risk=round(best, 6),
                unsupportedPlans=rival["unsupportedPlans"],
            )
        )
    return total, details
