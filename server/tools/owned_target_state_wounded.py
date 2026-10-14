"""Compose native owned damage, caster charge, and short-lived target states."""
import ast
import json

DISCOVERY = "owned_target_state_wounded_v1"


def target_requirements(criterion):
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return None
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return None
    if sum(1 for _ in ast.walk(root)) > 256:
        return None
    nodes = []

    def flatten(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            for value in node.values:
                flatten(value)
        else:
            nodes.append(node)

    flatten(root)
    states, thresholds = set(), []
    for node in nodes:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "HasState"
            and not node.keywords
            and len(node.args) == 2
        ):
            if all(isinstance(a, ast.Constant) for a in node.args):
                state, selector = [a.value for a in node.args]
                if type(state) is int and state > 0 and selector == "target":
                    states.add(state)
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
            and isinstance(node.ops[0], ast.Lt)
        ):
            call, threshold = node.left, node.comparators[0]
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "GetCharacInPct"
                and not call.keywords
                and len(call.args) == 2
                and all(isinstance(a, ast.Constant) for a in call.args)
                and isinstance(threshold, ast.Constant)
            ):
                characteristic, selector = [a.value for a in call.args]
                if (
                    isinstance(characteristic, str)
                    and characteristic.lower() == "hp"
                    and selector == "target"
                    and type(threshold.value) is int
                    and 1 <= threshold.value < 100
                ):
                    thresholds.append(threshold.value)
    return (
        (next(iter(states)), min(thresholds))
        if len(states) == 1 and thresholds
        else None
    )


def constant_pair(raw, offset):
    if (
        len(raw) <= offset + 1
        or raw[offset + 1] != 0
        or type(raw[offset]) not in (int, float)
        or not float(raw[offset]).is_integer()
    ):
        return None
    return int(raw[offset])


