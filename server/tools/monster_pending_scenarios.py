"""Declarative, replayable native prerequisites for monster validation.

Recipes only construct ordinary native companions or commit owned spells. They
never assign states, resources or encounter properties to make a cast legal.
"""


def scenario_recipes(reference, spell):
    """Return bounded native preparations; absence never authorizes a bypass."""
    from monster_class_buff_scenarios import encounter_buff_recipe

    buff = encounter_buff_recipe(reference, spell)
    if buff is not None:
        return [buff]
    if (reference, spell) == (2601, 3835):
        return [
            dict(
                kind="owned_spell_sequence",
                actions=[dict(spell_id=3800, target="caster", next_turn=True)],
            )
        ]
    if (reference, spell) == (3907, 5599):
        return [dict(kind="native_opponent", opponent=dict(reference=3907, level=1))]
    if (reference, spell) == (5361, 7527):
        return [
            dict(
                kind="native_opponent",
                opponent=dict(reference=1987, level=95, team=1),
                required_opponent_states=[7318],
            )
        ]
    return []


def prepare_scenario(fight, character, monsters, deck, *, caster_id=-200, recipe):
    """Replay a recipe using normal ownership, eligibility and commit paths."""
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.monsters import native_abilities

    if recipe.get("kind") not in ("native_opponent", "owned_spell_sequence"):
        raise ValueError("Unknown native preparation recipe")
    advance_to(fight, caster_id)
    preparations = []
    provider = NativeProvider(character, monsters, deck)

    def serialize(actor, state):
        keywords = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **keywords)
        return actual_monster_actor_stats(
            monsters[actor.id], actor, state.id, **keywords
        )

    if recipe["kind"] == "native_opponent":
        descriptor = recipe["opponent"]
        opponents = [
            actor
            for actor in fight.actors.values()
            if actor.team == descriptor.get("team", 0)
            and actor.id != caster_id
            and actor.id in monsters
            and monsters[actor.id]["ref"] == descriptor["reference"]
            and actor.effective_level == descriptor["level"]
        ]
        if not opponents:
            raise ValueError("Recipe native companion was not initialized")
        for state_id in recipe.get("required_opponent_states", ()):
            if not any(
                actor.state_ledger is not None
                and any(
                    entry.reference == state_id for entry in actor.state_ledger.entries
                )
                for actor in opponents
            ):
                raise ValueError(
                    "Recipe companion lacks its required native initial state"
                )
    for step in recipe.get("actions", ()):
        if step.get("target") != "caster":
            raise ValueError("Unsupported native preparation target")
        spell_id = step["spell_id"]
        abilities = native_abilities(
            monsters[caster_id]["ref"], fight.actors[caster_id].effective_level
        )
        owned = next((a for a in abilities if a["spell_id"] == spell_id), None)
        if owned is None:
            raise ValueError("Preparation spell is not natively owned")
        actor = fight.actors[caster_id]
        action = dict(
            type="cast",
            spellId=spell_id,
            level=owned["spell_level"],
            target=list(actor.position),
            targetId=caster_id,
        )
        packets = provider.commit(RuntimeMessages(fight), action, serialize)
        if not packets:
            raise ValueError("Native preparation cast delivered no packets")
        preparations.append(
            dict(
                spell_id=spell_id,
                spell_level=owned["spell_level"],
                packets=len(packets),
                turn_id=fight.turn_id,
            )
        )
        if step.get("next_turn"):
            finish_current_turn(fight)
            advance_to(fight, caster_id)
    return dict(
        schema="native-monster-scenario-v1",
        kind=recipe["kind"],
        preparations=preparations,
        caster_turn_id=fight.turn_id,
    )


