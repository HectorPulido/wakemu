"""AI-owned search coroutine over complete snapshots and native queries.

Yielded requests run on world's encounter thread. Only certified previews
enter the search; unknown mechanics never become presumed legal actions.
"""
import time
import math
import json
from collections import OrderedDict, deque

from ..context.native_context import NativeGraph
from ..context.native_graph_parts import load_graph
from .scoring import evaluate
from .turn_memory import (
    attacked_this_turn,
    battleground_border_cells,
    damaged_targets_this_turn,
)
from .tactical import DEFAULT_WEIGHTS
from .capability_evidence import observed
from .topology_distance import (
    directed_adjacencies,
    immutable_directed_adjacencies,
    distance_field_from_reverse,
    minimum_exposure,
    exposure_field_from_reverse,
)
from .casting_prerequisites import (
    certified_unavailable_spell_keys,
    all_owned_spells_unavailable,
)
from ..native.native_deadline import check
from .query_identity import identity as state_identity
from .movement_routes import hazard_route_alternatives
from .attack_opportunities import attack_opportunity_routes
from .feature_values import DEFAULT_FEATURE_WEIGHTS, validate_features
from .decision_context_cache import DecisionContextCache
from .turn_continuation import recovery_proposal
from .team_posture import (
    decide as decide_team_posture,
    apply_position,
    contradicted_hold,
)


def _fight(graph):
    runtime = graph.field(graph.data["root"], "runtime")
    return graph.field(runtime, "fight")


_MEMO_GRAPH = object()


def _preview_cache_key(state, action):
    """Complete runtime identity, or an exact receipt for custom old oracles."""
    check()
    identity = state_identity(state)
    scope = "runtime" if "runtimeIdentity" in state else "receipt"
    encoded = json.dumps(
        action,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    check()
    return scope, identity, encoded


def _warm_start_actions(raw):
    """Copy bounded advisory actions; custody/freshness belongs to NativeSession.

    A malformed hint cannot invalidate normal search. Nothing returned here is
    executable until a new preview accepts it for the exact current source.
    """
    check()
    if (
        not isinstance(raw, dict)
        or set(raw) != {"schema", "actions"}
        or raw.get("schema") != "verified-turn-continuation-v1"
        or not isinstance(raw.get("actions"), list)
        or not 1 <= len(raw["actions"]) <= 3
    ):
        return []
    result = []
    for action in raw["actions"]:
        if not isinstance(action, dict):
            return []
        if action.get("type") == "move":
            path = action.get("path")
            if (
                set(action) != {"type", "path"}
                or not isinstance(path, list)
                or not 1 <= len(path) <= 32767
            ):
                return []
            copied = []
            for index, cell in enumerate(path):
                if index % 256 == 0:
                    check()
                if (
                    not isinstance(cell, list)
                    or len(cell) != 3
                    or any(type(value) is not int for value in cell)
                ):
                    return []
                copied.append(list(cell))
            check()
            result.append(dict(type="move", path=copied))
        elif action.get("type") == "cast":
            if (
                set(action) - {"type", "spellId", "level", "target", "targetId"}
                or type(action.get("spellId")) is not int
                or action["spellId"] <= 0
                or type(action.get("level")) is not int
                or action["level"] < 0
                or not isinstance(action.get("target"), list)
                or len(action["target"]) != 3
                or any(type(value) is not int for value in action["target"])
                or ("targetId" in action and type(action["targetId"]) is not int)
            ):
                return []
            result.append(dict(action, target=list(action["target"])))
        elif action.get("type") == "portal_travel":
            destination = action.get("destination")
            if (
                set(action) != {"type", "destination"}
                or not isinstance(destination, list)
                or len(destination) != 3
                or any(type(value) is not int for value in destination)
            ):
                return []
            result.append(dict(type="portal_travel", destination=list(destination)))
        else:
            return []
    check()
    return result


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


def _certified_target_bounds(repertoire, actor_id, origin):
    """Consume only native upper bounds bound to this exact caster state."""
    envelope = repertoire.get("nativeTargetEnvelope")
    if not isinstance(envelope, dict) or set(envelope) != {
        "version",
        "actorId",
        "origin",
        "metric",
        "complete",
        "maximum",
        "basis",
        "spells",
        "unrestrictedSpellIds",
        "unknownSpellIds",
    }:
        return {}
    if (
        envelope["version"] != "native-target-envelope-v1"
        or envelope["basis"] != "native-casting-range-upper-bound"
        or envelope["metric"] != "xy-manhattan"
        or envelope["actorId"] != actor_id
        or not isinstance(envelope["origin"], list)
        or len(envelope["origin"]) != 3
        or any(type(value) is not int for value in envelope["origin"])
        or envelope["origin"] != list(origin)
        or type(envelope["complete"]) is not bool
        or not isinstance(envelope["spells"], list)
    ):
        return {}
    excluded = set()
    for field in ("unknownSpellIds", "unrestrictedSpellIds"):
        values = envelope[field]
        if not isinstance(values, list) or any(
            type(value) is not int for value in values
        ):
            return {}
        excluded.update(values)
    result = {}
    seen = set()
    for row in envelope["spells"]:
        if (
            not isinstance(row, dict)
            or set(row) - {"spellId", "level", "minimum", "maximum", "source", "reason"}
            or type(row.get("spellId")) is not int
            or type(row.get("level")) is not int
        ):
            return {}
        key = row["spellId"], row["level"]
        if key in seen:
            return {}
        seen.add(key)
        if (
            row["spellId"] not in excluded
            and row.get("source") == "baseline+all-conditional-branches"
            and type(row.get("maximum")) is int
            and 0 <= row["maximum"] <= (1 << 31) - 1
        ):
            result[key] = row["maximum"]
    return result


def _within_target_bound(origin, cell, maximum):
    # The native distance uses Java int32 arithmetic. Keep all targets whose
    # wraparound behavior cannot be represented by an ordinary XY radius.
    coordinates = (*origin[:2], *cell[:2])
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in coordinates
    ):
        return True
    distance = abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
    return distance > (1 << 31) - 1 or distance <= maximum


def _cast_recipient_ids(actors):
    """Keep retained KO identities without treating them as living occupancy.

    A living fighter wins a shared cell. Otherwise every retained fighter is
    offered independently; native eligibility alone accepts or rejects revival.
    """
    result = {}
    for actor in sorted(actors.values(), key=lambda entry: entry["id"]):
        result.setdefault(tuple(actor["position"]), []).append(actor["id"])
    for cell, identities in result.items():
        living = [identity for identity in identities if actors[identity]["hp"] > 0]
        if living:
            result[cell] = living
    return result


