"""Native rival-response queries, generated exclusively by AI.

All rivals are represented. Failed projections remain unknown, rather than
being reported as zero danger. Independent responses are a risk estimate,
not a jointly executable sequence of future initiative turns.
"""
from ..context.native_context import NativeGraph
from ..context.native_graph_parts import load_graph
from .threat import estimate
from .query_identity import identity as state_identity
import time


def forecast(
    state,
    actor_id,
    store,
    weights,
    *,
    nodes=12,
    depth=2,
    beam=4,
    deadline=None,
    clock=time.monotonic
):
    from .query_search import candidates

    if any(type(value) is not int or value < 1 for value in (nodes, depth, beam)):
        raise ValueError("Invalid rival response search limits")
    source = {actor["id"]: actor for actor in state["actors"]}
    friendly = source[actor_id]["team"]
    rivals = sorted(
        (
            actor["id"]
            for actor in source.values()
            if actor["team"] != friendly and actor["hp"] > 0
        ),
        key=lambda identity: (
            source[identity].get("registeredSummon") is True,
            identity,
        ),
    )
    forecasts, details, sequence = [], [], 0
    observed_actor_hp_loss = 0
    observed_ally_hp_loss = {}

    def request(operation, key, **fields):
        nonlocal sequence
        sequence += 1
        return dict(
            id="risk:" + state["key"] + ":" + str(sequence),
            operation=operation,
            state=key,
            **fields
        )

    def response(answer, query, unknown):
        if (
            not isinstance(answer, dict)
            or answer.get("id") != query["id"]
            or type(answer.get("supported")) is not bool
        ):
            raise ValueError("Invalid native rival response")
        if not answer["supported"]:
            unknown.update(
                answer.get("unknownDependencies", ["native_rival_query_unsupported"])
            )
            return None
        return answer["result"]

    for rival in rivals:
        unknown = set()
        if deadline is not None and clock() >= deadline:
            details.append(
                dict(
                    actorId=rival,
                    risk=None,
                    complete=False,
                    unknownDependencies=["rival_search_deadline_reached"],
                    expanded=0,
                )
            )
            continue
        query = request("project_turn", state["key"], actorId=rival)
        projected = response((yield query), query, unknown)
        if projected is None:
            details.append(
                dict(
                    actorId=rival,
                    risk=None,
                    complete=False,
                    unknownDependencies=sorted(unknown),
                    expanded=0,
                )
            )
            continue
        unknown.update(projected.get("unknownDependencies", []))
        # Lifecycle deltas remain part of the response relative to the source.
        frontier = [(projected, [], frozenset({state_identity(projected)}))]
        projected_actors = {actor["id"]: actor for actor in projected["actors"]}
        if not set(source) <= set(projected_actors):
            raise ValueError("Native rival projection omitted existing actor")
        outcomes, expanded = [("project_turn", projected_actors)], 0
        ended = None
        if deadline is None or clock() < deadline:
            query = request("preview", projected["key"], action={"type": "end_turn"})
            ended = response((yield query), query, unknown)
        if ended is not None:
            ended_actors = {actor["id"]: actor for actor in ended["actors"]}
            if not set(source) <= set(ended_actors):
                raise ValueError("Native rival end-turn omitted existing actor")
            outcomes.append(("end_turn", ended_actors))
        for ply in range(depth):
            following = []
            for current, actions, visited in frontier:
                if expanded >= nodes or deadline is not None and clock() >= deadline:
                    break
                query = request("repertoire", current["key"], actorId=rival)
                metadata = response((yield query), query, unknown)
                if metadata is None:
                    continue
                graph = load_graph(store, metadata["nativeMetadata"])
                repertoire = graph.plain(graph.data["root"])
                graph = load_graph(store, current["nativeContext"])
                for action in candidates(graph, current, repertoire, rival):
                    if (
                        expanded >= nodes
                        or deadline is not None
                        and clock() >= deadline
                    ):
                        break
                    expanded += 1
                    query = request("preview", current["key"], action=action)
                    outcome = response((yield query), query, unknown)
                    if outcome is None or state_identity(outcome) in visited:
                        continue
                    actors = {actor["id"]: actor for actor in outcome["actors"]}
                    if not set(source) <= set(actors):
                        raise ValueError("Native rival response omitted existing actor")
                    plan = actions + [action]
                    outcomes.append((str(len(outcomes)), actors))
                    forecast_entry = dict(
                        actorId=rival,
                        mode="approximate",
                        unknownDependencies=sorted(unknown),
                        outcomes=[("candidate", actors)],
                        unsupportedPlans=0,
                    )
                    score, _ = estimate(source, actor_id, [forecast_entry], weights)
                    if (
                        outcome["phase"] == "active"
                        and outcome["currentId"] == rival
                        and actors[rival]["hp"] > 0
                    ):
                        following.append(
                            (score, outcome, plan, visited | {state_identity(outcome)})
                        )
            following.sort(
                key=lambda entry: (-entry[0], len(entry[2]), entry[1]["key"])
            )
            frontier, seen = [], set()
            for _, current, actions, visited in following:
                if state_identity(current) not in seen:
                    seen.add(state_identity(current))
                    if len(frontier) < beam:
                        frontier.append((current, actions, visited))
                    else:
                        unknown.add("rival_response_beam_pruned")
            # Certified outcomes remain useful lower bounds. A live response
            # at the horizon is not evidence that its remaining actions are
            # harmless; report this limit just like node/time exhaustion.
            if frontier and ply + 1 == depth:
                unknown.add("rival_response_depth_exhausted")
            if not frontier or expanded >= nodes:
                break
        if expanded >= nodes:
            unknown.add("rival_candidate_budget_exhausted")
        if deadline is not None and clock() >= deadline:
            unknown.add("rival_search_deadline_reached")
        if not outcomes:
            unknown.add("no_certified_rival_response")
        entry = dict(
            actorId=rival,
            mode="approximate" if unknown else "native",
            unknownDependencies=sorted(unknown),
            outcomes=outcomes,
            unsupportedPlans=0,
        )
        forecasts.append(entry)
        # Sum independent per-rival worst HP losses as a conservative danger
        # budget, not evidence of a jointly executable lethal sequence.
        # Native outcomes already include armor and damage mitigation.
        for identity, original in source.items():
            if original["team"] != friendly:
                continue
            loss = max(
                (
                    max(0, original["hp"] - outcome[identity]["hp"])
                    for _, outcome in outcomes
                ),
                default=0,
            )
            if identity == actor_id:
                observed_actor_hp_loss += loss
            else:
                observed_ally_hp_loss[identity] = (
                    observed_ally_hp_loss.get(identity, 0) + loss
                )
        risk, trace = estimate(source, actor_id, [entry], weights)
        details.append(
            dict(
                trace[0],
                actorHpLoss=max(
                    (
                        max(0, source[actor_id]["hp"] - outcome[actor_id]["hp"])
                        for _, outcome in outcomes
                    ),
                    default=0,
                ),
                actorArmorLoss=max(
                    (
                        max(0, source[actor_id]["armor"] - outcome[actor_id]["armor"])
                        for _, outcome in outcomes
                    ),
                    default=0,
                ),
                actorLoss=max(
                    (
                        max(0, source[actor_id]["hp"] - outcome[actor_id]["hp"])
                        + max(0, source[actor_id]["armor"] - outcome[actor_id]["armor"])
                        for _, outcome in outcomes
                    ),
                    default=0,
                ),
                actorLethal=any(
                    outcome[actor_id]["hp"] <= 0 for _, outcome in outcomes
                ),
                risk=risk if outcomes else None,
                complete=bool(outcomes) and not unknown,
                expanded=expanded,
                knownLowerBound=risk,
            )
        )
    total, _ = estimate(source, actor_id, forecasts, weights)
    complete = all(detail["complete"] for detail in details)
    return dict(
        risk=total if complete else None,
        knownLowerBound=total,
        complete=complete,
        observedActorHpLoss=observed_actor_hp_loss,
        observedAllyHpLoss=observed_ally_hp_loss,
        rivals=details,
        unknownDependencies=sorted(
            {reason for detail in details for reason in detail["unknownDependencies"]}
        ),
    )