def recipes(
    reference,
    actor_level,
    consumer_spell,
    criterion,
    abilities,
    document,
    casting,
    definitions,
):
    from owned_state_stack import required_caster_state_levels
    from wakfu_server.combat_effect_targets import native_selector_policy

    target = target_requirements(criterion)
    charges = required_caster_state_levels(criterion)
    if target is None or len(charges) != 1:
        return []
    charge, required = next(iter(charges.items()))
    target_state, threshold = target
    charge_definition = definitions.get(str(charge), {})
    target_definition = definitions.get(str(target_state), {})
    cap = charge_definition.get("maximum_level")
    if not (
        type(cap) is int
        and required > 1
        and cap >= required
        and charge_definition.get("additive") is True
        and charge_definition.get("refresh") is False
        and charge_definition.get("duration_base") == -1
    ):
        return []
    if (
        target_definition.get("duration_base") != 1
        or target_definition.get("clock_actor") != "target"
        or target_definition.get("tick_at_turn_end") is not True
    ):
        return []
    effects = dict(document.get("baseline_effects", {}))
    effects.update(document.get("effects", {}))
    damage_options, state_options = [], []
    for ability in abilities:
        spell, level = ability["spell_id"], ability["spell_level"]
        if spell == consumer_spell:
            continue
        record = document.get("spells", {}).get(str(spell))
        cast = casting.get(str(spell), {})
        if record is None or not 1 <= level <= len(record["levels"]):
            continue
        minimum, maximum, roots = record["levels"][level - 1]
        rows = [effects.get(str(key)) for key in roots]
        if any(row is None for row in rows):
            continue
        costs = cast.get("costs", [])
        if not 1 <= level <= len(costs) or len(costs[level - 1]) != 3:
            continue
        gains, damage, state_rows, consumption = [], [], [], []
        for key, row in zip(roots, rows):
            try:
                policy = native_selector_policy(row)
            except ValueError:
                continue
            raw = row.get("parameters", [])
            family = row.get("effect_class")
            self_only = (
                policy["relations"] == frozenset({"self"}) and not policy["in_area"]
            )
            enemy_point = "enemy" in policy["relations"] and (
                row.get("area_class"),
                row.get("area_native"),
            ) == ("anD", "point")
            if (
                family == 304
                and constant_pair(raw, 0) == charge
                and self_only
                and not row.get("criteria")
            ):
                gain = constant_pair(raw, 2)
                if gain is not None and gain > 0:
                    gains.append(dict(effect_id=key, gain=gain))
            if family == 1 and enemy_point and not row.get("criteria"):
                amount = constant_pair(raw, 0)
                if amount is not None and amount > 0:
                    damage.append(dict(effect_id=key, amount=amount))
            if (
                family == 304
                and constant_pair(raw, 0) == target_state
                and enemy_point
                and constant_pair(raw, 2) == 1
                and constant_pair(raw, 4) == 100
            ):
                state_rows.append(
                    dict(effect_id=key, criterion=row.get("criteria", ""))
                )
            if (
                family == 321
                and constant_pair(raw, 0) == charge
                and self_only
                and not row.get("criteria")
            ):
                amount = constant_pair(raw, 2)
                if amount is not None and amount > 0:
                    consumption.append(amount)
        if (
            len(rows) == 2
            and len(gains) == len(damage) == 1
            and cast.get("cast_criterion_raw", "").strip()
            in ("", "IsEnnemy()", "IsEnemy()")
            and not cast.get("conditional")
        ):
            damage_options.append(
                dict(
                    spell_id=spell,
                    spell_level=level,
                    range=[minimum, maximum],
                    costs=costs[level - 1],
                    gain=gains[0]["gain"],
                    damage=damage[0]["amount"],
                    roots=roots,
                )
            )
        needed = required_caster_state_levels(cast.get("cast_criterion_raw", ""))
        if (
            len(state_rows) == len(consumption) == 1
            and needed.get(charge)
            and cap - consumption[0] >= required
            and not cast.get("conditional")
            and costs[level - 1] == [0, 0, 0]
        ):
            # The immediate post-state scene must be reachable without a target turn.
            pulls = [
                constant_pair(row.get("parameters", []), 0)
                for row in rows
                if row.get("effect_class") == 301
            ]
            if (
                len(pulls) == 1
                and type(pulls[0]) is int
                and pulls[0] > 0
                and minimum == maximum
                and minimum - pulls[0] == 1
            ):
                state_options.append(
                    dict(
                        spell_id=spell,
                        spell_level=level,
                        range=[minimum, maximum],
                        costs=costs[level - 1],
                        consumed_charge=consumption[0],
                        required_charge=needed[charge],
                        target_state_effect=state_rows[0],
                        pull=pulls[0],
                        roots=roots,
                    )
                )
    if not damage_options or not state_options:
        return []
    damage_options.sort(
        key=lambda row: (row["costs"][2], row["costs"][1], row["costs"][0])
    )
    consumer = document.get("spells", {}).get(str(consumer_spell))
    own_consumer = next((a for a in abilities if a["spell_id"] == consumer_spell), None)
    if consumer is None or own_consumer is None:
        return []
    cmin, cmax, _ = consumer["levels"][own_consumer["spell_level"] - 1]
    if cmin < 1 or cmax < cmin or max(0, cmin - 1, 1 - cmax) > 1:
        return []  # Short target clocks permit at most one actual post-pull step.
    consumer_costs = casting.get(str(consumer_spell), {}).get("costs", [])
    if not 1 <= own_consumer["spell_level"] <= len(consumer_costs) or consumer_costs[
        own_consumer["spell_level"] - 1
    ] != [0, 0, 0]:
        return []
    return [
        dict(
            kind="native_opponent",
            discovery=DISCOVERY,
            opponent=dict(reference=reference, level=actor_level, team=0),
            native_producer_target_id=-201,
            qualification_spell=consumer_spell,
            qualification_spell_level=own_consumer["spell_level"],
            native_criterion=criterion,
            charge_state=charge,
            required_charge=required,
            native_charge_maximum=cap,
            target_state=target_state,
            threshold_percent=threshold,
            target_state_duration=1,
            damage_producer=damage_options[0],
            target_state_producer=state,
            consumer_range=[cmin, cmax],
            max_damage_casts=64,
        )
        for state in state_options[:2]
    ]


