"""Bounded tactical search over world-authored, isolated native forecasts.

Inspired by Dofus bounded_turn_plans, but no foreign rules or simulators.
Every edge is a legal action certified by world for its exact source state.
"""
import math
import time

from .feature_values import DEFAULT_FEATURE_WEIGHTS, validate_features


DEFAULT_WEIGHTS = {
    "damage": 1.0,
    "healing": 1.0,
    "armor": 0.25,
    "reinforcements": 0.25,
    "kills": 25.0,
    "control": 0.5,
    "resources": 0.1,
    "threat": 1.0,
    "position": 1.0,
    "coordination": 1.0,
    "uncertainty": 1.0,
}
LIMITS = {
    "depth": (4, 16),
    "beam": (12, 64),
    "nodes": (576, 4096),
    "budgetMs": (50, 250),
    "alternatives": (6, 16),
}


def _integer(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("Invalid " + label)
    return value


def _number(value, label, lower=0, upper=1e9):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not lower <= value <= upper
    ):
        raise ValueError("Invalid " + label)
    return value


def _text(value, label):
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        raise ValueError("Invalid " + label)
    return value


def _features(raw, label, maximum):
    return validate_features(raw, label, maximum)


class ForecastAdapter:
    """Read-only source for the generic search protocol.

    Future native preview adapters can implement state(), legal_actions(),
    preview() and terminal() without changing search or spell-specific handlers.
    """

    def __init__(self, states):
        self.states = states

    def state(self, key):
        return self.states[key]

    def legal_actions(self, key):
        return self.states[key]["transitions"]

    def preview(self, key, transition):
        return transition["nextState"]

    def terminal(self, key, actor_id):
        return self.states[key]["actors"][actor_id]["hp"] <= 0


def _position(value, cells):
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(type(v) is not int for v in value)
    ):
        raise ValueError("Invalid native position")
    if tuple(value) not in cells:
        raise ValueError("Position outside native terrain")
    return tuple(value)


def _native_controller_team_change(actor, before, actors):
    """Accept only the server's actual eWD207/fdt receipt, never physical ownership."""
    row = actor.get("nativeControllerTransfer")
    expected = {
        "source",
        "producer",
        "effect_class",
        "effect_reference",
        "running_uid",
        "target_id",
        "caster_id",
        "controller_id",
        "current_team",
        "original_team",
        "original_controller",
    }
    if not isinstance(row, dict) or set(row) != expected:
        return False
    if (
        row["source"] != "fdt.a.fdy.saH_saJ_saF_ebh.v1"
        or (row["effect_class"], row["producer"])
        not in (
            (207, "eWD207.eZd.fQM.actual"),
            (1030, "eYV1030.fdy.au.actual"),
        )
        or row["target_id"] != actor["id"]
        or row["current_team"] != actor["team"]
        or type(row["effect_reference"]) is not int
        or row["effect_reference"] <= 0
        or type(row["running_uid"]) is not int
        or not 0 < row["running_uid"] < 1 << 63
        or type(row["original_team"]) is not int
        or not 0 <= row["original_team"] <= 255
        or any(
            type(row[key]) is not int
            for key in (
                "target_id",
                "caster_id",
                "controller_id",
                "original_controller",
            )
        )
        or row["caster_id"] not in actors
        or row["controller_id"] not in actors
    ):
        return False
    previous = before.get("nativeControllerTransfer")
    if previous is None:
        return row["original_team"] == before["team"]
    return (
        isinstance(previous, dict)
        and previous.get("original_team") == row["original_team"]
        and previous.get("original_controller") == row["original_controller"]
    )


