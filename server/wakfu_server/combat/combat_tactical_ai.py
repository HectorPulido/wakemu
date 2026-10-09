"""Small native bridge for the separate tactical service.

Only world certifies forecasts and commits actions. Service plans are advisory.
No model/rules from ai-service are imported into the game server.
"""
from wakfu_server import native_catalog as protocol_catalog
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
import random
import time
import uuid
import urllib.request
from functools import lru_cache
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal

MAX_BODY = 4 * 1024 * 1024
POLICY_VERSION = "native-npc-v2-1"


@lru_cache(maxsize=1)
def catalog_version():
    from wakfu_server.paths import DATA_ROOT

    digest = hashlib.sha256()
    # Hash immutable source assets directly, without re-encoding hundreds of
    # thousands of compiled rank records on the decision path.
    for name in (
        "native-npc-spell-effect-trees.json",
        "native-spell-casting.json",
        "native-spell-limits.json",
        "spell-effect-trees.json",
        "combat-state-definitions.json",
        "granted-spell-effect-trees.json",
        "native-area-effect-trees.json",
        "effect-characteristic-registry.json",
        "content-manifest.json",
    ):
        digest.update(name.encode())
        with protocol_catalog.open(DATA_ROOT / name, "rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=_context_json,
        ).encode()
    ).hexdigest()


def _context_json(value):
    # PostgreSQL character/build records contain timestamps and binary blobs.
    # Canonicalize their types rather than dropping gameplay context or using
    # repr(), whose object addresses make identical contexts nondeterministic.
    if isinstance(value, (bytes, bytearray, memoryview)):
        return dict(nativeBytes=bytes(value).hex())
    if isinstance(value, (datetime, date)):
        return dict(nativeDate=value.isoformat())
    if isinstance(value, Decimal) and value.is_finite():
        return dict(nativeDecimal=str(value))
    if isinstance(value, (set, frozenset)):
        return dict(nativeSet=sorted((_hash(item) for item in value)))
    raise TypeError("Unsupported native AI context type: " + type(value).__name__)


def state_key(fight):
    from .combat_geometry_snapshot import ImmutableTerrainSet, source_snapshot

    state = source_snapshot(fight)
    for name in ("walkable", "edges"):
        if isinstance(state.get(name), ImmutableTerrainSet):
            state[name] = dict(immutableTerrain=_terrain_hash(state[name]))
    return _hash(state)


@lru_cache(maxsize=16)
def _terrain_hash(terrain):
    return _hash(sorted(terrain))


def _adjacency(edges):
    from .combat_geometry_snapshot import ImmutableTerrainSet

    return (
        _cached_adjacency(edges)
        if isinstance(edges, ImmutableTerrainSet)
        else _make_adjacency(edges)
    )


def _make_adjacency(edges):
    graph = {}
    for src, dst in edges or ():
        if abs(src[0] - dst[0]) + abs(src[1] - dst[1]) == 1:
            graph.setdefault(src, []).append(dst)
    return {src: tuple(sorted(destinations)) for src, destinations in graph.items()}


@lru_cache(maxsize=16)
def _cached_adjacency(edges):
    return _make_adjacency(edges)


@dataclass
class Preview:
    fight: object
    packets: tuple = ()
    spell: object = None


