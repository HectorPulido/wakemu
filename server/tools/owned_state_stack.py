"""Necessary native caster-state grades and bounded genuine producer casts."""
import ast
import math


def required_caster_state_levels(criterion, *, maximum_grade=16):
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if type(maximum_grade) is not int or not 1 <= maximum_grade <= 32767:
        raise ValueError("Invalid native state-grade bound")

    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return {}
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return {}
    if sum(1 for _ in ast.walk(root)) > 256:
        return {}

    def visit(node):
        if isinstance(node, ast.BoolOp):
            rows = [visit(v) for v in node.values]
            keys = set().union(*rows)
            if isinstance(node.op, ast.And):
                return {k: max(r.get(k, 0) for r in rows) for k in keys}
            if isinstance(node.op, ast.Or):
                return {
                    k: min(r[k] for r in rows)
                    for k in keys
                    if all(k in r for r in rows)
                }
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            args = node.args
            name = node.func.id
            if name == "HasState" and len(args) == 2:
                args = [args[0], ast.Constant(value=1), args[1]]
            elif name != "HasStateFromLevel" or len(args) != 3:
                return {}
            if all(isinstance(a, ast.Constant) for a in args):
                state, grade, selector = [a.value for a in args]
                if (
                    type(state) is int
                    and state > 0
                    and type(grade) is int
                    and 1 <= grade <= maximum_grade
                    and selector == "caster"
                ):
                    return {state: grade}
        return {}

    return visit(root)


def bounded_repeat_count(paths, requirements, definitions, *, bound=8):
    counts = []
    for state, threshold in requirements.items():
        row = definitions.get(str(state))
        producers = [p for p in paths if p["state"] == state]
        if (
            row is None
            or not producers
            or type(row.get("maximum_level")) is not int
            or threshold > row["maximum_level"]
        ):
            return None
        # Multiple applications in one spell can depend on different criteria.
        # Use only a single unconditional, constant positive self-state effect.
        if len(producers) != 1 or producers[0]["criteria"]:
            return None
        gain = producers[0].get("constant_state_gain")
        if type(gain) is not int or gain <= 0:
            return None
        if threshold > gain and row.get("additive") is not True:
            return None
        counts.append(math.ceil(threshold / gain))
    count = max(counts, default=0)
    return count if 1 <= count <= bound else None


def native_state_definitions():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return native_catalog.load(DATA_ROOT / "combat-state-definitions.json")["states"]


def native_path(fight, caster_id, destination, *, limit=12):
    """Bounded directed walkable path; runtime commit remains authoritative."""
    from collections import deque

    start = tuple(fight.actors[caster_id].position)
    occupied = {
        tuple(a.position)
        for uid, a in fight.actors.items()
        if uid != caster_id and a.hp > 0
    }
    cells = set(map(tuple, fight.walkable)) - occupied
    queue = deque([(start, [])])
    seen = {start}
    edges = getattr(fight, "edges", None)
    while queue:
        cell, path = queue.popleft()
        if destination(cell):
            return path
        if len(path) >= limit:
            continue
        x, y, z = cell
        for next_cell in sorted(
            ((x - 1, y, z), (x + 1, y, z), (x, y - 1, z), (x, y + 1, z))
        ):
            if next_cell in seen or next_cell not in cells:
                continue
            if edges is not None and (cell, next_cell) not in edges:
                continue
            seen.add(next_cell)
            queue.append((next_cell, path + [next_cell]))
    raise ValueError("No bounded real native producer movement path")


def native_segment_cost(fight, caster_id, path):
    from wakfu_server.combat_rail_movement import movement_cost
    from wakfu_server.combat_tackle_movement import movement_tackle_cost

    actor = fight.actors[caster_id]
    movement, _ = movement_cost(fight, actor, path)
    ap, mp = movement_tackle_cost(fight, actor, path)
    return ap, movement + mp


