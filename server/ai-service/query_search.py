"""AI-owned search coroutine over complete snapshots and native queries.

Yielded requests run on world's encounter thread. Only certified previews
enter the search; unknown mechanics never become presumed legal actions.
"""
import time
import math
from collections import deque

if __package__:
    from .native_context import NativeGraph
    from .native_graph_parts import load_graph
    from .scoring import evaluate
    from .tactical import DEFAULT_WEIGHTS
    from .capability_evidence import observed
    from .topology_distance import directed_adjacencies, distance_field_from_reverse
    from .query_identity import identity as state_identity
    from .feature_values import validate_features
else:
    from native_context import NativeGraph
    from native_graph_parts import load_graph
    from scoring import evaluate
    from tactical import DEFAULT_WEIGHTS
    from capability_evidence import observed
    from topology_distance import directed_adjacencies, distance_field_from_reverse
    from query_identity import identity as state_identity
    from feature_values import validate_features


def _fight(graph):
    runtime = graph.field(graph.data["root"], "runtime")
    return graph.field(runtime, "fight")


_MEMO_GRAPH = object()


def _sequence(graph, reference, memo=None):
    node = graph.resolve(reference)
    if not isinstance(node, dict) or "items" not in node:
        raise ValueError("Missing complete native geometry sequence")
    # Terrain coordinates and edges share immutable tuple references. Decode
    # each such tuple once in this sequence; retain ordinary plain semantics
    # for mutable containers, scalar descriptors and native object rejection.
    if memo is None:
        memo = {}
    elif memo.setdefault(_MEMO_GRAPH, graph) is not graph:
        raise ValueError("Native geometry memo belongs to a different graph")
    visiting = set()

    def decode(reference):
        if "value" in reference:
            return reference["value"], True
        identity = reference["ref"]
        if identity in memo:
            return memo[identity], True
        value = graph.nodes[identity]
        if value["type"] != "tuple":
            return graph.plain(reference), False
        if all("value" in item for item in value["items"]):
            result = tuple(item["value"] for item in value["items"])
            memo[identity] = result
            return result, True
        if identity in visiting:
            raise ValueError("Cyclic native value requires reference navigation")
        visiting.add(identity)
        try:
            children = [decode(item) for item in value["items"]]
            result = tuple(child for child, _ in children)
            immutable = all(safe for _, safe in children)
            if immutable:
                memo[identity] = result
            return result, immutable
        finally:
            visiting.remove(identity)

    try:
        return [decode(item)[0] for item in node["items"]]
    finally:
        # The recursive closure otherwise keeps the complete graph and its
        # tuple memo alive until cyclic GC, even after this sequence returns.
        decode = None