def _portal_candidates(repertoire, state, actor_id, cells):
    """A source-bound native endpoint is advice, never a terrain edge."""
    fact = repertoire.get("nativePortalTravel")
    if (
        not isinstance(fact, dict)
        or set(fact)
        != {"schema", "sourceState", "stateRevision", "actorId", "destinations"}
        or fact.get("schema") != "native-portal-travel-v1"
        or not isinstance(fact.get("sourceState"), str)
        or not fact["sourceState"]
        or fact.get("sourceState") != state.get("key")
        or type(fact.get("stateRevision")) is not int
        or fact["stateRevision"] != state.get("stateRevision")
        or type(fact.get("actorId")) is not int
        or fact["actorId"] != actor_id
        or type(state.get("currentId")) is not int
        or state["currentId"] != actor_id
        or not isinstance(fact.get("destinations"), list)
        or not fact["destinations"]
    ):
        return
    walkable, seen = {tuple(cell) for cell in cells}, set()
    for index, cell in enumerate(fact["destinations"]):
        if index % 256 == 0:
            check()
        if (
            not isinstance(cell, list)
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
        ):
            continue
        destination = tuple(cell)
        if destination in walkable and destination not in seen:
            seen.add(destination)
            yield dict(type="portal_travel", destination=list(cell))


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
    recipients = _cast_recipient_ids(actors)

    def priority(cell):
        identities = recipients.get(tuple(cell), ())
        target = actors.get(identities[0]) if identities else None
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

    unavailable_spells = certified_unavailable_spell_keys(repertoire, state, actor_id)
    spells = prepared(
        lambda: sorted(
            (
                spell
                for spell in repertoire["spells"]
                if (spell.get("spellId"), spell.get("level")) not in unavailable_spells
            ),
            key=lambda spell: (spell["spellId"], spell["level"]),
        )
    )
    bounds = _certified_target_bounds(repertoire, actor_id, origin)
    # Retain full geometry for approach planning and native certification.
    # Only the current state's spell targets use an advisory relevance mask.
    bounded_all = bool(spells) and all(
        (spell["spellId"], spell["level"]) in bounds for spell in spells
    )
    maximum = max(bounds.values(), default=0)
    target_cells = (
        prepared(
            lambda: [
                cell for cell in cells if _within_target_bound(origin, cell, maximum)
            ]
        )
        if bounded_all
        else cells
    )
    targets = prepared(lambda: sorted(target_cells, key=priority))
    cast_streams = []
    move_before_first_cast = bool(spells and targets)
    for spell in spells:
        bound = bounds.get((spell["spellId"], spell["level"]))
        spell_targets = (
            prepared(
                lambda: [
                    cell
                    for cell in targets
                    if _within_target_bound(origin, cell, bound)
                ]
            )
            if bound is not None
            else targets
        )
        roles = (capability_evidence or {}).get(
            (spell["spellId"], spell["level"]), set()
        )
        ranges = prepared(lambda: _native_range_hints(spell))
        hint = spell.get("advisoryCapabilities")
        if (
            isinstance(hint, dict)
            and type(hint.get("spellId")) is int
            and type(hint.get("level")) is int
            and hint.get("spellId") == spell["spellId"]
            and hint.get("level") == spell["level"]
            and isinstance(hint.get("tags"), list)
            and "damage" in hint["tags"]
        ):
            # A fresh decision has no observed roles yet. An injured caster
            # must not put self-casts ahead of an adjacent enemy for a damage
            # spell and exhaust the bounded preview budget. This hint changes
            # ordering only; all recipients still require native certification.
            roles = set(roles) | {"damage"}
        summon_hint = "summoning" in roles or (
            isinstance(hint, dict)
            and hint.get("spellId") == spell["spellId"]
            and hint.get("level") == spell["level"]
            and isinstance(hint.get("tags"), list)
            and "summon" in hint["tags"]
        )

        if summon_hint and ranges is None and isinstance(hint, dict):
            # Capabilities are advisory even when newer casting metadata cannot
            # be parsed here. They order probes without excluding any target.
            minimum, maximum = hint.get("minimum"), hint.get("maximum")
            if (
                type(minimum) is int
                and type(maximum) is int
                and 0 <= minimum <= maximum
            ):
                ranges = ((minimum, maximum),)

        def range_priority(cell, ranges=ranges):
            distance = abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
            return ranges is not None and not any(
                lo <= distance <= hi for lo, hi in ranges
            )

        if summon_hint:
            # Native advisory tags order exploration only. Every recipient
            # remains eligible, including self and occupied cells, because
            # conditional or multi-purpose summons still require a preview.
            spell_targets = prepared(
                lambda: sorted(
                    spell_targets,
                    key=lambda cell: (
                        range_priority(cell),
                        tuple(cell) in occupied,
                        priority(cell),
                    ),
                )
            )

        def relevant(cell, roles=roles, summon_hint=summon_hint):
            identities = recipients.get(tuple(cell), ())
            target = actors.get(identities[0]) if identities else None
            if target is None:
                return summon_hint
            ally = target["team"] == actor["team"]
            return (
                ally
                and (
                    "protection" in roles
                    or "healing" in roles
                    and target["hp"] < target["max_hp"]
                )
            ) or (not ally and bool(set(roles) & {"damage", "control"}))

        if roles and ranges is not None and not summon_hint:
            # Among useful recipients, try current-range targets before weak
            # distant ones. Unknown-role streams retain their original order;
            # all targets, including conditional self casts, remain eligible.
            spell_targets = prepared(
                lambda: sorted(
                    spell_targets,
                    key=lambda cell: (
                        not relevant(cell),
                        range_priority(cell),
                        priority(cell),
                    ),
                )
            )

        # A conservative range envelope is used only to order exploration. If
        # any stream lacks complete known metadata, keep the established
        # cast-first order. The native preview remains the only legality test.
        first_target = prepared(
            lambda: (
                next(
                    (cell for cell in spell_targets if relevant(cell)), spell_targets[0]
                )
                if roles and spell_targets
                else (spell_targets[0] if spell_targets else None)
            )
        )
        if first_target is None or ranges is None:
            move_before_first_cast = False
        elif _in_any_range(origin, first_target, ranges):
            move_before_first_cast = False

        def casts(
            spell=spell,
            roles=roles,
            relevant=relevant,
            spell_targets=spell_targets,
            summon_hint=summon_hint,
            range_priority=range_priority,
        ):
            # Observations order exploration only. A multi-purpose spell keeps
            # both sides eligible, including empty cells and future mechanics.
            def role_priority(cell):
                if summon_hint:
                    return (range_priority(cell), not relevant(cell), priority(cell))
                return (not relevant(cell), range_priority(cell), priority(cell))

            ordered = (
                prepared(lambda: sorted(spell_targets, key=role_priority))
                if roles
                else spell_targets
            )
            for cell in ordered:
                action = dict(
                    type="cast",
                    spellId=spell["spellId"],
                    level=spell["level"],
                    target=list(cell),
                )
                identities = recipients.get(tuple(cell), ())
                if identities:
                    for target_id in identities:
                        yield dict(action, targetId=target_id)
                else:
                    yield action

        cast_streams.append(iter(casts()))
    moves = _movement_candidates(
        graph,
        edges_reference,
        cells,
        actors,
        actor_id,
        spells=spells,
        capability_evidence=capability_evidence,
        geometry=geometry,
        prepare=prepare,
    )
    ordinary_moves = moves

    def movement_stream():
        streams = deque(
            [
                iter(_portal_candidates(repertoire, state, actor_id, cells)),
                ordinary_moves,
            ]
        )
        while streams:
            stream = streams.popleft()
            try:
                action = next(stream)
            except StopIteration:
                continue
            streams.append(stream)
            yield action

    moves = movement_stream()
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
        "range_modifiable",
        "path_option",
        "diagonal",
        "linear_path",
        "allow_self",
        "forbid_QI_P",
        "cast_criterion_raw",
        "cast_criterion_native_present",
    }
    known_conditional = {
        "linear",
        "line_of_sight",
        "levels",
        "criteria",
        "ranges",
        "free_cell",
        "range_modifiable",
        "path_option",
        "diagonal",
        "linear_path",
        "allow_self",
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
    graph,
    edges_reference,
    cells,
    actors,
    actor_id,
    geometry=None,
    prepare=None,
    spells=(),
    capability_evidence=None,
):
    """Decode the complete movement graph only when its stream is explored."""
    decode = geometry or (lambda reference: _sequence(graph, reference))
    edges = [] if graph.resolve(edges_reference) is None else decode(edges_reference)
    after_attack = attacked_this_turn(graph, _fight(graph), actor_id)
    operation = lambda: _movement_orders(
        edges,
        cells,
        actors,
        actor_id,
        retreat=after_attack,
        team_posture=after_attack,
        attacked_targets=damaged_targets_this_turn(graph, _fight(graph), actor_id),
        hazard_cells=battleground_border_cells(graph, _fight(graph)),
        spells=spells,
        capability_evidence=capability_evidence,
    )
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