def _actors(raw, cells):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
        raise ValueError("Invalid forecast roster")
    result, occupied = {}, set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Invalid forecast actor")
        identity = _integer(entry.get("id"), -(1 << 63) + 1, (1 << 63) - 1, "actor ID")
        if identity == 0 or identity in result:
            raise ValueError("Duplicate or zero actor ID")
        actor = dict(entry)
        actor["position"] = _position(entry.get("position"), cells)
        for field in ("hp", "max_hp", "armor", "ap", "mp", "wp"):
            actor[field] = _integer(entry.get(field), 0, (1 << 31) - 1, field)
        # Native maximum-HP reduction can leave a retained dead fighter at
        # zero current and maximum HP. Living fighters still require max > 0.
        if actor["hp"] > actor["max_hp"]:
            raise ValueError("Invalid forecast HP")
        actor["team"] = _integer(entry.get("team"), 0, 255, "team")
        if type(entry.get("controlled")) is not bool:
            raise ValueError("Invalid forecast control flag")
        if actor["hp"] > 0:
            if actor["position"] in occupied:
                raise ValueError("Living forecast actors overlap")
            occupied.add(actor["position"])
        result[identity] = actor
    return result


def _action(raw, before, after, actor_id, cells, edges):
    if not isinstance(raw, dict):
        raise ValueError("Invalid typed action")
    action = dict(raw)
    kind = action.get("type")
    if kind == "move":
        if set(action) != {"type", "path"}:
            raise ValueError("Invalid move action fields")
        path = action.get("path")
        if not isinstance(path, list) or not 1 <= len(path) <= before[actor_id]["mp"]:
            raise ValueError("Invalid forecast movement budget")
        previous = before[actor_id]["position"]
        occupied = {
            a["position"] for i, a in before.items() if i != actor_id and a["hp"] > 0
        }
        for raw_cell in path:
            cell = _position(raw_cell, cells)
            if (
                cell in occupied
                or (previous, cell) not in edges
                or abs(previous[0] - cell[0]) + abs(previous[1] - cell[1]) != 1
            ):
                raise ValueError("Illegal forecast movement edge")
            previous = cell
        # Reactions may change HP/resources/other actors, but an interrupted
        # path must be represented by its actually traversed prefix.
        if after[actor_id]["position"] != previous:
            raise ValueError("Forecast destination does not match path")
    elif kind == "cast":
        if set(action) - {"type", "spellId", "level", "targetId", "target"}:
            raise ValueError("Invalid cast action fields")
        _integer(action.get("spellId"), 1, (1 << 31) - 1, "spell ID")
        # Explicit native bPO morph books may own level-zero spells. World
        # certifies that exact owned level; this does not permit level-zero actors.
        _integer(action.get("level"), 0, 32767, "spell level")
        _position(action.get("target"), cells)
        target = action.get("targetId")
        if target is not None and (type(target) is not int or target not in before):
            raise ValueError("Invalid forecast cast target")
        # Range/LOS, ownership, costs, usage, facing and conditional effects
        # belong to the native preview authority, never reconstructed here.
    elif kind == "end_turn":
        if set(action) != {"type"}:
            raise ValueError("Invalid end_turn action")
    else:
        raise ValueError("Unsupported action type (no free face action)")
    return action