def candidates(
    graph, state, repertoire, actor_id, capability_evidence=None, prepare=None
):
    """Order candidates; legality and effects belong exclusively to native APIs.

    All owned spells and verified cells remain eligible. Interleaving spells
    prevents one large repertoire entry from consuming the query budget.
    Movement is expanded one native directed edge at a time by the search.
    """
    actors = {actor["id"]: actor for actor in state["actors"]}
    actor = actors[actor_id]
    fight = _fight(graph)
    tuple_memo = {}

    def geometry(reference):
        operation = lambda: _sequence(graph, reference, tuple_memo)
        return operation() if prepare is None else prepare(operation)

    cells = geometry(graph.field(fight, "walkable"))
    edges_reference = graph.field(fight, "edges")
    origin = tuple(actor["position"])
    occupied = {tuple(a["position"]): a["id"] for a in actors.values() if a["hp"] > 0}

    def priority(cell):
        target = actors.get(occupied.get(tuple(cell)))
        if target is None:
            category, health = 3, 0
        elif target["team"] == actor["team"] and target["hp"] < target["max_hp"]:
            category, health = 0, target["hp"] - target["max_hp"]
        elif target["team"] != actor["team"]:
            category, health = 1, target["hp"]
        else:
            category, health = 2, 0
        return (
            category,
            health,
            abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]),
            tuple(cell),
        )

    def prepared(operation):
        return operation() if prepare is None else prepare(operation)

    targets = prepared(lambda: sorted(cells, key=priority))
    spells = prepared(
        lambda: sorted(
            repertoire["spells"], key=lambda spell: (spell["spellId"], spell["level"])
        )
    )
    cast_streams = []
    move_before_first_cast = bool(spells and targets)
    for spell in spells:
        roles = (capability_evidence or {}).get(
            (spell["spellId"], spell["level"]), set()
        )

        def relevant(cell, roles=roles):
            target = actors.get(occupied.get(tuple(cell)))
            if target is None or target["hp"] <= 0:
                return False
            ally = target["team"] == actor["team"]
            return (
                ally
                and (
                    "protection" in roles
                    or "healing" in roles
                    and target["hp"] < target["max_hp"]
                )
            ) or (not ally and bool(set(roles) & {"damage", "control"}))

        # A conservative range envelope is used only to order exploration. If
        # any stream lacks complete known metadata, keep the established
        # cast-first order. The native preview remains the only legality test.
        first_target = prepared(
            lambda: (
                next((cell for cell in targets if relevant(cell)), targets[0])
                if roles
                else (targets[0] if targets else None)
            )
        )
        ranges = prepared(lambda: _native_range_hints(spell))
        if first_target is None or ranges is None:
            move_before_first_cast = False
        elif _in_any_range(origin, first_target, ranges):
            move_before_first_cast = False

        def casts(spell=spell, roles=roles, relevant=relevant):
            # Observations order exploration only. A multi-purpose spell keeps
            # both sides eligible, including empty cells and future mechanics.
            def role_priority(cell):
                return (not relevant(cell), priority(cell))

            ordered = (
                prepared(lambda: sorted(targets, key=role_priority))
                if roles
                else targets
            )
            for cell in ordered:
                action = dict(
                    type="cast",
                    spellId=spell["spellId"],
                    level=spell["level"],
                    target=list(cell),
                )
                if tuple(cell) in occupied:
                    action["targetId"] = occupied[tuple(cell)]
                yield action

        cast_streams.append(iter(casts()))
    moves = _movement_candidates(
        graph,
        edges_reference,
        cells,
        actors,
        actor_id,
        geometry=geometry,
        prepare=prepare,
    )
    casting = deque(cast_streams)
    moving = True
    if move_before_first_cast:
        try:
            first_move = next(moves)
        except StopIteration:
            moving = False
        else:
            yield first_move
    # Rotate spells and give movement a probe between casts. Repertoire size
    # must not postpone the first movement behind every owned spell.
    while casting or moving:
        if casting:
            stream = casting.popleft()
            try:
                action = next(stream)
            except StopIteration:
                pass
            else:
                casting.append(stream)
                yield action
        if moving:
            try:
                action = next(moves)
            except StopIteration:
                moving = False
            else:
                yield action


def _native_range_hints(spell):
    """Read known native ranges as ordering hints; None means fail open."""
    casting = spell.get("casting")
    level = spell.get("level")
    known_casting = {
        "protected",
        "maximum_level",
        "line_of_sight",
        "linear",
        "free_cell",
        "levels",
        "costs",
        "categories",
        "conditional",
    }
    known_conditional = {
        "linear",
        "line_of_sight",
        "levels",
        "criteria",
        "ranges",
        "free_cell",
    }
    if (
        type(casting) is not dict
        or set(casting) - known_casting
        or type(level) is not int
        or level < 1
        or type(casting.get("levels")) is not list
        or type(casting.get("conditional")) is not list
        or level > len(casting["levels"])
    ):
        return None

    def parse_range(value, *, baseline=False):
        if (
            type(value) is not list
            or len(value) < 2
            or type(value[0]) is not int
            or type(value[1]) is not int
            or value[0] < 0
            or value[1] < value[0]
        ):
            return None
        # Baseline levels contain [min, max, effectRoots]; conditional
        # ranges are pairs. Extra baseline members are native roots, not hints.
        if not baseline and len(value) != 2:
            return None
        return value[0], value[1]

    baseline = parse_range(casting["levels"][level - 1], baseline=True)
    if baseline is None:
        return None
    ranges = [baseline]
    for conditional in casting["conditional"]:
        if (
            type(conditional) is not dict
            or set(conditional) - known_conditional
            or type(conditional.get("ranges")) is not list
            or level > len(conditional["ranges"])
        ):
            return None
        conditional_range = parse_range(conditional["ranges"][level - 1])
        if conditional_range is None:
            return None
        ranges.append(conditional_range)
    return tuple(ranges)