def bounded_empty_targets(
    fight,
    source,
    minimum,
    maximum,
    *,
    limit=12,
    caster_id=-200,
    prefer_linear=False,
    prefer_diagonal=False
):
    """Enumerate real empty walkable cells, prioritizing hostile proximity.

    These are candidates, never an eligibility certificate. The native casting
    path still owns line of sight, QI collision, criteria and effect selection.
    Exclude every actual fighter and serialized obstacle, including allies and
    companions, rather than assuming only the primary enemy occupies the arena.
    """
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or type(limit) is not int
        or minimum < 0
        or maximum < minimum
        or not 1 <= limit <= 256
        or type(prefer_linear) is not bool
        or type(prefer_diagonal) is not bool
    ):
        raise ValueError("Invalid bounded native empty-cell search")
    occupied = {tuple(actor.position) for actor in fight.actors.values()}
    obstacles = {tuple(cell) for cell in getattr(fight, "native_obstacle_cells", ())}
    caster = fight.actors[caster_id]
    hostiles = [
        tuple(actor.position)
        for actor in fight.actors.values()
        if actor.team != caster.team and actor.hp > 0
    ]

    def distance(left, right):
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    candidates = [
        tuple(cell)
        for cell in fight.walkable
        if tuple(cell) not in occupied
        and tuple(cell) not in obstacles
        and minimum <= distance(source, cell) <= maximum
    ]
    return sorted(
        set(candidates),
        key=lambda cell: (
            int(prefer_linear and cell[0] != source[0] and cell[1] != source[1]),
            int(
                prefer_diagonal and abs(cell[0] - source[0]) != abs(cell[1] - source[1])
            ),
            min((distance(cell, enemy) for enemy in hostiles), default=0),
            distance(source, cell),
            cell,
        ),
    )[:limit]


def effect_search_envelope(effects, roots, casting_maximum):
    """Bound advisory enemy placement by audited native XY effect extents.

    This changes only fixture search positions. Spell target range and every
    runtime eligibility guard remain unchanged. Unknown geometry contributes
    no inferred extension; the final search stays bounded to twelve cells.
    """
    from wakfu_server.combat_area_geometry import native_area_shape

    if type(casting_maximum) is not int or casting_maximum < 0:
        raise ValueError("Invalid native casting maximum")
    radius, seen, pending = 0, set(), list(roots)
    while pending:
        reference = str(pending.pop())
        if reference in seen:
            continue
        seen.add(reference)
        effect = effects.get(reference)
        if effect is None:
            continue
        shape = native_area_shape(effect)
        if shape is not None:
            points, _ = shape
            radius = max(radius, max((abs(x) + abs(y) for x, y in points), default=0))
        pending.extend(effect.get("children", ()))
    return min(12, casting_maximum + radius)


def enemy_search_envelope(spell, spell_level, casting_maximum):
    """Read the exact compiled NPC graph used by native spell transactions."""
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.combat_npc_attack import npc_runtime_catalog

    casting = catalog().get(str(spell))
    if casting is None or not 1 <= spell_level <= len(casting["levels"]):
        raise ValueError("Missing native casting roots for enemy scene search")
    roots = casting["levels"][spell_level - 1][2]
    return effect_search_envelope(npc_runtime_catalog().effects, roots, casting_maximum)


def discover_owned_state_recipes(abilities, required_states, document, *, limit=4):
    """Propose bounded self-cast preparations from actual owned state roots.

    This is structural discovery, never proof that the state was applied. The
    ordinary preparation commit still checks eligibility, cost, probability,
    targeting, timing and packet delivery. Only constant state IDs on direct,
    unconditional family-304 roots of zero-range owned spells are considered.
    """
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Invalid native state preparation recipe limit")
    states = set(required_states)
    if any(type(state) is not int or state <= 0 for state in states):
        raise ValueError("Invalid required native preparation state")
    if not states:
        return []
    recipes = []
    from collections import ChainMap

    effects = ChainMap(
        document.get("effects", {}), document.get("baseline_effects", {})
    )
    for ability in abilities:
        spell, level = ability["spell_id"], ability["spell_level"]
        record = document.get("spells", {}).get(str(spell))
        if (
            record is None
            or type(level) is not int
            or not 1 <= level <= len(record["levels"])
        ):
            continue
        minimum, maximum, roots = record["levels"][level - 1]
        if minimum != 0 or maximum != 0:
            continue
        produced = set()
        pending, seen = list(roots), set()
        while pending and len(seen) < 128:
            root = str(pending.pop())
            if root in seen:
                continue
            seen.add(root)
            effect = effects.get(root, {})
            if effect.get("effect_class") in (330, 349) and not effect.get("criteria"):
                pending.extend(effect.get("children", ()))
            parameters = effect.get("parameters", [])
            selector = effect.get("native_target_selector", {})
            if (
                effect.get("effect_class") == 304
                and effect.get("variant") == 0
                and not effect.get("criteria")
                and len(parameters) >= 2
                and parameters[1] == 0
                and type(parameters[0]) in (int, float)
                and float(parameters[0]).is_integer()
                and selector.get("mask") == 1
            ):
                produced.add(int(parameters[0]))
        if not states.issubset(produced):
            continue
        for next_turn in (False, True):
            recipes.append(
                dict(
                    kind="owned_spell_sequence",
                    actions=[
                        dict(spell_id=spell, target="caster", next_turn=next_turn)
                    ],
                    discovered_required_states=sorted(states),
                    discovery="owned_direct_self_state_root_v1",
                )
            )
            if len(recipes) >= limit:
                return recipes
    return recipes