class NativeProvider:
    def __init__(
        self,
        character,
        monsters,
        deck_blob,
        *,
        area_provider=None,
        policy=None,
        forecast_limits=None,
        policy_version=None
    ):
        self.character, self.monsters, self.deck = character, monsters, deck_blob
        self.area_provider = area_provider
        self.policy = deepcopy(policy or {})
        self.forecast_limits = deepcopy(forecast_limits or {})
        self.policy_version = policy_version

    @property
    def context_key(self):
        return _hash(
            dict(
                character=self.character,
                monsters=self.monsters,
                deck=self.deck.hex(),
                policy=self.policy,
                forecast_limits=self.forecast_limits,
                policy_version=self.policy_version,
            )
        )

    @property
    def catalog_version(self):
        return catalog_version()

    def roster(self, fight):
        result = []
        for actor in sorted(fight.actors.values(), key=lambda a: a.id):
            stats = actor.effect_stats
            if not isinstance(stats, dict) or 4 not in stats or 97 not in stats:
                raise ValueError(
                    "Missing authoritative AI actor resource/armor context"
                )
            result.append(
                dict(
                    id=actor.id,
                    team=actor.team,
                    controlled=actor.controlled,
                    position=list(actor.position),
                    hp=actor.hp,
                    max_hp=actor.max_hp,
                    ap=actor.ap,
                    mp=actor.mp,
                    wp=stats[4],
                    armor=stats[97],
                    direction=getattr(actor, "direction", None),
                )
            )
        return result

    def capabilities(self, fight):
        from .combat_ai_capabilities import spell_capabilities

        return spell_capabilities(fight, self.monsters)

    def _useful_targets(self, fight, capability):
        actor = fight.current
        tags = set(capability.get("tags", ()))
        targets = []
        for target in fight.actors.values():
            if target.hp <= 0:
                continue
            ally = target.team == actor.team
            if (
                not ally
                and tags & {"damage", "control", "debuff", "displacement"}
                or ally
                and "heal" in tags
                and target.hp < target.max_hp
                or ally
                and tags & {"armor", "buff"}
                or not ally
                and "unknown" in tags
            ):
                targets.append(target)
        return targets

    def outcome_features(self, fight):
        # Advisory position value rewards proximity to useful capabilities.
        # Native previews still decide range/LOS/conditions and actual benefit.
        if fight.phase != "active" or fight.current is None or fight.current.controlled:
            return dict(positionValue=0)
        actor = fight.current
        capabilities = self.capabilities(fight)
        targets = [
            (capability, target)
            for capability in capabilities
            for target in self._useful_targets(fight, capability)
        ]

        def useful(cell):
            return any(
                (
                    1
                    <= abs(cell[0] - target.position[0])
                    + abs(cell[1] - target.position[1])
                    <= 1
                    if capability.get("unknownDependencies")
                    == ["missing_casting_table"]
                    else capability["minimum"]
                    <= abs(cell[0] - target.position[0])
                    + abs(cell[1] - target.position[1])
                    <= capability["maximum"]
                )
                for capability, target in targets
            )

        # No healed deficit or other useful target: do not force support into
        # melee. Empty/unknown repertories may still approach living enemies.
        if not capabilities:
            enemies = [
                a for a in fight.actors.values() if a.hp > 0 and a.team != actor.team
            ]

            def useful(cell):
                return any((cell, e.position) in (fight.edges or ()) for e in enemies)

        if capabilities and not targets:
            return dict(positionValue=0)
        distance = _nearest_distance(fight, actor, useful)
        return dict(positionValue=-distance)

    def actions(self, fight):
        from .combat_ai_capabilities import target_affinity

        actor = fight.current
        if actor is None or actor.controlled or actor.hp <= 0:
            return
        capabilities = self.capabilities(fight)
        targets = [a for a in fight.actors.values() if a.hp > 0]
        distances = _distances(fight, actor.position, actor.id, budget=actor.mp)
        useful = [(c, t) for c in capabilities for t in self._useful_targets(fight, c)]
        enemies = [a for a in targets if a.team != actor.team]

        def movement_rank(cell):
            gap = min(
                (
                    max(
                        c["minimum"]
                        - abs(cell[0] - t.position[0])
                        - abs(cell[1] - t.position[1]),
                        abs(cell[0] - t.position[0])
                        + abs(cell[1] - t.position[1])
                        - c["maximum"],
                        0,
                    )
                    for c, t in useful
                ),
                default=0,
            )
            return gap, distances[cell][0], cell

        ranked = sorted(
            (p for p in distances if p != actor.position), key=movement_rank
        )
        # Preserve native BACK/SIDE alternatives before nearby frontal cells
        # exhaust the shortlist. Only preview damage can reward localization.
        from types import SimpleNamespace
        from .combat_ordinary_authority import native_facing

        flanks = []
        offensive = [(c, t) for c, t in useful if "damage" in c.get("tags", ())]
        for localization in ("BACK", "SIDE"):
            candidate = next(
                (
                    cell
                    for cell in ranked
                    if any(
                        c["minimum"]
                        <= abs(cell[0] - t.position[0]) + abs(cell[1] - t.position[1])
                        <= c["maximum"]
                        and type(getattr(t, "direction", None)) is int
                        and 0 <= t.direction < 8
                        and native_facing(SimpleNamespace(position=cell), t)
                        == localization
                        for c, t in offensive
                    )
                ),
                None,
            )
            if candidate is not None and candidate not in flanks:
                flanks.append(candidate)
        relevant = (flanks + [p for p in ranked if p not in flanks])[:8]
        if enemies:
            escape = max(
                distances,
                key=lambda p: (
                    min(
                        abs(p[0] - e.position[0]) + abs(p[1] - e.position[1])
                        for e in enemies
                    ),
                    p,
                ),
            )
            if escape != actor.position and escape not in relevant:
                relevant.append(escape)
        ground = sorted(
            {
                dst
                for src, dst in fight.edges or ()
                if any(src == a.position for a in targets)
            }
            - {a.position for a in targets}
        )[:8]
        # One iterator per spell avoids spending the whole budget on the first
        # target or spell. Exact preview validates the range envelope/conditions.
        spell_groups = []
        for capability in capabilities:
            ordered = sorted(
                targets, key=lambda t: target_affinity(capability, actor, t)
            )
            candidates = [
                dict(
                    type="cast",
                    spellId=capability["spellId"],
                    level=capability["level"],
                    targetId=t.id,
                    target=list(t.position),
                )
                for t in ordered
            ]
            candidates += [
                dict(
                    type="cast",
                    spellId=capability["spellId"],
                    level=capability["level"],
                    targetId=None,
                    target=list(cell),
                )
                for cell in ground
            ]
            # This is only a conservative coarse pruning. Conditional tables
            # contribute their entire envelope; self policy is left to native.
            candidates = [
                a
                for a in candidates
                if tuple(a["target"]) == actor.position
                or capability["minimum"]
                <= abs(a["target"][0] - actor.position[0])
                + abs(a["target"][1] - actor.position[1])
                <= capability["maximum"]
            ]
            spell_groups.append(iter(candidates))
        movement_group = iter(
            dict(type="move", path=[list(p) for p in distances[cell][1]])
            for cell in relevant
        )
        groups = [*spell_groups, movement_group]
        while groups:
            active = []
            for group in groups:
                action = next(group, None)
                if action is not None:
                    yield action
                    active.append(group)
            groups = active

    def preview(self, fight, action, action_id, *, forecast):
        if action["type"] == "cast":
            from .combat_npc_spell import prepare_npc_spell

            # Independent deterministic forecast draws; real execution receives
            # a fresh RNG and is re-evaluated after every commit.
            seed = int(_hash(dict(state=state_key(fight), action=action)), 16)
            transaction = prepare_npc_spell(
                fight,
                action,
                self.character,
                self.monsters,
                self.deck,
                action_id=action_id,
                rng=random.Random(seed) if forecast else None,
            )
            if set(transaction.fight.actors) != set(fight.actors):
                raise ValueError(
                    "New summon actors require native stat serialization authority"
                )
            return Preview(transaction.fight, transaction.packets, transaction)
        if action["type"] != "move":
            raise ValueError("Unsupported native AI action")
        from .combat_cast_facing import DIRECTIONS
        from .combat_movement import movement

        preview = deepcopy(fight)
        actor = preview.current
        origin = actor.position
        path = [tuple(c) for c in action["path"]]
        preview.server_move(actor.id, path)
        before = origin if len(path) == 1 else path[-2]
        actor.direction = DIRECTIONS[(path[-1][0] - before[0], path[-1][1] - before[1])]
        packets = (
            movement(fight.id, action_id, actor.id, [origin, *path], actor.direction),
        )
        if self.area_provider is not None:
            preview, callbacks = self.area_provider(
                preview,
                actor_id=actor.id,
                action_id=action_id + 1,
                path=path,
                origin=origin,
            )
            packets += tuple(callbacks)
        if preview.actors[actor.id].position != path[-1]:
            raise ValueError(
                "Movement reaction displaced actor; no certified complete route"
            )
        return Preview(preview, packets)

    def commit(self, runtime, action, stats_serializer):
        if runtime.awaiting_ack is not None or runtime.pending:
            raise ValueError("Previous combat turn is not synchronized")
        source = _source_key(runtime, self)
        preview = self.preview(
            runtime.fight, action, runtime.action_id + 1, forecast=False
        )
        from .combat_area_boundary import adopt_runtime

        candidate = deepcopy(runtime)
        if preview.spell is not None:
            from .combat_spell_commit import commit_spell_transaction

            packets = commit_spell_transaction(
                candidate, preview.spell, stats_serializer=stats_serializer
            )
        else:
            from .combat_wire import actor_state

            packets = list(preview.packets) + [candidate._flush()]
            for actor in preview.fight.actors.values():
                packets.append(
                    (
                        12873,
                        actor_state(
                            12873,
                            preview.fight.id,
                            actor.id,
                            stats_serializer(actor, preview.fight),
                        ),
                    )
                )
            packets.append(candidate._flush())
            packets = candidate.prepare_delivery(packets)
            candidate.fight = preview.fight
            candidate.action_id += 2 if self.area_provider is not None else 1
        if source != _source_key(runtime, self):
            raise ValueError("Combat changed while preparing NPC delivery")
        adopt_runtime(runtime, candidate)
        target = runtime.fight.actors.get(action.get("targetId"))
        if action["type"] == "cast" and target is not None:
            caster = runtime.fight.actors[preview.spell.plan["actor_id"]]
            if target.team != caster.team:
                focus = dict(getattr(runtime, "tactical_focus", {}))
                focus[str(caster.team)] = target.id if target.hp > 0 else None
                runtime.tactical_focus = focus
        return packets