def _movement_orders(
    edges,
    cells,
    actors,
    actor_id,
    *,
    retreat=False,
    hazard_cells=(),
    team_posture=False,
    attacked_targets=(),
    spells=(),
    capability_evidence=None,
):
    """Prepare complete route orders; candidate exploration is timed separately.

    This fixed topology work still consumes the native turn and decision wall
    budgets. It must not consume the smaller budget for evaluating candidates.
    """
    actor = actors[actor_id]
    origin = tuple(actor["position"])
    occupied = {tuple(a["position"]): a["id"] for a in actors.values() if a["hp"] > 0}
    cell_set = set(cells)
    adjacency, reverse = immutable_directed_adjacencies(edges, cells=cell_set)
    posture_mode = None
    if team_posture:
        posture_mode = decide_team_posture(
            actors,
            actor_id,
            adjacency,
            attacked_targets=attacked_targets,
        )["mode"]
        retreat = posture_mode == "retreat"
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
    if hazard_cells:
        # Native edges can converge after different exposure costs. Preserve
        # ordinary shortest routes and also offer safer detours within MP.
        seen_routes = set(routes)
        for route in hazard_route_alternatives(
            adjacency, origin, occupied, actor["mp"], hazard_cells
        ):
            if route not in seen_routes:
                routes.append(route)
                seen_routes.add(route)
    enemies = [a for a in actors.values() if a["team"] != actor["team"] and a["hp"] > 0]
    enemy_cells = {tuple(enemy["position"]) for enemy in enemies}
    approach = distance_field_from_reverse(
        reverse, enemy_cells, set(occupied) - enemy_cells - {origin}
    )
    navigation_blocked = set(occupied) - enemy_cells - {origin}
    if not retreat and origin not in approach:
        # An allied queue can block every complete route this turn. Use the
        # terrain objective to order already reachable, occupied-safe routes;
        # this neither creates a route nor authorizes crossing an actor.
        hostile_blockers = {
            tuple(other["position"])
            for other in actors.values()
            if other["hp"] > 0 and other["team"] != actor["team"]
        } - enemy_cells
        relaxed = distance_field_from_reverse(reverse, enemy_cells, hostile_blockers)
        if origin in relaxed:
            approach = relaxed
            navigation_blocked = hostile_blockers
    exposure_field = (
        exposure_field_from_reverse(
            reverse,
            enemy_cells,
            navigation_blocked,
            hazard_cells,
        )
        if hazard_cells and not retreat
        else {}
    )

    def route_exposure(route):
        exposure = sum(cell in hazard_cells for cell in route)
        if origin in exposure_field and route[-1] in exposure_field:
            return max(0, exposure + exposure_field[route[-1]] - exposure_field[origin])
        return exposure

    def route_priority(route):
        end = route[-1]
        distance = min(
            (
                abs(end[0] - a["position"][0]) + abs(end[1] - a["position"][1])
                for a in enemies
            ),
            default=0,
        )
        exposure = route_exposure(route)
        if retreat:
            return exposure, -min(distance, 6), len(route), route
        return exposure, approach.get(end, len(cells) + 1), distance, len(route), route

    # Promote complete reachable routes without discarding their shorter
    # prefixes. Keep the ordinary nearest-threat order first, then interleave
    # one route representative for every rival. This prevents a nearby actor
    # from starving every route toward other opponents under a small search
    # budget; it does not classify or exclude any actor, and the full route
    # stream remains available for native preview.
    route_orders = [iter(sorted(routes, key=route_priority))]
    if not retreat and posture_mode != "hold":
        opportunities = attack_opportunity_routes(
            routes,
            actors,
            actor_id,
            spells,
            range_hints=_native_range_hints,
            capability_evidence=capability_evidence,
            route_priority=route_priority,
        )
        if opportunities:
            route_orders.insert(0, iter(opportunities))
    if routes and not retreat:
        for enemy in sorted(enemies, key=lambda value: value["id"]):
            check()
            target = tuple(enemy["position"])
            origin_distance = abs(origin[0] - target[0]) + abs(origin[1] - target[1])
            inspected = 0

            def representative_priority(route, target=target):
                nonlocal inspected
                if inspected % 256 == 0:
                    check()
                inspected += 1
                end = route[-1]
                distance = abs(end[0] - target[0]) + abs(end[1] - target[1])
                # If a route can close XY distance to this particular rival,
                # promote that route. Otherwise keep a deterministic closest
                # reachable representative. XY is only a shortlist tie-break;
                # route legality and final ranking remain native-certified.
                progress_rank = 0 if distance < origin_distance else 1
                return (
                    route_exposure(route),
                    progress_rank,
                    distance,
                    route_priority(route),
                )

            representative = min(routes, key=representative_priority)
            route_orders.append(iter((representative,)))
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


def _approach_topology(raw, actor_id, *, retreat=False):
    """Choose a navigation objective once; occupied paths stay authoritative."""
    if retreat or not isinstance(raw.get("topologyDistances"), dict):
        return None
    primary = raw.get("primaryTopologyDistances")
    use_primary = "primaryTopologyDistances" in raw and (
        primary is None or isinstance(primary, dict) and str(actor_id) in primary
    )
    strict = primary if use_primary else raw["topologyDistances"]
    name = (
        "allyRelaxedPrimaryTopologyDistances"
        if use_primary
        else "allyRelaxedTopologyDistances"
    )
    relaxed = raw.get(name)
    if (
        isinstance(strict, dict)
        and str(actor_id) in strict
        and strict[str(actor_id)] is None
        and isinstance(relaxed, dict)
        and type(relaxed.get(str(actor_id))) is int
        and relaxed[str(actor_id)] >= 0
    ):
        return name
    return None