def validate(snapshot, base_validation):
    from .threat import validate_forecasts, estimate

    legacy = dict(snapshot, protocol=1)
    actor_id, base_actors, cells, edges = base_validation(legacy)
    for field in ("fightInstanceId", "catalogVersion", "policyVersion", "rootState"):
        _text(snapshot.get(field), field)
    for field in ("turnId", "stateRevision"):
        _integer(snapshot.get(field), 0, (1 << 63) - 1, field)
    raw_states = snapshot.get("states")
    if not isinstance(raw_states, list) or not 1 <= len(raw_states) <= 2048:
        raise ValueError("Invalid native forecast states")
    states = {}
    transitions, actor_records = 0, 0
    rival_budget = dict(steps=0, actors=0)
    for raw in raw_states:
        if not isinstance(raw, dict):
            raise ValueError("Invalid native forecast state")
        key = _text(raw.get("key"), "forecast key")
        if key in states:
            raise ValueError("Duplicate forecast state")
        actors = _actors(raw.get("actors"), cells)
        actor_records += len(actors)
        if actor_records > 32768:
            raise ValueError("Too many forecast actor records")
        if not set(base_actors) <= set(actors):
            raise ValueError("Forecast omitted existing actor")
        if actor_id not in actors:
            raise ValueError("Forecast lost current actor")
        for i, actor in actors.items():
            if i in base_actors:
                if actor["controlled"] != base_actors[i]["controlled"]:
                    raise ValueError("Forecast changed actor ownership")
                if actor["team"] != base_actors[i][
                    "team"
                ] and not _native_controller_team_change(actor, base_actors[i], actors):
                    raise ValueError("Forecast changed actor ownership")
        outgoing = raw.get("transitions", [])
        if not isinstance(outgoing, list):
            raise ValueError("Invalid forecast transitions")
        transitions += len(outgoing)
        if transitions > 8192:
            raise ValueError("Too many forecast transitions")
        states[key] = dict(
            actors=actors,
            transitions=outgoing,
            threat=_number(raw.get("threat", 0), "forecast threat"),
            position=_number(raw.get("positionValue", 0), "position value", -1e6, 1e6),
            uncertainty=_number(raw.get("uncertainty", 0), "uncertainty"),
            features=_features(raw.get("outcomeFeatures", {}), "outcome features", 1e9),
        )
        if "rivalForecasts" in raw:
            if "threat" in raw:
                raise ValueError("Ambiguous scalar and rival forecast threat")
            states[key]["rivalForecasts"] = validate_forecasts(
                raw["rivalForecasts"],
                actors,
                actor_id,
                cells,
                edges,
                (_actors, _action, _text),
                rival_budget,
            )
    root = states.get(snapshot["rootState"])
    if root is None:
        raise ValueError("Missing forecast root")
    if any("rivalForecasts" in state for state in states.values()):
        if "rivalForecasts" not in root:
            raise ValueError("Missing root rival forecasts")
        covered = {r["actorId"] for r in root["rivalForecasts"]}
        for state in states.values():
            expected = {i for i in covered if state["actors"][i]["hp"] > 0}
            actual = {r["actorId"] for r in state.get("rivalForecasts", [])}
            if "rivalForecasts" not in state or actual != expected:
                raise ValueError("Inconsistent rival forecast coverage")
    if set(root["actors"]) != set(base_actors):
        raise ValueError("Forecast root roster differs from snapshot")
    for i, actor in base_actors.items():
        if any(root["actors"][i][k] != v for k, v in actor.items()):
            raise ValueError("Forecast root differs from snapshot")
    # Extended root fields must also match the full snapshot, not just v1 DTO.
    for entry in snapshot["actors"]:
        if _actors([entry], cells)[entry["id"]] != root["actors"][entry["id"]]:
            raise ValueError("Forecast root context differs from snapshot")
    feature_weights = {}
    rejected = 0
    for key, state in states.items():
        verified, seen = [], set()
        for transition in state["transitions"]:
            if not isinstance(transition, dict):
                raise ValueError("Invalid forecast transition")
            identity = _text(transition.get("id"), "transition ID")
            if identity in seen:
                raise ValueError("Duplicate transition ID")
            seen.add(identity)
            if type(transition.get("supported")) is not bool:
                raise ValueError("Missing native support evidence")
            if not transition["supported"]:
                rejected += 1
                continue
            destination = transition.get("nextState")
            if not isinstance(destination, str) or destination not in states:
                raise ValueError("Missing forecast successor")
            action = _action(
                transition.get("action"),
                state["actors"],
                states[destination]["actors"],
                actor_id,
                cells,
                edges,
            )
            if state["actors"][actor_id]["hp"] <= 0:
                raise ValueError("Dead actor has outgoing actions")
            verified.append(dict(id=identity, action=action, nextState=destination))
        state["transitions"] = sorted(verified, key=lambda t: t["id"])
    policy = snapshot.get("policy", {})
    if not isinstance(policy, dict) or set(policy) - {
        "weights",
        "featureWeights",
        *LIMITS,
    }:
        raise ValueError("Invalid tactical policy")
    weights = dict(DEFAULT_WEIGHTS)
    overrides = policy.get("weights", {})
    if not isinstance(overrides, dict) or set(overrides) - set(weights):
        raise ValueError("Invalid tactical weights")
    for field, value in overrides.items():
        weights[field] = _number(value, "weight " + field, 0, 1000)
    for state in states.values():
        if "rivalForecasts" in state:
            state["threat"], state["rivalResponses"] = estimate(
                state["actors"], actor_id, state.pop("rivalForecasts"), weights
            )
    feature_weights = dict(DEFAULT_FEATURE_WEIGHTS)
    feature_weights.update(
        _features(policy.get("featureWeights", {}), "feature weights", 1000)
    )
    limits = {
        k: _integer(policy.get(k, default), 1, maximum, k)
        for k, (default, maximum) in LIMITS.items()
    }
    # Blackboard is an authoritative checkpoint carried by world, not local
    # mutable memory that would confuse uncommitted plans or multiple replicas.
    team = snapshot.get("teamContext", {})
    if not isinstance(team, dict):
        raise ValueError("Invalid team checkpoint")
    if team:
        _integer(team.get("stateRevision"), 0, (1 << 63) - 1, "team revision")
        _integer(team.get("team"), 0, 255, "checkpoint team")
        if (
            team.get("fightInstanceId") != snapshot["fightInstanceId"]
            or team.get("stateRevision") != snapshot["stateRevision"]
            or team.get("team") != base_actors[actor_id]["team"]
        ):
            raise ValueError("Stale or foreign team checkpoint")
        focus = team.get("focusId")
        if focus is not None and (
            type(focus) is not int
            or focus not in base_actors
            or base_actors[focus]["team"] == base_actors[actor_id]["team"]
            or base_actors[focus]["hp"] == 0
        ):
            raise ValueError("Invalid team focus")
        reserved = team.get("reservedCells", [])
        if not isinstance(reserved, list) or len(reserved) > 8192:
            raise ValueError("Invalid team reservations")
        team = dict(team, reservedCells=[_position(c, cells) for c in reserved])
    return actor_id, states, weights, limits, team, rejected, feature_weights