def _distances(fight, origin, actor_id, *, budget=None, paths=True):
    occupied = {
        a.position for a in fight.actors.values() if a.id != actor_id and a.hp > 0
    }
    graph = _adjacency(fight.edges)
    reached = {origin: (0, [])}
    queue = deque([origin])
    while queue:
        cell = queue.popleft()
        distance, path = reached[cell]
        if budget is not None and distance >= budget:
            continue
        for dst in graph.get(cell, ()):
            if dst not in occupied and dst not in reached:
                reached[dst] = distance + 1, [*path, dst] if paths else []
                queue.append(dst)
    return reached


def _nearest_distance(fight, actor, useful):
    graph = _adjacency(fight.edges)
    occupied = {
        a.position for a in fight.actors.values() if a.id != actor.id and a.hp > 0
    }
    visited, queue = {actor.position}, deque([(actor.position, 0)])
    while queue:
        cell, distance = queue.popleft()
        if useful(cell):
            return distance
        for destination in graph.get(cell, ()):
            if destination not in visited and destination not in occupied:
                visited.add(destination)
                queue.append((destination, distance + 1))
    return len(fight.walkable)


def _source_key(runtime, provider):
    return _hash(
        dict(
            fight=state_key(runtime.fight),
            action=runtime.action_id,
            nativeAction=runtime.native_action_id,
            ack=runtime.awaiting_ack,
            pending=bool(runtime.pending),
            focus=getattr(runtime, "tactical_focus", {}),
            context=provider.context_key,
        )
    )