def charge_entry(actor, reference):
    return next(
        (
            entry
            for entry in actor.state_ledger.entries
            if entry.reference == reference
            and entry.target_id == actor.id
            and entry.caster_id == actor.id
        ),
        None,
    )


def verify_damage_preview(before_fight, preview, caster_id, target_id, recipe):
    before, after = before_fight.actors[target_id], preview.fight.actors[target_id]
    events = getattr(getattr(preview, "spell", None), "events", ())
    if (
        after.hp <= 0
        or after.hp >= before.hp
        or after.max_hp != before.max_hp
        or not any(
            e.get("kind") == "damage"
            and e.get("source_id") == caster_id
            and e.get("target_id") == target_id
            and type(e.get("amount")) is int
            and e["amount"] > 0
            for e in events
        )
    ):
        raise ValueError(
            "Owned target damage preview lacks safe living actual HP decrease"
        )
    old = charge_entry(before_fight.actors[caster_id], recipe["charge_state"])
    current = charge_entry(preview.fight.actors[caster_id], recipe["charge_state"])
    old_level = 0 if old is None else old.level
    expected = min(
        old_level + recipe["damage_producer"]["gain"], recipe["native_charge_maximum"]
    )
    if current is None or current.level != expected:
        raise ValueError(
            "Actual owned damage did not preserve native charge growth/cap"
        )
    if old_level < recipe["native_charge_maximum"] and (
        old is not None
        and current.uid == old.uid
        or not any(
            e.get("kind") == "state_applied"
            and e.get("uid") == current.uid
            and e.get("actor_id") == caster_id
            and e.get("source_id") == caster_id
            and e.get("state_id") == recipe["charge_state"]
            for e in events
        )
    ):
        raise ValueError("Actual native charge growth lacks new state UID/event")
    if old_level == recipe["native_charge_maximum"] and current.uid != old.uid:
        raise ValueError(
            "Native non-refreshing charge cap unexpectedly replaced state UID"
        )
    return dict(
        before_hp=before.hp,
        after_hp=after.hp,
        charge_uid=current.uid,
        charge_level=current.level,
        charge_at_native_cap=old_level == recipe["native_charge_maximum"],
    )


def verify_target_state(fight, events, caster_id, target_id, recipe, *, prior_uid=None):
    target = fight.actors[target_id]
    entries = [
        e
        for e in target.state_ledger.entries
        if e.reference == recipe["target_state"]
        and e.target_id == target_id
        and e.caster_id == caster_id
    ]
    matched = (
        [
            e
            for e in entries
            if any(
                v.get("kind") == "state_applied"
                and v.get("uid") == e.uid
                and v.get("actor_id") == target_id
                and v.get("source_id") == caster_id
                and v.get("state_id") == recipe["target_state"]
                for v in events
            )
        ]
        if prior_uid is None
        else [e for e in entries if e.uid == prior_uid]
    )
    charge = charge_entry(fight.actors[caster_id], recipe["charge_state"])
    if (
        not matched
        or charge is None
        or charge.level < recipe["required_charge"]
        or matched[0].duration != recipe["target_state_duration"]
        or matched[0].clock_actor != "target"
        or matched[0].tick_at_turn_end is not True
    ):
        raise ValueError(
            "Native target state UID/owner or remaining caster charge missing"
        )
    return dict(
        target_state=recipe["target_state"],
        target_state_uid=matched[0].uid,
        charge_uid=charge.uid,
        charge_level=charge.level,
    )


