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


def requires_non_enemy_target(criterion):
    """Recognize a required native non-enemy conjunct, never an OR branch.

    This only requests an ordinary witness scene. It does not certify that an
    ally satisfies any remaining criterion or effect selector.
    """
    import ast

    if not isinstance(criterion, str) or not criterion.strip():
        return False
    try:
        expression = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except (SyntaxError, ValueError):
        return False

    def required(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return any(required(value) for value in node.values)
        return (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Not)
            and isinstance(node.operand, ast.Call)
            and isinstance(node.operand.func, ast.Name)
            and node.operand.func.id == "IsEnnemy"
            and not node.operand.args
            and not node.operand.keywords
        )

    return required(expression)


def native_ko_ally_recipe(criterion):
    """Suggest owned hostile KO preparation only for required allied corpses."""
    import ast

    if not requires_non_enemy_target(criterion):
        return None
    try:
        expression = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except (SyntaxError, ValueError):
        return None

    def required(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return any(required(value) for value in node.values)
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "IsOffPlay"
            and not node.keywords
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "target"
        )

    return "knocked_out_ally" if required(expression) else None


def native_ally_recipe(
    reference, level, capability, *, criterion=None, root_effects=()
):
    """Suggest an ordinary same-species ally for supportive spell witnesses.

    This grants no resources or states: the existing native constructor and
    preparation path must initialize the additional participant normally.
    """
    from wakfu_server.combat_effect_targets import native_selector_policy

    ally_only_root = False
    for effect in root_effects:
        relations = native_selector_policy(effect)["relations"]
        if "ally" in relations and "enemy" not in relations:
            ally_only_root = True
    if (
        not set(capability.get("tags", ())) & {"heal", "armor", "buff"}
        and not requires_non_enemy_target(criterion)
        and not ally_only_root
    ):
        return None
    if (
        type(reference) is not int
        or reference <= 0
        or type(level) is not int
        or level <= 0
    ):
        raise ValueError("Invalid native ally descriptor")
    recipe = dict(
        kind="native_opponent",
        opponent=dict(reference=reference, level=level, team=1),
        discovery="ordinary_same_species_ally_v1",
    )
    minimum, maximum = capability.get("minimum"), capability.get("maximum")
    if type(minimum) is int and type(maximum) is int and 1 <= minimum <= maximum <= 64:
        recipe["native_recipient_range"] = [minimum, maximum]
    return recipe


def refresh_native_actor_targets(fight, targets):
    """Refresh moved live actors' cells without changing target identity/order."""
    result = []
    for cell, identity in targets:
        actor = fight.actors.get(identity)
        if actor is not None and actor.hp > 0:
            cell = tuple(actor.position)
        result.append((cell, identity))
    return result


def additional_native_actor_targets(fight, existing):
    """Include actual living companions omitted by the primary target pair."""
    present = {identity for _, identity in existing if identity is not None}
    return [
        (tuple(actor.position), identity)
        for identity, actor in sorted(fight.actors.items())
        if identity not in present and actor.hp > 0
    ]