def build_request(runtime, provider, *, max_previews=48, budget_ms=150, depth=2):
    if (
        any(type(v) is not int or v <= 0 for v in (max_previews, budget_ms, depth))
        or max_previews > 256
        or depth > 4
        or budget_ms > 5000
    ):
        raise ValueError("Invalid native forecast budget")
    fight = runtime.fight
    if runtime.awaiting_ack is not None or runtime.pending:
        raise ValueError("Previous combat turn is not synchronized")
    if fight.phase != "active" or fight.current is None or fight.current.controlled:
        raise ValueError("Missing active NPC turn")
    if fight.edges is None:
        raise ValueError("AI requires native movement edges")
    if not hasattr(runtime, "tactical_instance_id"):
        runtime.tactical_instance_id = uuid.uuid4().hex
    version = getattr(provider, "catalog_version", "external-provider-v1")
    source = _source_key(runtime, provider)
    root = state_key(fight)
    deadline = time.monotonic() + budget_ms / 1000
    states, private, frontier = {}, {root: fight}, [root]

    def register(key, state):
        states[key] = dict(
            key=key,
            actors=provider.roster(state),
            transitions=[],
            **provider.outcome_features(state)
        )

    register(root, fight)
    previews, rejected, reasons = 0, 0, {}
    started = time.monotonic()
    for level in range(depth):
        following = []
        for key in frontier:
            state = private[key]
            if (
                state.phase != "active"
                or state.current is None
                or state.current.id != fight.current.id
            ):
                continue
            for action in provider.actions(state):
                if previews >= max_previews or time.monotonic() >= deadline:
                    break
                previews += 1
                try:
                    preview = provider.preview(
                        deepcopy(state),
                        action,
                        runtime.action_id + level + 1,
                        forecast=True,
                    )
                    next_key = state_key(preview.fight)
                    if next_key == key:
                        continue
                    if next_key not in states:
                        register(next_key, preview.fight)
                        private[next_key] = preview.fight
                        following.append(next_key)
                    states[key]["transitions"].append(
                        dict(
                            id=_hash(action),
                            supported=True,
                            action=action,
                            nextState=next_key,
                        )
                    )
                except ValueError as error:
                    rejected += 1
                    label = str(error)[:160]
                    if label in reasons or len(reasons) < 8:
                        reasons[label] = reasons.get(label, 0) + 1
            if previews >= max_previews or time.monotonic() >= deadline:
                break
        representatives, seen = [], set()
        for destination in following:
            incoming = next(
                (
                    t["action"]
                    for k in frontier
                    for t in states[k]["transitions"]
                    if t["nextState"] == destination
                ),
                {},
            )
            category = (
                incoming.get("type"),
                incoming.get("spellId"),
                incoming.get("targetId"),
            )
            if category not in seen:
                seen.add(category)
                representatives.append(destination)
        frontier = (
            representatives + [k for k in following if k not in representatives]
        )[:8]
        if not frontier or previews >= max_previews or time.monotonic() >= deadline:
            break
    policy = dict(getattr(provider, "policy", {}))
    policy.setdefault("depth", depth)
    capabilities = (
        provider.capabilities(fight)
        if callable(getattr(provider, "capabilities", None))
        else []
    )
    # Only the service's certified actions need geometric validation. Keep the
    # complete native terrain in world/state hashes, and send an exact subset
    # containing every forecast actor, cast cell and movement route. This avoids
    # retransmitting a 17k-cell arena on every action; no edge is invented.
    decision_cells = {
        tuple(a["position"]) for state in states.values() for a in state["actors"]
    }
    for state in states.values():
        for transition in state["transitions"]:
            action = transition["action"]
            decision_cells.update(tuple(cell) for cell in action.get("path", ()))
            if "target" in action:
                decision_cells.add(tuple(action["target"]))
    if not decision_cells <= fight.walkable:
        raise ValueError("Forecast geometry outside native arena")
    decision_edges = {
        (a, b) for a, b in fight.edges if a in decision_cells and b in decision_cells
    }
    request = dict(
        protocol=2,
        requestId=uuid.uuid4().hex,
        stateKey=source,
        fightInstanceId=runtime.tactical_instance_id,
        fight_id=fight.id,
        actor_id=fight.current.id,
        current_id=fight.current.id,
        turnId=fight.turn_id,
        stateRevision=fight.sequence,
        catalogVersion=version,
        policyVersion=POLICY_VERSION
        + ":"
        + _hash(
            dict(policy=policy, identity=getattr(provider, "policy_version", None))
        ),
        walkable=[list(p) for p in sorted(decision_cells)],
        edges=[[list(a), list(b)] for a, b in sorted(decision_edges)],
        terrainScope="certified_action_footprint",
        actors=states[root]["actors"],
        rootState=root,
        states=list(states.values()),
        capabilities=capabilities,
        policy=policy,
        producerTrace=dict(
            previews=previews,
            rejected=rejected,
            nativeCells=len(fight.walkable),
            decisionCells=len(decision_cells),
            rejectedReasons=reasons,
            elapsedMs=round((time.monotonic() - started) * 1000, 3),
        ),
    )
    focus_id = getattr(runtime, "tactical_focus", {}).get(str(fight.current.team))
    focus = fight.actors.get(focus_id)
    if focus is not None and focus.hp > 0 and focus.team != fight.current.team:
        request["teamContext"] = dict(
            fightInstanceId=runtime.tactical_instance_id,
            stateRevision=fight.sequence,
            team=fight.current.team,
            focusId=focus_id,
            reservedCells=[],
        )
    if source != _source_key(runtime, provider):
        raise ValueError("Combat changed during AI preview generation")
    if (
        len(json.dumps(request, allow_nan=False, separators=(",", ":")).encode())
        > MAX_BODY
    ):
        raise ValueError("Native AI snapshot exceeds transport budget")
    return request