def simple_required_caster_states(criterion):
    """Extract necessary positive caster states through native AND syntax only."""
    import ast
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return []
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return []
    nodes = list(ast.walk(root))
    if len(nodes) > 256 or any(
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.Not)
        or isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        for node in nodes
    ):
        return []

    def necessary(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return set().union(*(necessary(value) for value in node.values))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "HasState"
            and not node.keywords
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
            and node.args[0].value > 0
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "caster"
        ):
            return {node.args[0].value}
        return set()

    return sorted(necessary(root))


def recovery_owned_state_recipes(reference, level, spell, criterion):
    """Discover preparations only for a conservatively recognized criterion."""
    states = simple_required_caster_states(criterion)
    if not states:
        return []
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_npc_attack import npc_spell_catalog

    abilities = [
        ability
        for ability in native_abilities(reference, level)
        if ability["spell_id"] != spell
    ]
    return discover_owned_state_recipes(abilities, states, npc_spell_catalog(), limit=4)


def required_native_target_identity(criterion):
    """Extract positive target predicates only from a strict AND expression."""
    import ast
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return None
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return None
    nodes = list(ast.walk(root))
    if len(nodes) > 256 or any(
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.Not)
        or isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        for node in nodes
    ):
        return None
    states, breeds = set(), set()

    def visit(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            for value in node.values:
                visit(value)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
            and len(node.args) == 2
            and all(isinstance(arg, ast.Constant) for arg in node.args)
        ):
            left, right = (arg.value for arg in node.args)
            if (
                node.func.id == "HasState"
                and type(left) is int
                and left > 0
                and right == "target"
            ):
                states.add(left)
            elif (
                node.func.id == "IsBreedId"
                and left == "target"
                and type(right) is int
                and right > 0
            ):
                breeds.add(right)

    visit(root)
    if not states and not breeds or len(breeds) > 1:
        return None
    return dict(states=sorted(states), breed=next(iter(breeds), None))


def discover_native_opponent_recipes(criterion, monsters, initial_profiles, *, limit=4):
    """Suggest actual native identities; initialization and casting remain proof.

    Descriptor endpoints are native levels, never synthesized statistics. State
    membership merely narrows candidates: prepare_scenario checks their actual
    initialized state ledger before the ordinary spell transaction is attempted.
    """
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Invalid native opponent recipe limit")
    requirement = required_native_target_identity(criterion)
    if requirement is None:
        return []
    from wakfu_server.combat_summon_initial_states import initial_state_plan

    recipes = []
    for monster in sorted(monsters, key=lambda row: row["ref"]):
        reference = monster["ref"]
        if requirement["breed"] is not None and requirement["breed"] != reference:
            continue
        minimum, maximum = monster.get("min_level"), monster.get("max_level")
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or not 1 <= minimum <= maximum <= 32767
        ):
            continue
        raw = initial_profiles.get(str(reference))
        if raw is None:
            continue
        for level in sorted({minimum, maximum}):
            try:
                states = {
                    state.state_id
                    for state in initial_state_plan(raw, level)
                    if state.level > 0
                }
            except ValueError:
                continue
            if not set(requirement["states"]).issubset(states):
                continue
            recipes.append(
                dict(
                    kind="native_opponent",
                    opponent=dict(reference=reference, level=level),
                    required_opponent_states=requirement["states"],
                    discovery="positive_native_target_identity_v1",
                )
            )
            if len(recipes) >= limit:
                return recipes
    return recipes


def recovery_native_opponent_recipes(reference, level, spell, criterion):
    """Use only native roster records and imported initialization authorities."""
    if required_native_target_identity(criterion) is None:
        return []
    from wakfu_server.monsters import REFERENCES
    from wakfu_server.combat_summon_initial_states import native_initial_states

    return discover_native_opponent_recipes(
        criterion,
        REFERENCES.values(),
        {
            key: row["initial_state_triples"]
            for key, row in native_initial_states().items()
        },
        limit=4,
    )