def prepare_scenario(fight, character, monsters, deck, *, caster_id=-200, recipe):
    """Replay a recipe using normal ownership, eligibility and commit paths."""
    from owned_target_state_wounded import (
        DISCOVERY as TARGET_DISCOVERY,
        prepare as prepare_target,
    )

    if recipe.get("discovery") == TARGET_DISCOVERY:
        return prepare_target(
            fight, character, monsters, deck, recipe=recipe, caster_id=caster_id
        )
    from initial_subscription_preparation import (
        DISCOVERY as SUBSCRIPTION_DISCOVERY,
        prepare as prepare_subscription,
    )

    if recipe.get("discovery") == SUBSCRIPTION_DISCOVERY:
        return prepare_subscription(
            fight, character, monsters, deck, recipe=recipe, caster_id=caster_id
        )
    from wounded_caster_preparation import (
        DISCOVERY as HP_DISCOVERY,
        prepare as prepare_hp,
    )

    if recipe.get("discovery") == HP_DISCOVERY:
        return prepare_hp(
            fight, character, monsters, deck, recipe=recipe, caster_id=caster_id
        )
    from external_owned_area_preparation import DISCOVERY, prepare

    if recipe.get("discovery") == DISCOVERY:
        return prepare(
            fight, character, monsters, deck, recipe=recipe, caster_id=caster_id
        )
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.monsters import native_abilities

    if recipe.get("kind") not in ("native_opponent", "owned_spell_sequence"):
        raise ValueError("Unknown native preparation recipe")
    advance_to(fight, caster_id)
    preparations = []
    if recipe.get("discovery") == "owned_conditional_self_state_v1":
        from conditional_owned_state import guarded_native_provider

        Provider = guarded_native_provider(NativeProvider, recipe, caster_id)
    elif recipe.get("discovery") == "owned_retained_effect_marker_v1":
        from owned_effect_marker import guard_provider

        Provider = guard_provider(NativeProvider, recipe, caster_id)
    else:
        Provider = NativeProvider
    provider = Provider(character, monsters, deck)

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
    if recipe.get("discovery") == "native_zero_mp_lifecycle_v1":
        if recipe.get("actions") != [] or recipe.get("prepare_zero_mp") is not True:
            raise ValueError("Native zero-MP lifecycle recipe changed")
        from owned_state_movement import (
            spend_native_movement,
            bind_owned_movement_authority,
        )

        bind_owned_movement_authority(fight, character, monsters, deck)
        proof = spend_native_movement(
            fight,
            caster_id,
            NativeProvider(character, monsters, deck),
            RuntimeMessages,
            serialize,
        )
        preparations.append(
            dict(native_movement_preparation_proof=proof, turn_id=fight.turn_id)
        )
    producer_movement = None
    if recipe.get("native_producer_target_id") is not None:
        from owned_state_stack import approach_native_producer_target
        from owned_state_movement import bind_owned_movement_authority

        bind_owned_movement_authority(fight, character, monsters, deck)
        producer_movement = approach_native_producer_target(
            fight,
            caster_id,
            recipe["native_producer_target_id"],
            recipe["native_producer_range"],
            NativeProvider(character, monsters, deck),
            RuntimeMessages,
            serialize,
        )
        preparations.append(dict(native_producer_movement=producer_movement))
    for step in recipe.get("actions", ()):
        if step.get("target") not in ("caster", "native_opponent", "player"):
            raise ValueError("Unsupported native preparation target")
        if (
            step.get("target") in ("native_opponent", "player")
            and recipe.get("discovery") != "owned_conditional_self_state_v1"
        ):
            raise ValueError(
                "Native companion state producer lacks guarded transaction"
            )
        spell_id = step["spell_id"]
        abilities = native_abilities(
            monsters[caster_id]["ref"], fight.actors[caster_id].effective_level
        )
        owned = next((a for a in abilities if a["spell_id"] == spell_id), None)
        if owned is None:
            raise ValueError("Preparation spell is not natively owned")
        actor = fight.actors[caster_id]
        movement_proof = None
        if step.get("prepare_zero_mp"):
            if recipe.get("discovery") != "owned_conditional_self_state_v1":
                raise ValueError(
                    "Native MP preparation requires guarded owned producer"
                )
            from owned_state_movement import (
                spend_native_movement,
                bind_owned_movement_authority,
            )

            bind_owned_movement_authority(fight, character, monsters, deck)
            movement_proof = spend_native_movement(
                fight,
                caster_id,
                NativeProvider(character, monsters, deck),
                RuntimeMessages,
                serialize,
            )
        action = dict(
            type="cast",
            spellId=spell_id,
            level=owned["spell_level"],
            target=list(
                fight.actors[7].position
                if step.get("target") == "player"
                else fight.actors[-201].position
                if step.get("target") == "native_opponent"
                else actor.position
            ),
            targetId=7
            if step.get("target") == "player"
            else -201
            if step.get("target") == "native_opponent"
            else caster_id,
        )
        base_costs = recipe.get("native_producer_base_costs")
        if (
            base_costs is not None
            and recipe.get("native_producer_target_id") is not None
        ):
            from owned_state_stack import ensure_native_producer_resources

            resource_proof = ensure_native_producer_resources(
                fight, caster_id, base_costs
            )
            preparations.append(
                dict(native_producer_resource_preparation=resource_proof)
            )
        try:
            packets = provider.commit(RuntimeMessages(fight), action, serialize)
        except ValueError as exc:
            if recipe.get("discovery") != "owned_conditional_self_state_v1":
                raise
            actor = fight.actors[caster_id]
            ledger = getattr(actor, "state_ledger", None)
            grades = (
                []
                if ledger is None
                else [(e.reference, e.level, e.uid) for e in ledger.entries]
            )
            raise ValueError(
                f"{exc}; owned producer spell={spell_id} AP={actor.ap} MP={actor.mp} WP={actor.effect_stats[4]} state_grades={grades}"
            ) from exc
        if not packets:
            raise ValueError("Native preparation cast delivered no packets")
        state_proof = None
        if recipe.get("discovery") == "owned_conditional_self_state_v1":
            from conditional_owned_state import verify_committed_states

            state_proof = verify_committed_states(
                fight, provider.native_state_preparation_proof, caster_id
            )
        marker_proof = None
        if recipe.get("discovery") == "owned_retained_effect_marker_v1":
            from owned_effect_marker import verify_committed

            marker_proof = verify_committed(
                fight, provider.native_marker_preparation_proof, caster_id
            )
        preparations.append(
            dict(
                spell_id=spell_id,
                spell_level=owned["spell_level"],
                packets=len(packets),
                conditional_native_state_proof=state_proof,
                native_effect_marker_proof=marker_proof,
                native_movement_preparation_proof=movement_proof,
                turn_id=fight.turn_id,
            )
        )
        if step.get("next_turn"):
            finish_current_turn(fight)
            advance_to(fight, caster_id)
        if state_proof is not None:
            verify_committed_states(fight, state_proof, caster_id)
        if marker_proof is not None:
            from owned_effect_marker import verify_committed

            verify_committed(fight, marker_proof, caster_id)
    if producer_movement is not None:
        from owned_state_stack import restore_native_producer_position

        preparations.append(
            dict(
                native_producer_return=restore_native_producer_position(
                    fight,
                    caster_id,
                    producer_movement,
                    NativeProvider(character, monsters, deck),
                    RuntimeMessages,
                    serialize,
                )
            )
        )
    requirements = recipe.get("required_state_levels", {})
    if requirements:
        entries = getattr(fight.actors[caster_id], "state_ledger", None)
        if entries is None or any(
            not any(
                e.reference == state
                and e.target_id == caster_id
                and e.caster_id == caster_id
                and e.level >= grade
                for e in entries.entries
            )
            for state, grade in __import__(
                "owned_state_stack", fromlist=["state_requirement_items"]
            ).state_requirement_items(requirements)
        ):
            raise ValueError(
                "Actual owned state sequence did not reach required native grade"
            )
    return dict(
        schema="native-monster-scenario-v1",
        kind=recipe["kind"],
        preparations=preparations,
        caster_turn_id=fight.turn_id,
    )