def decide(snapshot, base_validation):
    started = time.monotonic()
    actor_id, states, weights, limits, team, rejected, feature_weights = validate(
        snapshot, base_validation
    )
    root_key = snapshot["rootState"]
    root = states[root_key]
    from .search import bounded_search
    from .scoring import evaluate
    from .capabilities import validate_capabilities, affinities

    capabilities = validate_capabilities(snapshot.get("capabilities", []))
    search_started = time.monotonic()
    deadline = search_started + limits["budgetMs"] / 1000
    adapter = ForecastAdapter(states)
    candidates, expanded, timed_out = bounded_search(
        adapter,
        root_key,
        limits,
        deadline,
        lambda key: evaluate(
            root, adapter.state(key), actor_id, weights, team, feature_weights
        ),
        actor_id,
    )
    selected = candidates[0]
    actions = selected["actions"] or [{"type": "end_turn"}]
    alternatives, seen = [], set()
    for option in candidates:
        category = (option["intent"], option["target"])
        if category not in seen:
            seen.add(category)
            alternatives.append(
                dict(
                    intent=option["intent"],
                    target_id=option["target"],
                    score=round(option["score"], 6),
                    transitionIds=list(option["ids"]),
                )
            )
        if len(alternatives) >= limits["alternatives"]:
            break
    return dict(
        protocol=2,
        **{
            k: snapshot[k]
            for k in (
                "requestId",
                "stateKey",
                "fightInstanceId",
                "turnId",
                "stateRevision",
                "catalogVersion",
                "policyVersion",
            )
        },
        decision=dict(
            actor_id=actor_id,
            actions=actions,
            intent=selected["intent"],
            target_id=selected["target"],
            score=round(selected["score"], 6),
            score_components=selected["components"],
            transitionIds=list(selected["ids"]),
            reason="Native forecast ranking; execute first action and replan",
        ),
        trace=dict(
            expanded=expanded,
            elapsedMs=round((time.monotonic() - started) * 1000, 3),
            validationMs=round((search_started - started) * 1000, 3),
            searchMs=round((time.monotonic() - search_started) * 1000, 3),
            timedOut=timed_out,
            nodeLimitReached=expanded >= limits["nodes"],
            unsupportedTransitions=rejected,
            alternatives=alternatives,
            rivalResponses=dict(
                model="independent_best_response",
                root=root.get("rivalResponses", []),
                selected=adapter.state(selected["key"]).get("rivalResponses", []),
            ),
            roleAffinities=affinities(capabilities),
        )
    )
