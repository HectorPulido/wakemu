"""Meet native caster HP prerequisites using genuine incoming owned attacks."""
DISCOVERY = "native_incoming_damage_hp_prerequisite_v1"


def required_hp_threshold(criterion):
    import ast
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return None
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return None
    if sum(1 for _ in ast.walk(root)) > 256:
        return None

    def visit(node):
        if isinstance(node, ast.BoolOp):
            values = [visit(n) for n in node.values]
            if isinstance(node.op, ast.Or):
                return max(values) if all(v is not None for v in values) else None
            known = [v for v in values if v is not None]
            return min(known) if known else None
        if not (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
            and isinstance(node.ops[0], ast.Lt)
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
            and 1 <= node.comparators[0].value <= 99
        ):
            return None
        call = node.left
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "GetCharacInPct"
            and not call.keywords
            and len(call.args) in (1, 2)
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
            and call.args[0].value.lower() == "hp"
        ):
            return None
        if len(call.args) == 2 and not (
            isinstance(call.args[1], ast.Constant) and call.args[1].value == "caster"
        ):
            return None
        return node.comparators[0].value

    return visit(root)


def recipes(criterion, spell):
    threshold = required_hp_threshold(criterion)
    if threshold is None:
        return []
    return [
        dict(
            kind="native_opponent",
            discovery=DISCOVERY,
            opponent=dict(reference=6, level=4, team=0),
            attacker_spell=5790,
            qualification_spell=spell,
            native_criterion=criterion,
            threshold_percent=threshold,
            max_casts=64,
        )
    ]


def scene_cells(source, enemy, validated_cells):
    cells = set(validated_cells)
    attacker = next(
        (
            c
            for c in sorted(cells)
            if c not in {source, enemy}
            and c[2] == source[2]
            and abs(c[0] - source[0]) + abs(c[1] - source[1]) == 1
        ),
        None,
    )
    if attacker is None:
        raise ValueError("No separate validated adjacent incoming attacker cell")
    player = enemy if enemy in cells and enemy not in {source, attacker} else None
    if player is None:
        raise ValueError("No actual separate player placement")
    return attacker, player


def hp_and_shields(actor):
    stats = actor.effect_stats
    return dict(
        hp=actor.hp,
        max_hp=actor.max_hp,
        armor=stats.get(97, 0),
        barrier=stats.get(100, 0),
    )


def verify_incoming_damage(before, after, events, *, attacker_id, caster_id, packets):
    damage = [
        event
        for event in events
        if event.get("kind") == "damage"
        and event.get("source_id") == attacker_id
        and event.get("target_id") == caster_id
        and type(event.get("amount")) is int
        and event["amount"] >= 0
    ]
    if (
        not packets
        or not damage
        or after["hp"] <= 0
        or after["max_hp"] != before["max_hp"]
        or not (
            after["hp"] < before["hp"]
            or after["armor"] < before["armor"]
            or after["barrier"] < before["barrier"]
        )
    ):
        raise ValueError("Native incoming attack lacks living HP/shield damage proof")
    return dict(
        before=before,
        after=after,
        damage_events=damage,
        packet_ids=[p[0] for p in packets],
    )


def below_threshold(actor, threshold):
    return (
        actor.max_hp > 0 and 0 < actor.hp and 100 * actor.hp < threshold * actor.max_hp
    )


def prepare(fight, character, monsters, deck, *, recipe, caster_id=-200):
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats

    attacker_id = -201
    attacker = fight.actors[attacker_id]
    caster = fight.actors[caster_id]
    owned = native_abilities(monsters[caster_id]["ref"], caster.effective_level)
    spell = recipe.get("qualification_spell")
    criterion = catalog().get(str(spell), {}).get("cast_criterion_raw", "")
    if spell not in {a["spell_id"] for a in owned} or recipe not in recipes(
        criterion, spell
    ):
        raise ValueError("Unrecognized native incoming-damage prerequisite")
    descriptor = recipe["opponent"]
    if (
        monsters[attacker_id]["ref"] != descriptor["reference"]
        or attacker.effective_level != descriptor["level"]
        or attacker.team != descriptor["team"]
        or attacker.team == caster.team
    ):
        raise ValueError("Native incoming attacker constructor/team mismatch")
    ability = next(
        (
            a
            for a in native_abilities(descriptor["reference"], attacker.effective_level)
            if a["spell_id"] == recipe["attacker_spell"]
        ),
        None,
    )
    if ability is None:
        raise ValueError("Native incoming attacker does not own preparation spell")

    def serialize(actor, state):
        kwargs = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **kwargs)
        return actual_monster_actor_stats(monsters[actor.id], actor, state.id, **kwargs)

    preparations = []
    provider = NativeProvider(character, monsters, deck)
    for _ in range(recipe["max_casts"]):
        if below_threshold(caster, recipe["threshold_percent"]):
            break
        advance_to(fight, attacker_id)
        before = hp_and_shields(caster)
        start = len(fight.events)
        before_uid = fight.native_effect_uid_next
        before_retained = set(getattr(fight, "native_owned_group_effects", {}))
        packets = provider.commit(
            RuntimeMessages(fight),
            dict(
                type="cast",
                spellId=ability["spell_id"],
                level=ability["spell_level"],
                target=list(caster.position),
                targetId=caster_id,
            ),
            serialize,
        )
        proof = verify_incoming_damage(
            before,
            hp_and_shields(caster),
            fight.events[start:],
            attacker_id=attacker_id,
            caster_id=caster_id,
            packets=packets,
        )
        import hashlib

        proof.update(
            effect_uid_before=before_uid,
            effect_uid_after=fight.native_effect_uid_next,
            packet_sha256=[hashlib.sha256(packet[1]).hexdigest() for packet in packets],
            new_retained_runners=[
                row
                for uid, row in getattr(fight, "native_owned_group_effects", {}).items()
                if uid not in before_retained
            ],
        )
        preparations.append(
            dict(
                spell_id=ability["spell_id"],
                spell_level=ability["spell_level"],
                attacker_id=attacker_id,
                target_id=caster_id,
                **proof
            )
        )
        if below_threshold(caster, recipe["threshold_percent"]):
            break
        finish_current_turn(fight)
    advance_to(fight, caster_id)
    if not below_threshold(caster, recipe["threshold_percent"]):
        raise ValueError(
            "Native incoming damage failed finite caster HP prerequisite after lifecycle"
        )
    return dict(
        schema="native-monster-scenario-v1",
        kind="native_opponent",
        discovery=DISCOVERY,
        preparations=preparations,
        threshold_percent=recipe["threshold_percent"],
        caster_hp=caster.hp,
        caster_max_hp=caster.max_hp,
        caster_turn_id=fight.turn_id,
    )