def _metrics(
    raw, actor_id, *, unreachable_penalty=None, retreat=False, approach_topology=None
):
    features = validate_features(
        raw.get("outcomeFeatures", {}), "outcome features", 1e9
    )
    actors = {a["id"]: dict(a, position=tuple(a["position"])) for a in raw["actors"]}
    repertoires = raw.get("actorRepertoires")
    if isinstance(repertoires, dict):
        # Validate receipt binding before projecting tactical metadata. Opaque
        # native receipts can differ for unobserved state; they are not role
        # inputs and must not enter otherwise identical observation metrics.
        # Keep the original graph/receipt intact for native authority checks.
        repertoires = {
            identity: {
                name: value
                for name, value in row.items()
                if name not in ("sourceState", "stateRevision")
            }
            for identity, row in repertoires.items()
            if isinstance(row, dict)
            and ("sourceState" not in row or row["sourceState"] == raw.get("key"))
            and (
                "stateRevision" not in row
                or row["stateRevision"] == raw.get("stateRevision")
            )
        }
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
        has_primary_topology = "primaryTopologyDistances" in raw
        primary_topology = raw.get("primaryTopologyDistances")
        using_primary_topology = False
        if has_primary_topology:
            if primary_topology is None:
                topology = None
                using_primary_topology = True
            elif not isinstance(primary_topology, dict):
                raise ValueError("Invalid native primary topology distances")
            elif str(actor_id) in primary_topology:
                topology = primary_topology
                using_primary_topology = True
        position_basis = (
            "unknown_primary_topology"
            if using_primary_topology and topology is None
            else "directed_xyz_primary_target_topology"
            if using_primary_topology
            else "unknown_topology"
            if topology is None
            else "directed_xyz_topology"
        )
        if approach_topology is not None:
            # A fixed decision objective prevents an endpoint from switching
            # scales when an ally moves or a strict route becomes reachable.
            topology = raw.get(approach_topology)
            if topology is None:
                topology = {str(actor_id): None}
            position_basis = "directed_xyz_ally_relaxed_approach"
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
        actorRepertoires=repertoires,
        position=(min(distance, 6) if retreat else -distance) * 0.25,
        approachPosition=-distance * 0.25,
        position_basis=position_basis,
        threat=0,
        uncertainty=0,
        features=features,
    )