def _in_any_range(origin, target, ranges):
    distance = abs(origin[0] - target[0]) + abs(origin[1] - target[1])
    # Native range validation can admit XY-distance zero through a selected
    # allows-self condition, including cells at another height. Only its
    # preview knows that condition; range hints cannot rule the cast out.
    if distance == 0:
        return True
    return any(minimum <= distance <= maximum for minimum, maximum in ranges)


def _movement_candidates(
    graph, edges_reference, cells, actors, actor_id, geometry=None, prepare=None
):
    """Decode the complete movement graph only when its stream is explored."""
    decode = geometry or (lambda reference: _sequence(graph, reference))
    edges = [] if graph.resolve(edges_reference) is None else decode(edges_reference)
    operation = lambda: _movement_orders(edges, cells, actors, actor_id)
    route_orders = operation() if prepare is None else prepare(operation)

    def movement_candidates():
        seen = set()
        orders = route_orders
        while orders:
            remaining = []
            for order in orders:
                try:
                    route = next(order)
                except StopIteration:
                    continue
                remaining.append(order)
                if route not in seen:
                    seen.add(route)
                    yield dict(type="move", path=[list(cell) for cell in route])
            orders = remaining

    yield from movement_candidates()


def _movement_orders(edges, cells, actors, actor_id):
    """Prepare complete route orders; candidate exploration is timed separately.

    This fixed topology work still consumes the native turn and decision wall
    budgets. It must not consume the smaller budget for evaluating candidates.
    """
    actor = actors[actor_id]
    origin = tuple(actor["position"])
    occupied = {tuple(a["position"]): a["id"] for a in actors.values() if a["hp"] > 0}
    cell_set = set(cells)
    adjacency, reverse = directed_adjacencies(edges, cells=cell_set)
    routes, reached = [], {origin: ()}
    queue = deque([origin])
    while queue:
        start = queue.popleft()
        path = reached[start]
        if len(path) >= actor["mp"]:
            continue
        for end in sorted(adjacency.get(start, ())):
            if end in reached or end in occupied:
                continue
            route = path + (end,)
            reached[end] = route
            routes.append(route)
            queue.append(end)
    enemies = [a for a in actors.values() if a["team"] != actor["team"] and a["hp"] > 0]
    enemy_cells = {tuple(enemy["position"]) for enemy in enemies}
    approach = distance_field_from_reverse(
        reverse, enemy_cells, set(occupied) - enemy_cells - {origin}
    )

    def route_priority(route):
        end = route[-1]
        distance = min(
            (
                abs(end[0] - a["position"][0]) + abs(end[1] - a["position"][1])
                for a in enemies
            ),
            default=0,
        )
        return approach.get(end, len(cells) + 1), distance, len(route), route

    # Promote complete reachable routes without discarding their shorter
    # prefixes. One-edge expansion remains available for alternate paths;
    # callbacks, occupancy/footprints and costs are certified by the oracle.
    route_orders = [iter(sorted(routes, key=route_priority))]
    wounded = {
        tuple(other["position"])
        for other in actors.values()
        if other["id"] != actor_id
        and other["team"] == actor["team"]
        and 0 < other["hp"] < other["max_hp"]
    }
    if wounded:
        support = distance_field_from_reverse(
            reverse, wounded, set(occupied) - wounded - {origin}
        )
        route_orders.append(
            iter(
                sorted(
                    routes,
                    key=lambda route: (
                        support.get(route[-1], len(cells) + 1),
                        route_priority(route),
                    ),
                )
            )
        )
    return route_orders


