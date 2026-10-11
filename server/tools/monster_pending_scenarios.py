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
