"""Prepare native area prerequisites through real owned companion casts."""

DISCOVERY = "external_owned_area_native_commit_v1"


# Native-owned producer descriptors proved by ordinary constructor/cast receipts.
# These bound producer capabilities, never a consumer/species allowlist.
PRODUCERS = ((2078, 100, 3030), (2084, 104, 3040))
SUPPORTED_REFERENCES = frozenset((393, 394))


def necessary_area_references(criterion, mode):
    import ast

    if not isinstance(criterion, str) or mode not in ("caster_area", "target_area"):
        return set()
    try:
        tree = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except SyntaxError:
        return set()

    def visit(node):
        if isinstance(node, ast.BoolOp):
            groups = [visit(value) for value in node.values]
            if isinstance(node.op, ast.Or) and not all(groups):
                return set()
            return set().union(*groups)
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.keywords
        ):
            return set()
        if (
            mode == "target_area"
            and node.func.id == "IsSpecificArea"
            and len(node.args) == 1
        ):
            value = node.args[0]
        elif (
            mode == "caster_area"
            and node.func.id in ("IsOnSpecificEffectArea", "HasSpecificEffectArea")
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "caster"
        ):
            value = node.args[1]
        else:
            return set()
        return (
            {value.value}
            if isinstance(value, ast.Constant) and type(value.value) is int
            else set()
        )

    references = visit(tree)

    def supported(node):
        if isinstance(node, ast.BoolOp):
            values = [supported(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "IsSpecificArea" and len(node.args) == 1:
                value = node.args[0]
            elif (
                node.func.id in ("IsOnSpecificEffectArea", "HasSpecificEffectArea")
                and len(node.args) == 2
            ):
                value = node.args[1]
            else:
                return True
            return (
                isinstance(value, ast.Constant)
                and type(value.value) is int
                and value.value in SUPPORTED_REFERENCES
            )
        return True

    return references if supported(tree) else set()


def target_area_references(criterion):
    return sorted(
        necessary_area_references(criterion, "target_area") & SUPPORTED_REFERENCES
    )


def recipes(reference, spell, *, minimum=None, maximum=None, casting_record=None):
    if casting_record is None:
        from wakfu_server.combat_native_spell_casting import catalog

        casting_record = catalog().get(str(spell), {})
    criterion = casting_record.get("cast_criterion_raw", "")
    modes = [
        mode
        for mode in ("caster_area", "target_area")
        if necessary_area_references(criterion, mode) & SUPPORTED_REFERENCES
    ]
    # Mixed caster+target prerequisites need a separately proved compound scene.
    if (
        len(modes) != 1
        or type(minimum) is not int
        or type(maximum) is not int
        or not 0 <= minimum <= maximum
    ):
        return []
    mode = modes[0]
    return [
        dict(
            kind="native_opponent",
            discovery=DISCOVERY,
            opponent=dict(reference=producer, level=level, team=team),
            producer_spell=ability,
            required_area_references=[393, 394],
            area_mode=mode,
            qualification_spell=spell,
            target_minimum=minimum,
            target_maximum=maximum,
        )
        for producer, level, ability in PRODUCERS
        for team in (1, 0)
    ]


def adjacent(source, cell):
    return (
        cell[2] == source[2]
        and abs(cell[0] - source[0]) + abs(cell[1] - source[1]) == 1
    )


def new_area_proof(
    fight, before, producer_id, caster_id, contains, *, target_cell=None
):
    rows = getattr(fight, "native_effect_areas", {})
    actor = fight.actors[caster_id]
    if actor.hp <= 0:
        raise ValueError("External area preparation killed its recipient")
    proof = []
    for uid, row in rows.items():
        if uid in before or row.get("reference") not in (393, 394):
            continue
        if row.get("uid") != uid or row.get("owner_id") != producer_id:
            continue
        runners = [
            r
            for r in getattr(fight, "native_owned_area_effects", {}).values()
            if r.get("area_uid") == uid
            and r.get("effect_class") == 315
            and r.get("caster_id") == producer_id
            and r.get("executed") is True
            and row.get("effect_uid") == r.get("uid")
            and row.get("effect_class") == 315
            and type(row.get("effect_reference")) is int
            and row.get("target_id") == r.get("target_id")
            and (
                r.get("target_id") == caster_id
                or (
                    r.get("target_id") is None
                    and row.get("native_area_contract") == "faY"
                )
            )
        ]
        if len(runners) != 1:
            continue
        if contains(row, actor.position if target_cell is None else target_cell):
            proof.append(
                dict(
                    uid=uid,
                    reference=row["reference"],
                    owner_id=producer_id,
                    runner_uid=runners[0]["uid"],
                    cell=list(row["cell"]),
                    effect_reference=row["effect_reference"],
                    native_timer=None
                    if runners[0].get("timer") is None
                    else dict(runners[0]["timer"]),
                )
            )
    if not proof:
        raise ValueError("No newly committed native producer area covers caster")
    return proof


def verify_surviving_area(fight, proof, caster_id, contains, *, target_cell=None):
    rows = getattr(fight, "native_effect_areas", {})
    if fight.actors[caster_id].hp <= 0:
        raise ValueError("External area recipient did not survive lifecycle")
    for item in proof:
        row = rows.get(item["uid"])
        runner = getattr(fight, "native_owned_area_effects", {}).get(item["runner_uid"])
        if (
            runner is not None
            and runner.get("area_uid") == item["uid"]
            and runner.get("executed") is True
            and runner.get("timer") == item.get("native_timer")
            and row is not None
            and row.get("effect_uid") == item["runner_uid"]
            and row.get("effect_reference") == item["effect_reference"]
            and row.get("uid") == item["uid"]
            and row.get("reference") == item["reference"]
            and row.get("owner_id") == item["owner_id"]
            and contains(
                row,
                fight.actors[caster_id].position
                if target_cell is None
                else target_cell,
            )
        ):
            return
    raise ValueError("Committed producer area expired before caster turn")


def prepare(fight, character, monsters, deck, *, recipe, caster_id=-200):
    from monster_spell_scenarios import advance_to
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_effect_area_queries import contains_area_cell

    if recipe.get("qualification_spell") not in {
        a["spell_id"]
        for a in native_abilities(
            monsters[caster_id]["ref"], fight.actors[caster_id].effective_level
        )
    }:
        raise ValueError("External area consumer does not own requested native ability")
    if recipe not in recipes(
        monsters[caster_id]["ref"],
        recipe.get("qualification_spell"),
        minimum=recipe.get("target_minimum"),
        maximum=recipe.get("target_maximum"),
    ):
        raise ValueError("Unrecognized audited external area preparation")
    producer_id = -201
    producer = fight.actors[producer_id]
    descriptor = recipe["opponent"]
    if (
        monsters[producer_id]["ref"] != descriptor["reference"]
        or producer.effective_level != descriptor["level"]
        or producer.team != descriptor["team"]
    ):
        raise ValueError("External producer constructor descriptor mismatch")
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    if producer_id not in receipts:
        raise ValueError("Missing external producer initialization receipt")
    owned = next(
        (
            a
            for a in native_abilities(descriptor["reference"], producer.effective_level)
            if a["spell_id"] == recipe["producer_spell"]
        ),
        None,
    )
    if owned is None:
        raise ValueError("External producer does not own preparation spell")
    advance_to(fight, producer_id)
    before = set(getattr(fight, "native_effect_areas", {}))

    def serialize(actor, state):
        kwargs = dict(
            wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **kwargs)
        return actual_monster_actor_stats(monsters[actor.id], actor, state.id, **kwargs)

    target_cell = (
        getattr(fight, "validation_external_target_area_cell", None)
        if recipe.get("area_mode") == "target_area"
        else None
    )
    if recipe.get("area_mode") == "target_area" and target_cell is None:
        raise ValueError("Missing actual validated external target-area scene")
    action = dict(
        type="cast",
        spellId=owned["spell_id"],
        level=owned["spell_level"],
        target=list(
            fight.actors[caster_id].position if target_cell is None else target_cell
        ),
        targetId=caster_id if target_cell is None else None,
    )
    runtime = RuntimeMessages(fight)
    try:
        packets = NativeProvider(character, monsters, deck).commit(
            runtime, action, serialize
        )
    except ValueError as exc:
        raise ValueError(
            "External producer native eligibility/commit rejected: " + str(exc)
        ) from exc
    if not packets:
        raise ValueError("External producer native cast delivered no packets")
    try:
        proof = new_area_proof(
            fight,
            before,
            producer_id,
            caster_id,
            contains_area_cell,
            target_cell=target_cell,
        )
    except ValueError as exc:
        import json

        diagnostic = dict(
            native_commit_accepted=True,
            packet_ids=[p[0] for p in packets],
            new_areas=[
                row
                for uid, row in getattr(fight, "native_effect_areas", {}).items()
                if uid not in before
            ],
            owned_area_runners=list(
                getattr(fight, "native_owned_area_effects", {}).values()
            ),
            caster_position=list(fight.actors[caster_id].position),
        )
        raise ValueError(
            str(exc)
            + "; native_commit_diagnostic="
            + json.dumps(diagnostic, sort_keys=True, default=str)
        ) from exc
    advance_to(fight, caster_id)
    verify_surviving_area(
        fight, proof, caster_id, contains_area_cell, target_cell=target_cell
    )
    return dict(
        schema="native-monster-scenario-v1",
        kind="native_opponent",
        discovery=DISCOVERY,
        producer_initialization_receipt=receipts[producer_id],
        preparations=[
            dict(
                spell_id=owned["spell_id"],
                spell_level=owned["spell_level"],
                packets=len(packets),
                new_native_areas=proof,
            )
        ],
        caster_turn_id=fight.turn_id,
    )


def producer_scene_cells(source, enemy_cell, validated_cells, team):
    if team not in (0, 1):
        raise ValueError("Invalid native producer team")
    cells = sorted(set(validated_cells))
    if enemy_cell not in cells or enemy_cell == source:
        raise ValueError("Missing separate validated actual enemy cell")
    # Prefer a perpendicular adjacent producer, preserving the requested enemy
    # scene. The actual native LOS check remains the authority for every cast.
    dx, dy = enemy_cell[0] - source[0], enemy_cell[1] - source[1]
    candidates = [
        c for c in cells if c not in {source, enemy_cell} and adjacent(source, c)
    ]
    candidates.sort(
        key=lambda c: (-abs(dx * (c[1] - source[1]) - dy * (c[0] - source[0])), c)
    )
    producer = next(
        (
            c
            for c in candidates
            if dx * (c[1] - source[1]) - dy * (c[0] - source[0]) != 0
        ),
        None,
    )
    if producer is None:
        raise ValueError("No validated adjacent producer outside enemy ray")
    return producer, enemy_cell


def actual_external_targets(fight, caster_id=-200, player_id=7):
    # Requests must refer to the actor's actual constructor/runtime position.
    if getattr(fight, "validation_external_target_area_cell", None) is not None:
        return [(fight.validation_external_target_area_cell, None)]
    return [
        (fight.actors[player_id].position, player_id),
        (fight.actors[caster_id].position, caster_id),
    ]