def commit_native_path(fight, caster_id, path, provider, runtime_factory, serialize):
    """Commit affordable real path segments, including actual native tackle."""
    from monster_spell_scenarios import finish_current_turn, advance_to

    remaining = list(path)
    segments = []
    turns = 0
    if len(remaining) > 12:
        raise ValueError("Unbounded native movement sequence")
    while remaining:
        actor = fight.actors[caster_id]
        choice = None
        for count in range(len(remaining), 0, -1):
            ap_cost, mp_cost = native_segment_cost(fight, caster_id, remaining[:count])
            if ap_cost <= actor.ap and mp_cost <= actor.mp:
                choice = (remaining[:count], ap_cost, mp_cost)
                break
        if choice is None:
            if turns >= 12:
                raise ValueError("Native producer movement exceeded normal turn bound")
            finish_current_turn(fight)
            advance_to(fight, caster_id)
            turns += 1
            actor = fight.actors[caster_id]
            for count in range(len(remaining), 0, -1):
                ap_cost, mp_cost = native_segment_cost(
                    fight, caster_id, remaining[:count]
                )
                if ap_cost <= actor.ap and mp_cost <= actor.mp:
                    choice = (remaining[:count], ap_cost, mp_cost)
                    break
            if choice is None:
                raise ValueError(
                    "Native maxima cannot afford one actual movement segment"
                )
        segment, ap_cost, mp_cost = choice
        before_ap, before_mp = actor.ap, actor.mp
        packets = provider.commit(
            runtime_factory(fight),
            {"type": "move", "path": [list(c) for c in segment]},
            serialize,
        )
        actor = fight.actors[caster_id]
        if (
            not packets
            or tuple(actor.position) != tuple(segment[-1])
            or actor.mp >= before_mp
            or actor.hp <= 0
        ):
            raise ValueError(
                "Actual producer movement did not commit authoritative position/MP"
            )
        segments.append(
            {
                "path": [list(c) for c in segment],
                "packets": len(packets),
                "initial_ap": before_ap,
                "final_ap": actor.ap,
                "initial_mp": before_mp,
                "final_mp": actor.mp,
                "native_tackle_inclusive_cost": {"ap": ap_cost, "mp": mp_cost},
            }
        )
        remaining = remaining[len(segment) :]
    return {
        "path": [list(c) for c in path],
        "packets": sum(s["packets"] for s in segments),
        "segments": segments,
        "normal_turns": turns,
    }


def approach_native_producer_target(
    fight, caster_id, target_id, bounds, provider, runtime_factory, serialize
):
    minimum, maximum = bounds
    if any(type(v) is not int for v in bounds) or not 0 <= minimum <= maximum <= 12:
        raise ValueError("Unbounded native producer range")
    origin = tuple(fight.actors[caster_id].position)
    target = fight.actors[target_id]
    if target.hp <= 0 or target.team == fight.actors[caster_id].team:
        raise ValueError("Native producer requires actual living hostile recipient")
    target_cell = tuple(target.position)
    path = native_path(
        fight,
        caster_id,
        lambda cell: cell[2] == target_cell[2]
        and minimum
        <= abs(cell[0] - target_cell[0]) + abs(cell[1] - target_cell[1])
        <= maximum,
    )
    proof = commit_native_path(
        fight, caster_id, path, provider, runtime_factory, serialize
    )
    proof.update(
        origin=list(origin), target_id=target_id, target_position=list(target_cell)
    )
    return proof


def restore_native_producer_position(
    fight, caster_id, proof, provider, runtime_factory, serialize
):
    origin = tuple(proof["origin"])
    path = native_path(fight, caster_id, lambda cell: cell == origin)
    return commit_native_path(
        fight, caster_id, path, provider, runtime_factory, serialize
    )


def ensure_native_producer_resources(fight, caster_id, base_costs):
    """Advance a real turn when actual AP/MP are below the source base cost."""
    from monster_spell_scenarios import finish_current_turn, advance_to

    if len(base_costs) != 3 or any(type(v) is not int or v < 0 for v in base_costs):
        raise ValueError("Missing exact native producer base costs")
    ap_cost, mp_cost, wp_cost = base_costs
    actor = fight.actors[caster_id]
    before = {"ap": actor.ap, "mp": actor.mp, "wp": actor.effect_stats[4]}
    advanced = False
    if actor.ap < ap_cost or actor.mp < mp_cost:
        finish_current_turn(fight)
        advance_to(fight, caster_id)
        advanced = True
        actor = fight.actors[caster_id]
    if actor.ap < ap_cost or actor.mp < mp_cost or actor.effect_stats[4] < wp_cost:
        raise ValueError(
            "Actual native resources cannot afford owned producer base cost"
        )
    return {
        "before": before,
        "after": {"ap": actor.ap, "mp": actor.mp, "wp": actor.effect_stats[4]},
        "normal_turn_advanced": advanced,
    }


def producer_spare_eligible(recipe, source, target, spare):
    """Keep the separately initialized player out of the native consumer ray."""
    if recipe.get("native_producer_target_id") is None:
        return True
    if spare[2] != source[2] or tuple(spare) in (tuple(source), tuple(target)):
        return False
    if abs(spare[0] - source[0]) + abs(spare[1] - source[1]) <= 1:
        return False
    return not (
        min(source[0], target[0]) <= spare[0] <= max(source[0], target[0])
        and min(source[1], target[1]) <= spare[1] <= max(source[1], target[1])
    )


def state_requirement_items(requirements):
    """Preserve integer state IDs across JSON recipe receipt round trips."""
    if not isinstance(requirements, dict) or len(requirements) > 16:
        raise ValueError("Invalid native required-state metadata")
    result = []
    for state, grade in requirements.items():
        if (
            isinstance(state, str)
            and state.isascii()
            and state.isdecimal()
            and str(int(state)) == state
        ):
            state = int(state)
        if (
            type(state) is not int
            or state <= 0
            or type(grade) is not int
            or not 1 <= grade <= 16
        ):
            raise ValueError("Invalid native required-state metadata")
        result.append((state, grade))
    return result