def _metrics(raw, actor_id, *, unreachable_penalty=None):
    features = validate_features(
        raw.get("outcomeFeatures", {}), "outcome features", 1e9
    )
    actors = {a["id"]: dict(a, position=tuple(a["position"])) for a in raw["actors"]}
    actor = actors[actor_id]
    if actor["hp"] <= 0:
        return dict(
            actors=actors,
            position=0,
            position_basis="inactive_actor",
            threat=0,
            uncertainty=0,
            features=features,
        )
    enemies = [a for a in actors.values() if a["team"] != actor["team"] and a["hp"] > 0]
    distance = min(
        (
            abs(a["position"][0] - actor["position"][0])
            + abs(a["position"][1] - actor["position"][1])
            for a in enemies
        ),
        default=0,
    )
    position_basis = "legacy_xy_heuristic"
    if "topologyDistances" in raw:
        topology = raw["topologyDistances"]
        position_basis = (
            "unknown_topology" if topology is None else "directed_xyz_topology"
        )
        if topology is None:
            distance = 0  # Unknown topology supplies no positional advantage.
        else:
            if not isinstance(topology, dict) or str(actor_id) not in topology:
                raise ValueError("Incomplete native topology distances")
            distance = topology[str(actor_id)]
            count = raw.get("topologyCellCount")
            if type(count) is not int or count < 0:
                raise ValueError("Invalid complete native topology size")
            if distance is None:
                distance = (
                    count + 1 if unreachable_penalty is None else unreachable_penalty
                )
            elif type(distance) is not int or distance < 0:
                raise ValueError("Invalid native topology distance")
    return dict(
        actors=actors,
        position=-distance * 0.25,
        position_basis=position_basis,
        threat=0,
        uncertainty=0,
        features=features,
    )


def _team_context(envelope, policy, actors, actor_id):
    team = envelope.get("teamContext", policy.get("team", {}))
    if not isinstance(team, dict):
        raise ValueError("Invalid native team context")
    if "teamContext" in envelope and team:
        if (
            team.get("fightInstanceId") != envelope.get("fightInstanceId")
            or team.get("stateRevision") != envelope.get("stateRevision")
            or team.get("team") != actors[actor_id]["team"]
            or type(team.get("team")) is not int
            or type(team.get("stateRevision")) is not int
            or not isinstance(team.get("fightInstanceId"), str)
            or not team["fightInstanceId"]
        ):
            raise ValueError("Stale or foreign native team context")
    focus = team.get("focusId")
    if focus is not None and (
        type(focus) is not int
        or focus not in actors
        or actors[focus]["hp"] <= 0
        or actors[focus]["team"] == actors[actor_id]["team"]
    ):
        raise ValueError("Invalid native team focus")
    reserved = team.get("reservedCells", [])
    if not isinstance(reserved, (list, tuple)) or any(
        not isinstance(cell, (list, tuple))
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        for cell in reserved
    ):
        raise ValueError("Invalid native team reservations")
    return dict(team, reservedCells=[tuple(cell) for cell in reserved])


def _diverse_beam(options, limit, actor_id=None, support_reference=None):
    """Retain useful support/position branches before duplicate intents.

    This is search allocation, not a role bonus. The highest utility node is
    always first; final selection still uses certified outcome utility.
    """
    ranked = sorted(
        options, key=lambda node: (-node["score"], len(node["actions"]), node["key"])
    )
    selected, represented, seen = [], set(), set()
    preferred_support = None
    if (
        limit > 1
        and actor_id is not None
        and isinstance(support_reference, dict)
        and support_reference.get("actorId") == actor_id
        and support_reference.get("targetIds")
        and type(support_reference.get("distance")) is int
    ):
        eligible = []
        for node in ranked:
            fact = node.get("state", {}).get("nativeSupportApproach")
            if (
                node["intent"] == "position"
                and isinstance(fact, dict)
                and fact.get("actorId") == actor_id
                and fact.get("targetIds") == support_reference["targetIds"]
                and type(fact.get("distance")) is int
                and 0 <= fact["distance"] < support_reference["distance"]
            ):
                eligible.append(node)
        if eligible:
            preferred_support = min(
                eligible,
                key=lambda node: (
                    node["state"]["nativeSupportApproach"]["distance"],
                    -node["score"],
                    len(node["actions"]),
                    node["key"],
                ),
            )
    if ranked and preferred_support is not None:
        for node in (ranked[0], preferred_support):
            identity = state_identity(node.get("state", node))
            if identity not in seen:
                selected.append(node)
                represented.add((node["intent"], node["target"]))
                seen.add(identity)
        if len(selected) == limit:
            return selected
    for node in ranked:
        category = node["intent"], node["target"]
        state = node.get("state", {})
        if (
            node["intent"] == "position"
            and actor_id is not None
            and type(state.get("nativeFacingActorId")) is int
            and state["nativeFacingActorId"] == actor_id
        ):
            # Allocate exploration to different certified snapshot locators.
            # This does not reward BACK: the later cast outcome must win.
            category += (tuple(sorted(state.get("nativeFacings", {}).items())),)
        identity = state_identity(node.get("state", node))
        if identity not in seen and category not in represented:
            selected.append(node)
            represented.add(category)
            seen.add(identity)
            if len(selected) == limit:
                return selected
    for node in ranked:
        identity = state_identity(node.get("state", node))
        if identity not in seen:
            selected.append(node)
            seen.add(identity)
            if len(selected) == limit:
                break
    return selected