def validate_response(runtime, request, response, provider):
    if (
        runtime.awaiting_ack is not None
        or runtime.pending
        or runtime.fight.current is None
        or runtime.fight.current.id != request["actor_id"]
    ):
        raise ValueError("AI actor changed or synchronization pending")
    if request["stateKey"] != _source_key(runtime, provider):
        raise ValueError("Combat changed while AI was deciding")
    if (
        not isinstance(response, dict)
        or type(response.get("protocol")) is not int
        or response["protocol"] != 2
    ):
        raise ValueError("Invalid tactical AI response")
    for field in (
        "requestId",
        "stateKey",
        "fightInstanceId",
        "turnId",
        "stateRevision",
        "catalogVersion",
        "policyVersion",
    ):
        if (
            type(response.get(field)) is not type(request[field])
            or response[field] != request[field]
        ):
            raise ValueError("Stale tactical AI response: " + field)
    decision = response.get("decision")
    if (
        not isinstance(decision, dict)
        or type(decision.get("actor_id")) is not int
        or decision["actor_id"] != request["actor_id"]
    ):
        raise ValueError("Invalid tactical AI actor")
    actions = decision.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 16:
        raise ValueError("Invalid tactical AI actions")
    first = actions[0]
    if first == dict(type="end_turn"):
        return first
    root = next(s for s in request["states"] if s["key"] == request["rootState"])
    for transition in root["transitions"]:
        if transition["supported"] and _hash(transition["action"]) == _hash(first):
            return deepcopy(transition["action"])
    raise ValueError("AI action lacks native certification")