def _remaining_border_exposure(
    reverse, actors, actor_id, hazards, *, relax_allies=False
):
    actor = actors[actor_id]
    enemies = [
        other
        for other in actors.values()
        if other["hp"] > 0 and other["team"] != actor["team"]
    ]
    primary = [other for other in enemies if other.get("registeredSummon") is not True]
    goals = {tuple(other["position"]) for other in primary or enemies}
    origin = tuple(actor["position"])
    blocked = (
        {
            tuple(other["position"])
            for other in actors.values()
            if other["hp"] > 0 and (not relax_allies or other["team"] != actor["team"])
        }
        - goals
        - {origin}
    )
    return minimum_exposure(reverse, goals, blocked, origin, hazards)


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
    # A setup can cost AP before its newly enabled cast repays it. Keep one
    # certified, still-outstanding progress/AP-gain continuation alongside the strongest outcome,
    # rather than requiring that setup to beat immediate damage already. This
    # allocates exploration only: final utility remains the outcome score.
    preparation = min(
        (node for node in ranked if node.get("preparationProgress", 0) > 0),
        key=lambda node: (
            -node["preparationProgress"],
            -node["score"],
            len(node["actions"]),
            node["key"],
        ),
        default=None,
    )
    # With only two slots, existing support priority takes the second slot.
    preferred = [node for node in (preferred_support, preparation) if node is not None]
    if ranked and preferred:
        for node in (ranked[0], *preferred):
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
    cursors = {}
    for frame in branches:
        identity = id(frame["node"])
        if identity not in retained:
            continue
        previous = cursors.get(identity)
        if previous is None or (
            previous["stream"] is None and frame["stream"] is not None
        ):
            # A reused warm node may arrive through normal enumeration too.
            # Retain its already advanced iterator instead of restarting it.
            cursors[identity] = frame
    result, emitted = deque(), set()
    for frame in frames:
        identity = id(frame["node"])
        if frame["depth"] == 0:
            result.append(frame)
        elif identity not in emitted and cursors.get(identity) is frame:
            result.append(frame)
            emitted.add(identity)
    return result


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
    registered_summon_value = policy.get("registeredSummonValue", 0.25)
    if (
        type(registered_summon_value) not in (int, float)
        or not math.isfinite(registered_summon_value)
        or not 0 <= registered_summon_value <= 1
    ):
        raise ValueError("Invalid registered summon value")
    feature_weights = dict(DEFAULT_FEATURE_WEIGHTS)
    feature_weights.update(
        validate_features(policy.get("featureWeights", {}), "feature weights", 1000)
    )
    context_cache = DecisionContextCache(store, graph_loader=load_graph)
    memory_graph = root_graph or context_cache.graph(envelope["root"]["nativeContext"])
    retreat = attacked_this_turn(memory_graph, _fight(memory_graph), actor_id)
    attacked_targets = damaged_targets_this_turn(
        memory_graph,
        _fight(memory_graph),
        actor_id,
    )
    border_cells = battleground_border_cells(memory_graph, _fight(memory_graph))
    approach_topology = _approach_topology(envelope["root"], actor_id, retreat=retreat)
    root = _metrics(
        envelope["root"], actor_id, retreat=retreat, approach_topology=approach_topology
    )
    posture_adjacency = None
    if retreat:
        fight_reference = _fight(memory_graph)
        edges_reference = memory_graph.field(fight_reference, "edges")
        if memory_graph.resolve(edges_reference) is not None:
            posture_adjacency, _ = directed_adjacencies(
                _sequence(memory_graph, edges_reference)
            )
    apply_position(
        root,
        actor_id,
        posture_adjacency,
        after_attack=retreat,
        attacked_targets=attacked_targets,
    )
    allow_approach = root["teamPosture"]["mode"] == "approach"
    border_reverse = None
    unavoidable_border = None
    if border_cells and root["teamPosture"]["mode"] != "retreat":
        fight_reference = _fight(memory_graph)
        edges_reference = memory_graph.field(fight_reference, "edges")
        if memory_graph.resolve(edges_reference) is not None:
            cells = {
                tuple(cell)
                for cell in _sequence(
                    memory_graph, memory_graph.field(fight_reference, "walkable")
                )
            }
            _, border_reverse = directed_adjacencies(
                _sequence(memory_graph, edges_reference), cells=cells
            )
            unavoidable_border = _remaining_border_exposure(
                border_reverse,
                root["actors"],
                actor_id,
                border_cells,
                relax_allies=approach_topology is not None,
            )
    if root["actors"][actor_id]["hp"] <= 0:
        raise ValueError("Native search requires a live source actor")
    root_movement_available = root["actors"][actor_id]["mp"] > 0
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
        score, components, intent, target = evaluate(
            root,
            metrics,
            actor_id,
            weights,
            team,
            available_weights,
            summon_value=registered_summon_value,
        )
        # A bounded strategic preference makes a small native movement toll
        # comparable to advancing this turn even when no cast is yet in range.
        # This is not a prediction of future damage or native spell legality.
        actor = root["actors"][actor_id]
        moved = metrics["actors"][actor_id]["position"] != actor["position"]
        progress = max(
            0.0,
            (metrics.get("approachPosition", 0) - root.get("approachPosition", 0))
            / 0.25,
        )
        bonus = 0.0
        if (
            moved
            and metrics["actors"][actor_id]["hp"] > 0
            and metrics["teamPosture"]["mode"] == "approach"
            and root["position_basis"] == metrics["position_basis"]
        ):
            movement_budget = max(1, actor["mp"])
            bonus = (
                min(progress, movement_budget)
                / movement_budget
                * (actor["hp"] + max(0, actor.get("armor", 0)))
                * 0.02
                * weights["position"]
            )
        components["strategic_approach"] = round(bonus, 6)
        return score + bonus, components, intent, target

    # Complete snapshot/repertoire loading is mandatory context preparation,
    # separate from exploration work. Count it under the real owner deadline,
    # but do not let parsing the next full map starve its first candidate.
    # Node/depth and owner limits still constrain all work; no data is omitted.
    deadline = None
    waiting = 0.0
    preparation = 0.0
    root_action_attempted = False
    root_action_certified = False
    rival_forecast_skipped = False
    movement_only = False
    movement_only_deadline = None
    movement_only_budget_ms = policy.get("movementOnlySearchMs", 100)
    if (
        type(movement_only_budget_ms) is not int
        or not 1 <= movement_only_budget_ms <= 10000
    ):
        raise ValueError("Invalid native movement-only search budget")
    turn_deadline = None
    decision_deadline = None
    search_decision_deadline = None
    decision_wall_budget = None
    rival_search_reserve_ms = policy.get("rivalSearchReserveMs", 500)
    if (
        type(rival_search_reserve_ms) is not int
        or not 0 <= rival_search_reserve_ms <= 10000
    ):
        raise ValueError("Invalid rival search reserve")
    rival_reserved_ms = 0.0
    rival_search_started = None
    rival_search_used_ms = 0.0
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
        nonlocal turn_deadline, decision_deadline, search_decision_deadline
        nonlocal decision_wall_budget, rival_reserved_ms
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
            if rival_search_reserve_ms and "project_turn" in envelope.get(
                "operations", []
            ):
                rival_reserved_ms = min(
                    float(rival_search_reserve_ms), decision_wall_budget * 0.25
                )
            search_decision_deadline = decision_deadline - rival_reserved_ms / 1000

    update_turn_budget(envelope)
    stop_reasons = []
    work_at_budget_check = 0.0
    search_allowance_exhausted = False

    def exhausted():
        nonlocal work_at_budget_check, stop_reasons
        now = clock()
        if deadline is not None:
            work_at_budget_check = max(
                0.0, limits["budgetMs"] + (now - deadline) * 1000
            )
        reasons = []
        if search_allowance_exhausted:
            reasons.append("native_search_allowance_exhausted")
        if deadline is not None and now >= deadline:
            reasons.append("search_work_budget")
        # A slow mandatory root repertoire/context lookup must not spend the
        # whole decision slice before the first own action can be certified.
        # Until a root transition is accepted, allow the first movement
        # preview even after a slow mandatory context lookup. If the actor has
        # no MP, a rejected root cast cannot lead to movement, so consume the
        # decision slice after that first attempt instead of enumerating every
        # target on the full map. Otherwise a rejected cast must not starve a
        # later movement candidate.
        if (
            search_decision_deadline is not None
            and now >= search_decision_deadline
            and (
                root_action_certified
                or (root_action_attempted and not root_movement_available)
            )
        ):
            reasons.append("decision_wall_budget")
        if (
            movement_only_deadline is not None
            and now >= movement_only_deadline
            and root_action_certified
        ):
            reasons.append("movement_only_budget")
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
        nonlocal deadline, waiting, search_allowance_exhausted
        started = clock()
        response = yield query
        elapsed = max(0.0, clock() - started)
        waiting += elapsed
        if deadline is not None:
            deadline += elapsed
        update_turn_budget(response)
        if (
            isinstance(response, dict)
            and response.get("supported") is False
            and "native_search_allowance_exhausted"
            in response.get("unknownDependencies", [])
        ):
            search_allowance_exhausted = True
        return answer(response, query)

    def request(operation, key, **fields):
        nonlocal sequence
        sequence += 1
        query = dict(id=str(sequence), operation=operation, state=key, **fields)
        if root_action_certified:
            boundaries = [
                value
                for value in (search_decision_deadline, movement_only_deadline)
                if value is not None
            ]
            if turn_deadline is not None:
                boundaries.append(turn_deadline - reserve / 1000)
            if boundaries:
                query["searchAllowanceMs"] = max(
                    0.0, (min(boundaries) - clock()) * 1000
                )
        return with_incumbent(query)

    risk_phase = False
    risk_incumbent = None

    def with_incumbent(query):
        incumbent = risk_incumbent if risk_phase else independent_best
        if root_action_certified and (incumbent is None or not incumbent["actions"]):
            # End-turn has no root preview certificate. Clear the previous
            # snapshot so the owner uses its safe fallback instead of a cast.
            return dict(query, incumbent=None)
        if not root_action_certified or (not risk_phase and not incumbent["actions"]):
            return query
        action = dict(incumbent["actions"][0])
        if "path" in action:
            action["path"] = [list(cell) for cell in action["path"]]
        if "target" in action:
            action["target"] = list(action["target"])
        if "destination" in action:
            action["destination"] = list(action["destination"])
        return dict(
            query,
            incumbent=dict(
                protocol=3,
                requestId=envelope["requestId"],
                sourceKey=envelope["sourceKey"],
                rootState=root_key,
                action=action,
                plan=[action],
                partial=True,
                unknownDependencies=["native_search_budget_partial"],
            ),
        )

    def forward_risk_queries(generator, risk_deadline):
        response = None
        try:
            while True:
                try:
                    query = (
                        next(generator)
                        if response is None
                        else generator.send(response)
                    )
                except StopIteration as completed:
                    return completed.value
                query = dict(
                    query, searchAllowanceMs=max(0.0, (risk_deadline - clock()) * 1000)
                )
                response = yield with_incumbent(query)
        finally:
            generator.close()

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
        postureMode=root["teamPosture"]["mode"],
    )
    alternatives = [best]
    # Recovery executes one action. Score its actual root outcome rather than
    # assigning the utility of an unavailable multi-action continuation to it.
    independent_best = best
    root_node = dict(**best, visited=frozenset({state_identity(envelope["root"])}))
    pending = deque([dict(node=root_node, depth=0, stream=None)])
    expanded_by_depth = {}
    peak_continuations = 0
    # Retain sampled native outcomes only within this decision/session. The
    # full identity includes private runtime, authorities and flags; policy
    # and catalogue are fixed by this search's guarded envelope. A cache hit
    # never inherits another path's option, score or visited-state set.
    preview_cache = OrderedDict()
    preview_cache_capacity = min(256, limits["nodes"])
    preview_cache_hits = 0
    preview_cache_evictions = 0
    missing_preview = object()

    def remember_preview(node, action, state, key=None):
        nonlocal preview_cache_evictions
        if search_allowance_exhausted:
            return
        if key is None:
            key = _preview_cache_key(node["state"], action)
        preview_cache[key] = (state, node["key"])
        preview_cache.move_to_end(key)
        if len(preview_cache) > preview_cache_capacity:
            preview_cache.popitem(last=False)
            preview_cache_evictions += 1

    def record_preview(node, action, state, *, sample_source=None):
        nonlocal best, independent_best
        metrics = _metrics(
            state,
            actor_id,
            unreachable_penalty=unreachable_penalty,
            retreat=retreat,
            approach_topology=approach_topology,
        )
        apply_position(
            metrics,
            actor_id,
            posture_adjacency,
            after_attack=retreat,
            allow_approach=allow_approach,
            attacked_targets=attacked_targets,
        )
        if metrics["actors"][actor_id]["hp"] <= 0:
            metrics["position"] = root["position"]
        if action["type"] == "cast":
            before = {row["id"]: row for row in node["state"]["actors"]}
            roles = observed(before, metrics["actors"], actor_id)
            identity = action["spellId"], action["level"]
            capability_evidence.setdefault(identity, set()).update(roles)
        score, components, intent, target = evaluate_state(metrics)
        # Compare to the decision root, not the immediately preceding
        # action. Walking must not erase an unspent setup, and consuming
        # the actual PA/state progress must remove its beam protection.
        before_progress = root["features"].get("owned_state_progress")
        after_progress = metrics["features"].get("owned_state_progress")
        preparation_progress = max(
            0, metrics["actors"][actor_id]["ap"] - root["actors"][actor_id]["ap"]
        )
        if before_progress is not None and after_progress is not None:
            preparation_progress += max(0, after_progress - before_progress)
        option = dict(
            score=score,
            preparationProgress=preparation_progress,
            postureMode=metrics["teamPosture"]["mode"],
            components=components,
            key=state["key"],
            actions=node["actions"] + [action],
            state=state,
            intent=intent,
            target=target,
            orientationEvidence=node["orientationEvidence"]
            + [
                dict(
                    row,
                    sourceState=sample_source or node["key"],
                    previewState=state["key"],
                    **(
                        {"reusedForState": node["key"]}
                        if sample_source is not None and sample_source != node["key"]
                        else {}
                    ),
                )
                for row in state.get("damageContextEvidence", [])
            ],
            borderExposure=node.get("borderExposure", 0)
            + (
                sum(tuple(cell) in border_cells for cell in action["path"])
                if action["type"] == "move"
                else int(tuple(action["destination"]) in border_cells)
                if action["type"] == "portal_travel"
                else 0
            ),
            visited=node["visited"] | {state_identity(state)},
        )
        if option["borderExposure"]:
            # Prefer avoiding the perimeter when a safer route exists.
            # Required crossings must not deadlock a narrow native bridge;
            # actual resource/damage loss remains in the native outcome.
            avoidable_exposure = option["borderExposure"]
            if unavoidable_border is not None:
                remaining = _remaining_border_exposure(
                    border_reverse,
                    metrics["actors"],
                    actor_id,
                    border_cells,
                    relax_allies=approach_topology is not None,
                )
                if remaining is not None:
                    avoidable_exposure = max(
                        0, avoidable_exposure + remaining - unavoidable_border
                    )
            penalty = 2.0 * avoidable_exposure
            option["score"] -= penalty
            option["components"]["battleground_border_exposure"] = -penalty
        alternatives.append(option)
        if len(option["actions"]) == 1 and option["score"] > independent_best["score"]:
            independent_best = option
        if option["score"] > best["score"]:
            best = option
        return option, metrics

    # Re-preview a bounded published continuation, then explore alternatives.
    # These are proposals for the fresh root, never inherited native forecasts.
    warm_actions = _warm_start_actions(envelope.get("warmStart"))
    warm_limit = min(len(warm_actions), limits["depth"], limits["nodes"] // 4)
    warm_attempted, warm_accepted = 0, 0
    warm_previews = []
    warm_reused = 0
    missing_warm_preview = object()
    warm_node = root_node
    if warm_limit:
        deadline = clock() + limits["budgetMs"] / 1000
    for action in warm_actions[:warm_limit]:
        if exhausted():
            break
        warm_attempted += 1
        expanded += 1
        depth = len(warm_node["actions"]) + 1
        expanded_by_depth[depth] = expanded_by_depth.get(depth, 0) + 1
        if warm_node is root_node:
            root_action_attempted = True
        query = request("preview", warm_node["key"], action=action)
        state = yield from exchange(query)
        remember_preview(warm_node, action, state)
        if state is None or state_identity(state) in warm_node["visited"]:
            warm_previews.append((warm_node, action, None))
            break
        if warm_node is root_node:
            root_action_certified = True
        option, metrics = record_preview(warm_node, action, state)
        warm_previews.append((warm_node, action, (option, metrics)))
        warm_accepted += 1
        before = {row["id"]: row for row in warm_node["state"]["actors"]}
        hostile_damage = action["type"] == "cast" and any(
            old["team"] != before[actor_id]["team"]
            and metrics["actors"].get(identity, old)["hp"] < old["hp"]
            for identity, old in before.items()
        )
        # An actual attack changes post-attack positioning. Do not carry an
        # old approach tail past it: the next real decision reads its ledger
        # and selects hold/retreat from the newly published result.
        if (
            hostile_damage
            or state["phase"] != "active"
            or state["currentId"] != actor_id
            or metrics["actors"][actor_id]["hp"] <= 0
        ):
            break
        warm_node = option
        if depth < limits["depth"]:
            pending.append(dict(node=option, depth=depth, stream=None))

    while pending and expanded < limits["nodes"] and not exhausted():
        frame = pending.popleft()
        node = frame["node"]
        if frame["stream"] is None:
            repertoire = context_cache.get_repertoire(node["state"], actor_id)
            if repertoire is None:
                query = request("repertoire", node["key"], actorId=actor_id)
                repertoire = yield from exchange(query)
                if repertoire is not None:
                    context_cache.put_repertoire(node["state"], actor_id, repertoire)
            if repertoire is None:
                continue
            preparing = clock()
            repertoire = context_cache.plain(repertoire["nativeMetadata"])
            if node["key"] == root_key and all_owned_spells_unavailable(
                repertoire, node["state"], actor_id
            ):
                movement_only = True
                if movement_only_deadline is None:
                    # Spending the full tactical slice on walking cannot find
                    # an attack when the native authority proves none can run.
                    # Keep the first certified action guarantee and allocate a
                    # short additional wall budget to position alternatives.
                    movement_only_deadline = clock() + movement_only_budget_ms / 1000
            unavailable_spells = certified_unavailable_spell_keys(
                repertoire, node["state"], actor_id
            )
            certificate = repertoire.get("nativeCastingPrerequisites", {})
            if not isinstance(certificate, dict):
                certificate = {}
            unavailable_rows = {
                (row["spellId"], row["level"]): row
                for row in certificate.get("unavailable", [])
                if isinstance(row, dict)
                and type(row.get("spellId")) is int
                and type(row.get("level")) is int
                and (row["spellId"], row["level"]) in unavailable_spells
            }
            for spell in repertoire.get("spells", []):
                key = spell.get("spellId"), spell.get("level")
                if key not in unavailable_spells:
                    continue
                row = unavailable_rows.get(key)
                if row is None:
                    continue
                if row["reason"] == "missing_casting_table":
                    unsupported.append(
                        "native_casting_table_missing:{}:{}".format(
                            spell["spellId"], spell["level"]
                        )
                    )
                elif row["reason"] == "missing_root_metadata":
                    roots = ",".join(
                        str(root) for root in sorted(row["missingRootIds"])
                    )
                    unsupported.append(
                        "native_casting_root_metadata_missing:{}:{}:{}".format(
                            spell["spellId"], spell["level"], roots
                        )
                    )
            if node["key"] == root_key and root_graph is not None:
                if not isinstance(root_graph, NativeGraph):
                    raise ValueError("Invalid validated native root graph")
                graph = root_graph
            else:
                graph = context_cache.graph(node["state"]["nativeContext"])
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
            # These at most three previews were obtained during this search
            # from this exact parent node, not retained from the previous
            # publication. Keep their normal descendants eligible without
            # paying for or scoring the same transition a second time.
            reused = next(
                (
                    cached
                    for parent, tried, cached in warm_previews
                    if parent is node and tried == action
                ),
                missing_warm_preview,
            )
            if reused is not missing_warm_preview:
                warm_reused += 1
                if reused is None:
                    continue
                option, metrics = reused
                state = option["state"]
            else:
                if frame["depth"] == 0 and node["key"] == root_key:
                    root_action_attempted = True
                cache_key = _preview_cache_key(node["state"], action)
                cached_preview = preview_cache.get(cache_key, missing_preview)
                sample_source = node["key"]
                if cached_preview is missing_preview:
                    expanded += 1
                    depth = frame["depth"] + 1
                    expanded_by_depth[depth] = expanded_by_depth.get(depth, 0) + 1
                    query = request("preview", node["key"], action=action)
                    state = yield from exchange(query)
                    remember_preview(node, action, state, key=cache_key)
                else:
                    state, sample_source = cached_preview
                    preview_cache_hits += 1
                    preview_cache.move_to_end(cache_key)
                if state is None or state_identity(state) in node["visited"]:
                    continue
                if frame["depth"] == 0 and node["key"] == root_key:
                    root_action_certified = True
                option, metrics = record_preview(
                    node, action, state, sample_source=sample_source
                )
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
        from .query_threat import forecast

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
        if root["teamPosture"]["mode"] == "hold":
            # A nominally useful blocker must get a real escape alternative
            # in the existing risk budget. Duplicate holding routes otherwise
            # crowd it out before native forecasts can contradict tanking.
            escape = next(
                (option for option in ranked if option.get("postureMode") == "retreat"),
                None,
            )
            if escape is not None:
                shortlist.append(escape)
                seen.add(state_identity(escape["state"]))
                represented.add((escape["intent"], escape["target"]))
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
        if not root_action_certified or (
            search_allowance_exhausted
            or risk_deadline <= clock()
            or turn_deadline is not None
            and clock() >= turn_deadline - reserve / 1000
        ):
            # Rival forecasting is optional and can require several native
            # round trips. Do not let it consume the owner reserve or displace
            # the first own action when mandatory context was slow.
            rival_forecast_skipped = True
            unsupported.append("rival_forecast_skipped_after_root_action_budget")
        baseline_penalty = None
        evaluated = []

        def assess_risk_option(option, risk):
            penalty = risk["knownLowerBound"] * weights["threat"]
            uncertainty_penalty = (
                0 if risk["complete"] else unknown_penalty * weights["uncertainty"]
            )
            adjusted = (
                option["score"] + baseline_penalty - penalty - uncertainty_penalty
            )
            option_metrics = _metrics(
                option["state"],
                actor_id,
                retreat=retreat,
                approach_topology=approach_topology,
            )
            posture = apply_position(
                option_metrics,
                actor_id,
                posture_adjacency,
                after_attack=retreat,
                allow_approach=allow_approach,
                attacked_targets=attacked_targets,
            )
            contradiction = contradicted_hold(
                option_metrics["actors"], actor_id, posture, risk
            )
            posture_penalty = (
                posture["holdPreference"] * weights["position"]
                if contradiction
                else 0.0
            )
            adjusted -= posture_penalty
            return dict(
                option,
                riskForecast=risk,
                score=adjusted,
                postureRiskReason=contradiction,
                components=dict(
                    option["components"],
                    rival_risk_baseline=baseline_penalty,
                    rival_risk_lower_bound=-penalty,
                    rival_risk_uncertainty=-uncertainty_penalty,
                    contradicted_hold_preference=-posture_penalty,
                ),
            )

        unknown_independent = {}

        def option_identity(option):
            return option["key"], json.dumps(
                option["actions"], sort_keys=True, separators=(",", ":")
            )

        def recovery_risk_pool():
            # A missing forecast certifies neither safety nor danger. Include
            # every certified one-action outcome with explicit missing coverage,
            # then impute observed rival danger on the same basis as real runs.
            actual = {option_identity(item) for item in evaluated}
            pool = list(evaluated)
            for candidate in alternatives:
                if len(candidate["actions"]) > 1:
                    continue
                identity = option_identity(candidate)
                if identity in actual:
                    continue
                if identity not in unknown_independent:
                    active = candidate["state"]["phase"] == "active"
                    friendly = next(
                        row["team"]
                        for row in candidate["state"]["actors"]
                        if row["id"] == actor_id
                    )
                    missing = dict(
                        risk=None if active else 0,
                        knownLowerBound=0,
                        complete=not active,
                        rivals=[
                            dict(
                                actorId=row["id"],
                                knownLowerBound=0,
                                complete=False,
                                expanded=0,
                            )
                            for row in candidate["state"]["actors"]
                            if active and row["team"] != friendly and row["hp"] > 0
                        ],
                        unknownDependencies=["rival_response_not_evaluated"]
                        if active
                        else [],
                    )
                    unknown_independent[identity] = assess_risk_option(
                        candidate, missing
                    )
                pool.append(unknown_independent[identity])
            return pool

        def recovery_risk_incumbent():
            # Rank a separate snapshot with the same coverage policy as the
            # completed phase. Never mutate scores that final ranking adjusts.
            from .risk_coverage import comparable_bounds

            recovery_pool = recovery_risk_pool()
            partial_bounds = comparable_bounds(
                [item["riskForecast"] for item in recovery_pool]
            )
            # Preserve an observed aggregate lower bound even when a provider
            # cannot attribute all of it to individual rivals. This remains
            # imputed unknown coverage, not a certified loss in another state.
            unattributed = max(
                (
                    max(
                        0,
                        item["riskForecast"]["knownLowerBound"]
                        - sum(
                            rival.get("knownLowerBound", 0)
                            for rival in item["riskForecast"].get("rivals", [])
                        ),
                    )
                    for item in evaluated
                ),
                default=0,
            )
            comparable = []
            for item, bound in zip(recovery_pool, partial_bounds):
                if (
                    "rival_response_not_evaluated"
                    in item["riskForecast"]["unknownDependencies"]
                ):
                    bound += unattributed
                imputation = (
                    -item["components"]["rival_risk_lower_bound"]
                    - bound * weights["threat"]
                )
                comparable.append(
                    dict(
                        item,
                        score=item["score"] + imputation,
                        components=dict(
                            item["components"],
                            rival_risk_coverage_imputation=imputation,
                        ),
                    )
                )
            independent_comparable = [
                item for item in comparable if len(item["actions"]) <= 1
            ]
            return min(
                independent_comparable,
                key=lambda item: (
                    -item["score"],
                    len(item["actions"]),
                    item["key"],
                ),
            )

        if not rival_forecast_skipped:
            risk_phase = True
            rival_search_started = clock()
            # Before the first response, every independent outcome has the
            # same explicitly unknown risk. Keep its certified own utility
            # available to RPC recovery without borrowing a combo forecast.
            baseline_penalty = unknown_penalty * weights["uncertainty"]
            risk_incumbent = recovery_risk_incumbent()
            # The first real baseline replaces this provisional reference.
            # Never retain provisional scores in the per-option assessment cache.
            baseline_penalty = None
            unknown_independent.clear()
        for option in [] if rival_forecast_skipped else shortlist:
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
                    yield from forward_risk_queries(
                        forecast(
                            option["state"],
                            actor_id,
                            store,
                            weights,
                            deadline=risk_deadline,
                            clock=clock,
                            **risk_limits,
                        ),
                        risk_deadline,
                    )
                )
            )
            unsupported.extend(risk["unknownDependencies"])
            if "native_search_allowance_exhausted" in risk["unknownDependencies"]:
                search_allowance_exhausted = True
                if "native_search_allowance_exhausted" not in stop_reasons:
                    stop_reasons.append("native_search_allowance_exhausted")
            if baseline_penalty is None:
                baseline_penalty = risk["knownLowerBound"] * weights["threat"] + (
                    0 if risk["complete"] else unknown_penalty * weights["uncertainty"]
                )
            assessed = assess_risk_option(option, risk)
            adjusted = assessed["score"]
            contradiction = assessed["postureRiskReason"]
            evaluated.append(assessed)
            risk_incumbent = recovery_risk_incumbent()
            risk_trace.append(
                dict(
                    state=option["key"],
                    actions=option["actions"],
                    score=adjusted,
                    forecast=risk,
                    postureRiskReason=contradiction,
                )
            )
            if search_allowance_exhausted:
                break
        if rival_search_started is not None:
            rival_search_used_ms = max(0.0, clock() - rival_search_started) * 1000
        if evaluated:
            from .risk_coverage import comparable_bounds

            bounds = comparable_bounds([option["riskForecast"] for option in evaluated])
            for option, bound, trace in zip(evaluated, bounds, risk_trace):
                old_penalty = -option["components"]["rival_risk_lower_bound"]
                penalty = bound * weights["threat"]
                option["score"] += old_penalty - penalty
                option["components"]["rival_risk_coverage_imputation"] = (
                    old_penalty - penalty
                )
                trace["score"] = option["score"]
                trace["coverageImputation"] = penalty - old_penalty
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
    recovery_selection = search_allowance_exhausted
    if recovery_selection:
        if risk_phase:
            # This snapshot includes actual forecasts and explicitly unknown
            # independent outcomes, normalized before final trace mutation.
            best = risk_incumbent if risk_incumbent is not None else alternatives[0]
            unsupported.extend(
                best.get("riskForecast", {}).get("unknownDependencies", [])
            )
        else:
            best = independent_best
    recovery_continuation = None
    if recovery_selection and best["actions"]:
        # Advice can outlive exploration, but only a branch beginning with the
        # exact independently selected action matches the next publication.
        # The risk shortlist is not the complete preview inventory. Rank all
        # matching branches by own utility only; advice inherits no risk score.
        matching = [
            option
            for option in alternatives
            if len(option["actions"]) > 1 and option["actions"][0] == best["actions"][0]
        ]
        for option in sorted(
            matching,
            key=lambda item: (-item["score"], len(item["actions"]), item["key"]),
        ):
            check()
            recovery_continuation = recovery_proposal(
                option["actions"][1:],
                root_action=best["actions"][0],
                source=envelope["sourceKey"],
                root=root_key,
                request=envelope["requestId"],
            )
            if recovery_continuation is not None:
                break
    selected = _metrics(
        best["state"],
        actor_id,
        unreachable_penalty=unreachable_penalty,
        retreat=retreat,
        approach_topology=approach_topology,
    )
    apply_position(
        selected,
        actor_id,
        posture_adjacency,
        after_attack=retreat,
        allow_approach=allow_approach,
        attacked_targets=attacked_targets,
    )
    if selected["actors"][actor_id]["hp"] <= 0:
        selected["position"] = root["position"]
    return dict(
        protocol=3,
        requestId=envelope["requestId"],
        sourceKey=envelope["sourceKey"],
        rootState=root_key,
        action=best["actions"][0] if best["actions"] else {"type": "end_turn"},
        defensiveFacing=(
            dict(
                sourceKey=envelope["sourceKey"],
                rootState=root_key,
                actorId=actor_id,
                turnId=envelope["root"]["turnId"],
                stateRevision=envelope["root"]["stateRevision"],
                actors=[
                    dict(id=row["id"], position=row["position"])
                    for row in envelope["root"]["actors"]
                ],
                visibleActorIds=[row["id"] for row in envelope["root"]["actors"]],
                rivals=best.get("riskForecast", {}).get("rivals", []),
            )
            if not best["actions"]
            else None
        ),
        plan=best["actions"],
        **(
            {"recoveryContinuation": recovery_continuation}
            if recovery_continuation is not None
            else {}
        ),
        score=best["score"],
        components=best["components"],
        expanded=expanded,
        rivalForecasts=risk_trace,
        teamPosture=dict(root=root["teamPosture"], selected=selected["teamPosture"]),
        postureRiskReason=best.get("postureRiskReason"),
        searchBudgetEvidence=dict(
            decisionContextCache=dict(context_cache.metrics),
            previewCacheHits=preview_cache_hits,
            previewCacheEntries=len(preview_cache),
            previewCacheCapacity=preview_cache_capacity,
            previewCacheEvictions=preview_cache_evictions,
            warmStartPreviews=warm_attempted,
            warmStartAccepted=warm_accepted,
            warmStartReused=warm_reused,
            nativeWaitMs=waiting * 1000,
            stopReasons=stop_reasons,
            searchWorkMsAtLastBudgetCheck=work_at_budget_check,
            decisionWallBudgetMs=decision_wall_budget,
            rivalSearchReserveMs=rival_reserved_ms,
            rivalSearchUsedMs=rival_search_used_ms,
            searchTimeFraction=time_fraction,
            movementOnly=movement_only,
            movementOnlyBudgetMs=movement_only_budget_ms if movement_only else None,
            contextPreparationMs=preparation * 1000,
            commitReserveMs=reserve,
            expandedByDepth={
                str(depth): count for depth, count in sorted(expanded_by_depth.items())
            },
            peakContinuationFrames=peak_continuations,
            rootActionCertified=root_action_certified,
            recoverySelection=(
                ("certified_single_action" if best["actions"] else "end_turn")
                if recovery_selection
                else None
            ),
            rootActionAttempted=root_action_attempted,
            rootActionReserveUsed=(
                root_action_certified
                and decision_deadline is not None
                and clock() >= decision_deadline
            ),
            rivalForecastSkipped=rival_forecast_skipped,
        ),
        positionEvidence=dict(
            basis=selected["position_basis"],
            strategicApproachBasis="root_effective_health_two_percent_per_mp_budget",
            strategicApproachUtility=best["components"].get("strategic_approach", 0),
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