from monster_target_cells import native_empty_target_predicate


def bounded_empty_targets(
    fight,
    source,
    minimum,
    maximum,
    *,
    limit=12,
    caster_id=-200,
    prefer_linear=False,
    prefer_diagonal=False,
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
    empty = native_empty_target_predicate(fight)
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
        if empty(cell) and minimum <= distance(source, cell) <= maximum
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
        if shape is None:
            from wakfu_server.combat_effect_targets import area_offsets

            try:
                shape = (area_offsets(effect), True)
            except ValueError:
                pass
        if shape is not None:
            points, _ = shape
            radius = max(radius, max((abs(x) + abs(y) for x, y in points), default=0))
        pending.extend(effect.get("children", ()))
    return min(12, casting_maximum + radius)


def enemy_search_envelope(spell, spell_level, casting_maximum):
    """Read the exact compiled NPC graph used by native spell transactions."""
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.combat_npc_attack import npc_runtime_catalog

    from native_scene_casting import native_scene_casting_row

    roots = native_scene_casting_row(spell, spell_level, catalog())[2]
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
    if sum(1 for _ in ast.walk(root)) > 256:
        return []

    def necessary(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return set().union(*(necessary(value) for value in node.values))
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            groups = [necessary(value) for value in node.values]
            return set.intersection(*groups) if groups else set()
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
    from owned_state_stack import required_caster_state_levels

    requirements = required_caster_state_levels(criterion)
    states = sorted(requirements)
    if not states:
        from owned_state_movement import requires_zero_mp_branch

        if requires_zero_mp_branch(criterion):
            return [
                dict(
                    kind="owned_spell_sequence",
                    actions=[],
                    discovery="native_zero_mp_lifecycle_v1",
                    prepare_zero_mp=True,
                )
            ]
        return []
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_npc_attack import npc_spell_catalog

    abilities = [
        ability
        for ability in native_abilities(reference, level)
        if ability["spell_id"] != spell
    ]
    from conditional_owned_state import discover_conditional_owned_state_recipes

    document = npc_spell_catalog()
    from wakfu_server.combat_native_spell_casting import catalog as casting_catalog
    from owned_target_state_wounded import (
        target_requirements,
        recipes as target_recipes,
    )

    if target_requirements(criterion) is not None:
        from owned_state_stack import native_state_definitions

        compound = target_recipes(
            reference,
            level,
            spell,
            criterion,
            native_abilities(reference, level),
            document,
            casting_catalog(),
            native_state_definitions(),
        )
        if compound:
            return compound

    conditional = discover_conditional_owned_state_recipes(
        abilities,
        states,
        document,
        limit=4,
        casting=casting_catalog() if abilities else {},
        required_levels=requirements,
        state_definitions=__import__(
            "owned_state_stack", fromlist=["native_state_definitions"]
        ).native_state_definitions()
        if any(grade > 1 for grade in requirements.values())
        else {},
        companion_recipes=lambda producer_criterion: recovery_native_opponent_recipes(
            reference, level, spell, producer_criterion
        )
        or (
            [
                dict(
                    kind="native_opponent",
                    opponent=dict(reference=reference, level=level, team=0),
                    discovery="ordinary_same_species_enemy_state_recipient_v1",
                )
            ]
            if any(grade > 1 for grade in requirements.values())
            and producer_criterion.strip() in ("", "IsEnnemy()", "IsEnemy()")
            else []
        ),
    )
    return (
        conditional
        + (
            discover_owned_state_recipes(abilities, states, document, limit=4)
            if all(v == 1 for v in requirements.values())
            else []
        )
    )[:4]


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
    criteria = [criterion]
    if required_native_target_identity(criterion) is None:
        from native_target_identity_choices import positive_target_breed_choices

        criteria = [
            'IsBreedId("target", ' + str(breed) + ")"
            for breed in positive_target_breed_choices(criterion)
        ]
        if not criteria:
            return []
    from wakfu_server.monsters import REFERENCES
    from wakfu_server.combat_summon_initial_states import native_initial_states

    profiles = {
        key: row["initial_state_triples"]
        for key, row in native_initial_states().items()
    }
    recipes = []
    for alternative in criteria:
        for recipe in discover_native_opponent_recipes(
            alternative, REFERENCES.values(), profiles, limit=4
        ):
            if recipe not in recipes:
                recipes.append(recipe)
                if len(recipes) == 4:
                    return recipes
    return recipes