def prepare(fight, character, monsters, deck, *, recipe, caster_id=-200):
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_npc_attack import npc_spell_catalog
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
    from owned_state_stack import (
        native_state_definitions,
        native_path,
        commit_native_path,
        ensure_native_producer_resources,
        native_segment_cost,
    )
    from owned_state_movement import bind_owned_movement_authority
    from wounded_caster_preparation import (
        below_threshold,
        hp_and_shields,
        verify_incoming_damage,
    )

    caster, target_id = fight.actors[caster_id], -201
    ref, level = monsters[caster_id]["ref"], caster.effective_level
    casting = catalog()
    consumer = recipe["qualification_spell"]
    candidates = recipes(
        ref,
        level,
        consumer,
        casting.get(str(consumer), {}).get("cast_criterion_raw", ""),
        native_abilities(ref, level),
        npc_spell_catalog(),
        casting,
        native_state_definitions(),
    )
    if json.loads(json.dumps(recipe)) not in [
        json.loads(json.dumps(r)) for r in candidates
    ]:
        raise ValueError(
            "Compound preparation recipe is not exact native owned discovery"
        )
    descriptor, target = recipe["opponent"], fight.actors[target_id]
    if (
        monsters[target_id]["ref"] != descriptor["reference"]
        or target.effective_level != descriptor["level"]
        or target.team != descriptor["team"]
        or target.team == caster.team
    ):
        raise ValueError("Compound native recipient constructor/team mismatch")
    advance_to(fight, caster_id)
    bind_owned_movement_authority(fight, character, monsters, deck)

    def serialize(actor, state):
        kwargs = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        if actor.controlled:
            return actual_actor_stats(character, actor, state.id, **kwargs)
        return actual_monster_actor_stats(monsters[actor.id], actor, state.id, **kwargs)

    def action(producer):
        return dict(
            type="cast",
            spellId=producer["spell_id"],
            level=producer["spell_level"],
            target=list(fight.actors[target_id].position),
            targetId=target_id,
        )

    def position_for(bounds, cast):
        def accepts(cell):
            enemy = fight.actors[target_id].position
            dx, dy = abs(cell[0] - enemy[0]), abs(cell[1] - enemy[1])
            return (
                cell[2] == enemy[2]
                and bounds[0] <= dx + dy <= bounds[1]
                and (not cast.get("linear") or dx == 0 or dy == 0)
            )

        return native_path(fight, caster_id, accepts)

    class DamageCheckedProvider(NativeProvider):
        def preview(self, source, cast_action, action_id, *, forecast):
            result = super().preview(source, cast_action, action_id, forecast=forecast)
            if (
                cast_action["spellId"] != recipe["damage_producer"]["spell_id"]
                or cast_action["targetId"] != target_id
                or cast_action["level"] != recipe["damage_producer"]["spell_level"]
            ):
                raise ValueError("Owned damage preparation action changed")
            self.native_damage_proof = verify_damage_preview(
                source, result, caster_id, target_id, recipe
            )
            return result

    provider = DamageCheckedProvider(character, monsters, deck)
    damage = recipe["damage_producer"]
    proofs = []
    movement = commit_native_path(
        fight,
        caster_id,
        position_for(damage["range"], casting[str(damage["spell_id"])]),
        NativeProvider(character, monsters, deck),
        RuntimeMessages,
        serialize,
    )
    for _ in range(recipe["max_damage_casts"]):
        charge = charge_entry(fight.actors[caster_id], recipe["charge_state"])
        if (
            below_threshold(fight.actors[target_id], recipe["threshold_percent"])
            and charge is not None
            and charge.level == recipe["native_charge_maximum"]
        ):
            break
        ensure_native_producer_resources(fight, caster_id, damage["costs"])
        before = hp_and_shields(fight.actors[target_id])
        event_start = len(fight.events)
        packets = provider.commit(RuntimeMessages(fight), action(damage), serialize)
        proof = verify_incoming_damage(
            before,
            hp_and_shields(fight.actors[target_id]),
            fight.events[event_start:],
            attacker_id=caster_id,
            caster_id=target_id,
            packets=packets,
        )
        proof["native_charge_proof"] = provider.native_damage_proof
        proofs.append(proof)
    else:
        raise ValueError("Bounded genuine owned target damage sequence exhausted")
    if not below_threshold(fight.actors[target_id], recipe["threshold_percent"]):
        raise ValueError("Actual native target HP threshold remains unmet")
    state = recipe["target_state_producer"]
    state_movement = commit_native_path(
        fight,
        caster_id,
        position_for(state["range"], casting[str(state["spell_id"])]),
        NativeProvider(character, monsters, deck),
        RuntimeMessages,
        serialize,
    )
    # This is the LAST normal turn: the short target state does not exist yet.
    finish_current_turn(fight)
    advance_to(fight, caster_id)
    ensure_native_producer_resources(fight, caster_id, state["costs"])
    charge_before = charge_entry(fight.actors[caster_id], recipe["charge_state"])
    if charge_before is None or charge_before.level != recipe["native_charge_maximum"]:
        raise ValueError(
            "Native caster charge did not survive ordinary preparation turns"
        )

    class TargetStateCheckedProvider(NativeProvider):
        def preview(self, source, cast_action, action_id, *, forecast):
            result = super().preview(source, cast_action, action_id, forecast=forecast)
            self.native_target_state_proof = verify_target_state(
                result.fight, result.spell.events, caster_id, target_id, recipe
            )
            after_charge = charge_entry(
                result.fight.actors[caster_id], recipe["charge_state"]
            )
            if (
                after_charge.level != charge_before.level - state["consumed_charge"]
                or result.fight.actors[target_id].hp <= 0
            ):
                raise ValueError(
                    "Native target-state cast charge consumption/living target changed"
                )
            return result

    state_provider = TargetStateCheckedProvider(character, monsters, deck)
    packets = state_provider.commit(RuntimeMessages(fight), action(state), serialize)
    if not packets:
        raise ValueError("Native target-state cast produced no actual packets")
    state_proof = state_provider.native_target_state_proof
    turn_id = fight.turn_id
    path = position_for(recipe["consumer_range"], casting[str(consumer)])
    if len(path) > 1:
        raise ValueError(
            "Short target-state lifetime cannot cover the actual consumer path"
        )
    if path:
        ap, mp = native_segment_cost(fight, caster_id, path)
        if ap > fight.actors[caster_id].ap or mp > fight.actors[caster_id].mp:
            raise ValueError(
                "No actual AP/MP budget for immediate native consumer placement"
            )
    consumer_movement = commit_native_path(
        fight,
        caster_id,
        path,
        NativeProvider(character, monsters, deck),
        RuntimeMessages,
        serialize,
    )
    final = verify_target_state(
        fight,
        (),
        caster_id,
        target_id,
        recipe,
        prior_uid=state_proof["target_state_uid"],
    )
    if fight.turn_id != turn_id or not below_threshold(
        fight.actors[target_id], recipe["threshold_percent"]
    ):
        raise ValueError(
            "Target state clock or real HP prerequisite changed before consumer"
        )
    return dict(
        schema="native-monster-scenario-v1",
        kind=recipe["kind"],
        owned_damage_casts=proofs,
        native_damage_approach=movement,
        native_target_state_approach=state_movement,
        native_target_state_proof=state_proof,
        native_target_state_packets=len(packets),
        native_consumer_placement=consumer_movement,
        final_native_prerequisites=final,
        final_target_hp=fight.actors[target_id].hp,
        final_target_max_hp=fight.actors[target_id].max_hp,
        no_turn_after_short_target_state=True,
        caster_turn_id=turn_id,
    )