def transport(request):
    url = os.environ.get("WAKFU_AI_URL", "http://127.0.0.1:18090").rstrip("/")
    call = urllib.request.Request(
        url + "/v2/decide",
        data=json.dumps(request, allow_nan=False, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(call, timeout=1) as reply:
        data = reply.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("Tactical AI response exceeds budget")
    return json.loads(data)


def step(
    runtime, provider, stats_serializer, *, transport_call=None, forecast_options=None
):
    limits = dict(getattr(provider, "forecast_limits", {}))
    limits.update(forecast_options or {})
    if set(limits) - {"max_previews", "budget_ms", "depth"}:
        raise ValueError("Unknown native forecast limit")
    request = build_request(runtime, provider, **limits)
    response = (transport if transport_call is None else transport_call)(request)
    action = validate_response(runtime, request, response, provider)
    diagnostic = dict(
        action=action,
        intent=response["decision"].get("intent"),
        score=response["decision"].get("score"),
        requestId=request["requestId"],
        fightInstanceId=request["fightInstanceId"],
        sourceRevision=request["stateRevision"],
        policyVersion=request["policyVersion"],
        score_components=response["decision"].get("score_components", {}),
        producer=request["producerTrace"],
        trace=response.get("trace", {}),
    )
    if action["type"] == "end_turn":
        return [], diagnostic
    return provider.commit(runtime, action, stats_serializer), diagnostic


def run_turn(
    runtime,
    provider,
    stats_serializer,
    *,
    transport_call=None,
    max_actions=12,
    budget_seconds=3
):
    """Yield one committed FIFO delivery; resume/replan after caller sends it.

    13510 is a turn barrier, never fabricated as a per-action ACK.
    """
    actor_id, turn = runtime.fight.current.id, runtime.fight.turn_id
    deadline = time.monotonic() + budget_seconds
    end_diagnostic = dict(action=dict(type="end_turn"))
    for _ in range(max_actions):
        if runtime.awaiting_ack is not None or runtime.pending:
            return
        if (
            runtime.fight.phase != "active"
            or runtime.fight.current.id != actor_id
            or runtime.fight.turn_id != turn
        ):
            return
        if time.monotonic() >= deadline:
            end_diagnostic["reason"] = "Native turn computation budget reached"
            break
        try:
            packets, diagnostic = step(
                runtime, provider, stats_serializer, transport_call=transport_call
            )
        except (ValueError, OSError, TypeError) as error:
            failure = dict(
                reason="Tactical AI unavailable or unsupported: "
                + type(error).__name__,
                detail=str(error)[:160],
            )
            end_diagnostic.update(failure)
            yield [], failure
            break
        if not packets:
            end_diagnostic = dict(diagnostic, action=dict(type="end_turn"))
            break
        end_diagnostic = dict(
            diagnostic,
            action=dict(type="end_turn"),
            reason="Native turn action limit reached",
        )
        yield packets, diagnostic
    if (
        runtime.fight.phase == "active"
        and runtime.fight.current.id == actor_id
        and runtime.fight.turn_id == turn
        and runtime.awaiting_ack is None
        and not runtime.pending
    ):
        yield runtime.end_server_turn(actor_id, turn), end_diagnostic