def _prune_frontier(frames, limit, actor_id, support_reference=None):
    """Keep the root cursor and a globally diverse bounded continuation set."""
    branches = [frame for frame in frames if frame["depth"] != 0]
    selected = _diverse_beam(
        [frame["node"] for frame in branches], limit, actor_id, support_reference
    )
    retained = {id(node) for node in selected}
    return deque(
        frame
        for frame in frames
        if frame["depth"] == 0 or id(frame["node"]) in retained
    )


def search(envelope, store, *, clock=time.monotonic, root_graph=None):
    """Yield native requests and return the best source-bound first action.

    Limits constrain search work, never the supplied native data. The caller
    sends each yielded request to NativeSession.query and resumes with its
    response. This coroutine contains no world imports or spell formulas.
    """
    actor_id, root_key = envelope["actor_id"], envelope["rootState"]
    policy = envelope.get("policy", {})
    if not isinstance(policy, dict):
        raise ValueError("Invalid native query policy")
    limits = dict(depth=4, beam=12, nodes=96, budgetMs=250, probeQuantum=2)
    limits.update(policy.get("limits", {}))
    for name, maximum in (
        ("depth", 16),
        ("beam", 64),
        ("nodes", 4096),
        ("budgetMs", 10000),
        ("probeQuantum", 64),
    ):
        if type(limits[name]) is not int or not 1 <= limits[name] <= maximum:
            raise ValueError("Invalid native query search limit: " + name)
    weights = dict(DEFAULT_WEIGHTS)
    configured_weights = policy.get("weights", {})
    if (
        not isinstance(configured_weights, dict)
        or set(configured_weights) - set(weights)
        or any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 1000
            for value in configured_weights.values()
        )
    ):
        raise ValueError("Invalid native search weights")
    weights.update(configured_weights)
    feature_weights = validate_features(
        policy.get("featureWeights", {}), "feature weights", 1000
    )
    root = _metrics(envelope["root"], actor_id)
    if root["actors"][actor_id]["hp"] <= 0:
        raise ValueError("Native search requires a live source actor")
    root_cell_count = envelope["root"].get("topologyCellCount")
    unreachable_penalty = (
        root_cell_count + 1
        if type(root_cell_count) is int and root_cell_count >= 0
        else None
    )
    team = _team_context(envelope, policy, root["actors"], actor_id)
    sequence, expanded, unsupported = 0, 0, []
    capability_evidence = {}
    unknown_feature_dependencies = set()
    for name, weight in feature_weights.items():
        if weight != 0 and name not in root["features"]:
            unknown_feature_dependencies.add("outcome_feature_missing_root:" + name)

    def evaluate_state(metrics):
        available_weights = {}
        for name, weight in feature_weights.items():
            if weight == 0:
                continue
            if name not in root["features"]:
                continue
            if name not in metrics["features"]:
                unknown_feature_dependencies.add(
                    "outcome_feature_missing_state:" + name
                )
                continue
            available_weights[name] = weight
        return evaluate(root, metrics, actor_id, weights, team, available_weights)

    # Complete snapshot/repertoire loading is mandatory context preparation,
    # separate from exploration work. Count it under the real owner deadline,
    # but do not let parsing the next full map starve its first candidate.
    # Node/depth and owner limits still constrain all work; no data is omitted.
    deadline = None
    waiting = 0.0
    preparation = 0.0
    turn_deadline = None
    decision_deadline = None
    decision_wall_budget = None
    reserve = policy.get("commitReserveMs", 500)
    if type(reserve) is not int or not 0 <= reserve <= 10000:
        raise ValueError("Invalid native commit reserve")
    time_fraction = policy.get("searchTimeFraction", 0.25)
    if (
        type(time_fraction) not in (int, float)
        or not math.isfinite(time_fraction)
        or not 0 < time_fraction <= 1
    ):
        raise ValueError("Invalid native search time fraction")

    def update_turn_budget(message):
        nonlocal turn_deadline, decision_deadline, decision_wall_budget
        if not isinstance(message, dict):
            raise ValueError("Invalid native query response")
        if "nativeBudgetMs" not in message:
            return
        value = message["nativeBudgetMs"]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid native owner budget hint")
        proposed = clock() + value / 1000
        turn_deadline = (
            proposed if turn_deadline is None else min(turn_deadline, proposed)
        )
        if decision_deadline is None:
            # A decision must leave time for its actual execution and a fresh
            # complete search after movement. This wall-clock slice includes
            # queries and preparation, and is never renewed by later hints.
            decision_wall_budget = max(0.0, value - reserve) * time_fraction
            decision_deadline = clock() + decision_wall_budget / 1000

    update_turn_budget(envelope)
    stop_reasons = []
    work_at_budget_check = 0.0

    def exhausted():
        nonlocal work_at_budget_check, stop_reasons
        now = clock()
        if deadline is not None:
            work_at_budget_check = max(
                0.0, limits["budgetMs"] + (now - deadline) * 1000
            )
        reasons = []
        if deadline is not None and now >= deadline:
            reasons.append("search_work_budget")
        if decision_deadline is not None and now >= decision_deadline:
            reasons.append("decision_wall_budget")
        if turn_deadline is not None and now >= turn_deadline - reserve / 1000:
            reasons.append("native_commit_reserve")
        if reasons and not stop_reasons:
            stop_reasons = reasons
        return bool(reasons)

    def prepare_geometry(operation):
        nonlocal deadline, preparation
        started = clock()
        try:
            return operation()
        finally:
            elapsed = max(0.0, clock() - started)
            preparation += elapsed
            if deadline is not None:
                deadline += elapsed

    def exchange(query):
        nonlocal deadline, waiting
        started = clock()
        response = yield query
        elapsed = max(0.0, clock() - started)
        waiting += elapsed
        if deadline is not None:
            deadline += elapsed
        update_turn_budget(response)
        return answer(response, query)

    def request(operation, key, **fields):
        nonlocal sequence
        sequence += 1
        return dict(id=str(sequence), operation=operation, state=key, **fields)

    def answer(response, query):
        if (
            not isinstance(response, dict)
            or response.get("id") != query["id"]
            or type(response.get("supported")) is not bool
        ):
            raise ValueError("Invalid native query response")
        if not response["supported"]:
            unsupported.extend(
                response.get("unknownDependencies", ["native_query_unsupported"])
            )
            return None
        return response["result"]

    best = dict(
        score=0,
        actions=[],
        components={},
        key=root_key,
        state=envelope["root"],
        intent="end_turn",
        target=None,
        orientationEvidence=[],
    )
    alternatives = [best]
    root_node = dict(**best, visited=frozenset({state_identity(envelope["root"])}))
    pending = deque([dict(node=root_node, depth=0, stream=None)])
    expanded_by_depth = {}
    peak_continuations = 0
    while pending and expanded < limits["nodes"] and not exhausted():
        frame = pending.popleft()
        node = frame["node"]
        if frame["stream"] is None:
            query = request("repertoire", node["key"], actorId=actor_id)
            repertoire = yield from exchange(query)
            if repertoire is None:
                continue
            preparing = clock()
            metadata = load_graph(store, repertoire["nativeMetadata"])
            repertoire = metadata.plain(metadata.data["root"])
            if node["key"] == root_key and root_graph is not None:
                if not isinstance(root_graph, NativeGraph):
                    raise ValueError("Invalid validated native root graph")
                graph = root_graph
            else:
                graph = load_graph(store, node["state"]["nativeContext"])
            frame["stream"] = iter(
                candidates(
                    graph,
                    node["state"],
                    repertoire,
                    actor_id,
                    capability_evidence,
                    prepare=prepare_geometry,
                )
            )
            prepared = max(0.0, clock() - preparing)
            preparation += prepared
            if deadline is None:
                deadline = clock() + limits["budgetMs"] / 1000
            else:
                deadline += prepared
        following = []
        finished = False
        for _ in range(limits["probeQuantum"]):
            if expanded >= limits["nodes"] or exhausted():
                break
            try:
                action = next(frame["stream"])
            except StopIteration:
                finished = True
                break
            if expanded >= limits["nodes"] or exhausted():
                break
            expanded += 1
            depth = frame["depth"] + 1
            expanded_by_depth[depth] = expanded_by_depth.get(depth, 0) + 1
            query = request("preview", node["key"], action=action)
            state = yield from exchange(query)
            if state is None or state_identity(state) in node["visited"]:
                continue
            metrics = _metrics(state, actor_id, unreachable_penalty=unreachable_penalty)
            if metrics["actors"][actor_id]["hp"] <= 0:
                metrics["position"] = root["position"]
            if action["type"] == "cast":
                before = {row["id"]: row for row in node["state"]["actors"]}
                roles = observed(before, metrics["actors"], actor_id)
                identity = action["spellId"], action["level"]
                capability_evidence.setdefault(identity, set()).update(roles)
            score, components, intent, target = evaluate_state(metrics)
            option = dict(
                score=score,
                components=components,
                key=state["key"],
                actions=node["actions"] + [action],
                state=state,
                intent=intent,
                target=target,
                orientationEvidence=node["orientationEvidence"]
                + [
                    dict(row, sourceState=node["key"], previewState=state["key"])
                    for row in state.get("damageContextEvidence", [])
                ],
                visited=node["visited"] | {state_identity(state)},
            )
            alternatives.append(option)
            if score > best["score"]:
                best = option
            if (
                frame["depth"] + 1 < limits["depth"]
                and state["phase"] == "active"
                and state["currentId"] == actor_id
                and metrics["actors"][actor_id]["hp"] > 0
            ):
                following.append(option)
        # Resume the exact remaining root/branch stream later. A small quantum
        # lets promising continuations compete before a large cell/spell set
        # consumes the native turn. Limits bound exploration, never catalogue.
        if not finished:
            pending.append(frame)
        children = _diverse_beam(
            following,
            limits["beam"],
            actor_id,
            envelope["root"].get("nativeSupportApproach"),
        )
        child_frames = [
            dict(node=child, depth=frame["depth"] + 1, stream=None)
            for child in children
        ]
        # Give newly found root continuations one immediate quantum. Deeper
        # children join the tail, so an entire DFS branch cannot starve root
        # enumeration or older continuations. Selection spans all depths.
        if frame["depth"] == 0:
            pending.extendleft(reversed(child_frames))
        else:
            pending.extend(child_frames)
        pending = _prune_frontier(
            pending,
            limits["beam"],
            actor_id,
            envelope["root"].get("nativeSupportApproach"),
        )
        peak_continuations = max(
            peak_continuations, sum(frame["depth"] != 0 for frame in pending)
        )
    risk_trace = []
    if "project_turn" in envelope.get("operations", []):
        if __package__:
            from .query_threat import forecast
        else:
            from query_threat import forecast
        risk_limits = policy.get("rivalLimits", {})
        if not isinstance(risk_limits, dict) or set(risk_limits) - {
            "nodes",
            "depth",
            "beam",
            "alternatives",
            "budgetMs",
        }:
            raise ValueError("Invalid rival search policy")
        risk_limits = {
            **dict(nodes=12, depth=2, beam=4, alternatives=6, budgetMs=500),
            **risk_limits,
        }
        for name, maximum in (
            ("nodes", 128),
            ("depth", 4),
            ("beam", 16),
            ("alternatives", 16),
            ("budgetMs", 10000),
        ):
            if (
                type(risk_limits[name]) is not int
                or not 1 <= risk_limits[name] <= maximum
            ):
                raise ValueError("Invalid rival search limit: " + name)
        unknown_penalty = policy.get("unknownRiskPenalty", 25)
        if (
            type(unknown_penalty) not in (int, float)
            or not 0 <= unknown_penalty <= 1000
        ):
            raise ValueError("Invalid unknown rival risk penalty")
        ranked = sorted(
            alternatives,
            key=lambda option: (
                -option["score"],
                len(option["actions"]),
                option["key"],
            ),
        )
        shortlist, represented, seen = (
            [alternatives[0]],
            set(),
            {state_identity(envelope["root"])},
        )
        for option in ranked:
            category = option["intent"], option["target"]
            identity = state_identity(option["state"])
            if category not in represented and identity not in seen:
                shortlist.append(option)
                seen.add(identity)
                represented.add(category)
        for option in ranked:
            identity = state_identity(option["state"])
            if identity not in seen:
                shortlist.append(option)
                seen.add(identity)
        shortlist = shortlist[: max(2, risk_limits.pop("alternatives"))]
        risk_deadline = clock() + risk_limits.pop("budgetMs") / 1000
        if turn_deadline is not None:
            risk_deadline = min(risk_deadline, turn_deadline - reserve / 1000)
        if decision_deadline is not None:
            risk_deadline = min(risk_deadline, decision_deadline)
        baseline_penalty = None
        evaluated = []
        for option in shortlist:
            risk = (
                dict(
                    risk=0,
                    knownLowerBound=0,
                    complete=True,
                    rivals=[],
                    unknownDependencies=[],
                )
                if option["state"]["phase"] != "active"
                else (
                    yield from forecast(
                        option["state"],
                        actor_id,
                        store,
                        weights,
                        deadline=risk_deadline,
                        clock=clock,
                        **risk_limits
                    )
                )
            )
            unsupported.extend(risk["unknownDependencies"])
            penalty = risk["knownLowerBound"] * weights["threat"]
            uncertainty_penalty = (
                0 if risk["complete"] else unknown_penalty * weights["uncertainty"]
            )
            if baseline_penalty is None:
                baseline_penalty = penalty + uncertainty_penalty
            adjusted = (
                option["score"] + baseline_penalty - penalty - uncertainty_penalty
            )
            assessed = dict(
                option,
                score=adjusted,
                components=dict(
                    option["components"],
                    rival_risk_baseline=baseline_penalty,
                    rival_risk_lower_bound=-penalty,
                    rival_risk_uncertainty=-uncertainty_penalty,
                ),
            )
            evaluated.append(assessed)
            risk_trace.append(
                dict(
                    state=option["key"],
                    actions=option["actions"],
                    score=adjusted,
                    forecast=risk,
                )
            )
        best = min(
            evaluated,
            key=lambda option: (
                -option["score"],
                len(option["actions"]),
                option["key"],
            ),
        )
    else:
        unsupported.append("native_rival_projection_operation_unavailable")
    selected = _metrics(
        best["state"], actor_id, unreachable_penalty=unreachable_penalty
    )
    if selected["actors"][actor_id]["hp"] <= 0:
        selected["position"] = root["position"]
    return dict(
        protocol=3,
        requestId=envelope["requestId"],
        sourceKey=envelope["sourceKey"],
        rootState=root_key,
        action=best["actions"][0] if best["actions"] else {"type": "end_turn"},
        plan=best["actions"],
        score=best["score"],
        components=best["components"],
        expanded=expanded,
        rivalForecasts=risk_trace,
        searchBudgetEvidence=dict(
            nativeWaitMs=waiting * 1000,
            stopReasons=stop_reasons,
            searchWorkMsAtLastBudgetCheck=work_at_budget_check,
            decisionWallBudgetMs=decision_wall_budget,
            searchTimeFraction=time_fraction,
            contextPreparationMs=preparation * 1000,
            commitReserveMs=reserve,
            expandedByDepth={
                str(depth): count for depth, count in sorted(expanded_by_depth.items())
            },
            peakContinuationFrames=peak_continuations,
        ),
        positionEvidence=dict(
            basis=selected["position_basis"],
            rootUtility=root["position"],
            selectedUtility=selected["position"],
        ),
        capabilityEvidence=[
            dict(
                spellId=spell,
                level=level,
                observedCapabilities=sorted(roles),
                basis="certified_native_transition",
            )
            for (spell, level), roles in sorted(capability_evidence.items())
        ],
        unknownFeatureDependencies=sorted(unknown_feature_dependencies),
        capabilitySurveyComplete=False,
        orientationEvidence=best["orientationEvidence"],
        unknownDependencies=sorted(set(unsupported)),
    )
