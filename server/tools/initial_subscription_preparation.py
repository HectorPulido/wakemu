"""Source-qualified initial-state prerequisites through genuine lifecycle/attacks."""
from copy import deepcopy

DISCOVERY = "native_initial_subscription_prerequisite_v1"


def plans(audit, reference, spell, required_state):
    """Require an exact native owned book and initial-state producer path."""
    matches = [
        r
        for r in audit["rows"]
        if r["ref"] == reference and r["required_caster_state"] == required_state
    ]
    if len(matches) != 1:
        return []
    row = matches[0]
    if row["required_caster_state"] != required_state:
        return []
    if spell not in {a["spell_id"] for a in row["owned_abilities"]}:
        return []
    result = []
    for producer in row["initial_state_producer_paths"]:
        records = [audit["native_records"].get(str(e)) for e in producer["path"]]
        if any(r is None for r in records):
            continue
        leaf = records[-1]
        if leaf["effect_class"] != 304 or leaf["parameters"][0] != required_state:
            continue
        events = [
            (i, tuple(events))
            for r in records
            for i, events in enumerate(r["target_masks"])
            if events
        ]
        if events == [(5, (1003,))]:
            mode, supported = "normal_fight_start", True
        elif (
            events == [(3, (2,))]
            and records[0]["criteria"] == "not IsTriggeredByIndirectEffect()"
        ):
            mode, supported = "incoming_owned_direct_damage", True
        elif (
            events in ([(5, (1001,))], [(5, (1002,))])
            and len(leaf["parameters"]) >= 4
            and leaf["parameters"][2] > 0
            and leaf["parameters"][3] == 0
        ):
            mode, supported = "normal_owned_turn_cycles", True
        elif events in ([(5, (1010,))], [(5, (1010,)), (2, (1026,))]):
            mode, supported = "real_knockout_then_native_lifecycle", False
        else:
            continue
        result.append(
            dict(
                discovery=DISCOVERY,
                reference=reference,
                qualification_spell=spell,
                required_state=required_state,
                mode=mode,
                executable=supported,
                source_producer=deepcopy(producer),
                event_masks=events,
                state_injection=False,
                start_boundary_authority="existing_server_policy_inference"
                if mode == "normal_fight_start"
                else None,
            )
        )
    return result


def require_state(fight, actor_id, state):
    actor = fight.actors[actor_id]
    if actor.hp <= 0 or not any(
        e.reference == state for e in actor.state_ledger.entries
    ):
        raise ValueError(
            "Genuine lifecycle did not produce required living caster state"
        )


def prepare_started(fight, *, recipe, caster_id=-200):
    """The fixture must already call its existing once-only real start transaction."""
    if (
        recipe.get("discovery") != DISCOVERY
        or recipe.get("mode") != "normal_fight_start"
        or recipe.get("executable") is not True
    ):
        raise ValueError("Unsupported initial subscription preparation")
    if not getattr(fight, "native_start_event_delivered", False):
        raise ValueError("Missing actual native fight-start delivery")
    require_state(fight, caster_id, recipe["required_state"])
    return dict(
        discovery=DISCOVERY,
        actual_start_delivered=True,
        required_state=recipe["required_state"],
        state_verified=True,
        state_injection=False,
        source_producer=deepcopy(recipe["source_producer"]),
    )


def prepare_incoming(
    fight,
    character,
    monsters,
    deck,
    *,
    recipe,
    attacker_id,
    attacker_spell,
    caster_id=-200,
    max_casts=6
):
    """Commit a real enemy-owned direct attack; never dispatch a synthetic event."""
    from monster_spell_scenarios import advance_to, finish_current_turn
    from wounded_caster_preparation import hp_and_shields
    from wakfu_server.monsters import native_abilities
    from wakfu_server.combat_tactical_ai import NativeProvider
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats

    if (
        recipe.get("discovery") != DISCOVERY
        or recipe.get("mode") != "incoming_owned_direct_damage"
        or recipe.get("executable") is not True
    ):
        raise ValueError("Unsupported initial subscription preparation")
    if type(max_casts) is not int or not 1 <= max_casts <= 6:
        raise ValueError("Invalid bounded attack preparation")
    caster, attacker = fight.actors[caster_id], fight.actors[attacker_id]
    if (
        caster.team == attacker.team
        or attacker.hp <= 0
        or monsters[caster_id]["ref"] != recipe["reference"]
    ):
        raise ValueError("Actual native preparation actor mismatch")
    book = native_abilities(monsters[caster_id]["ref"], caster.effective_level)
    if recipe["qualification_spell"] not in {a["spell_id"] for a in book}:
        raise ValueError("Missing actual qualification spell ownership")
    ability = next(
        (
            a
            for a in native_abilities(
                monsters[attacker_id]["ref"], attacker.effective_level
            )
            if a["spell_id"] == attacker_spell
        ),
        None,
    )
    if ability is None:
        raise ValueError("Incoming attack not owned by actual constructor")

    def serialize(actor, state):
        kwargs = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=state,
        )
        return (
            actual_actor_stats(character, actor, state.id, **kwargs)
            if actor.controlled
            else actual_monster_actor_stats(
                monsters[actor.id], actor, state.id, **kwargs
            )
        )

    provider, proofs = NativeProvider(character, monsters, deck), []
    for _ in range(max_casts):
        if any(
            e.reference == recipe["required_state"] for e in caster.state_ledger.entries
        ):
            break
        advance_to(fight, attacker_id)
        before, offset, uid = (
            hp_and_shields(caster),
            len(fight.events),
            fight.native_effect_uid_next,
        )
        from unittest.mock import patch
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeEventSource,
        )

        replayed = []
        original_replay = NativeEventReplay.__call__

        def observe(replay, source, *, authority):
            outcome = original_replay(replay, source, authority=authority)
            if isinstance(source, NativeEventSource) and 2 in source.event_ids:
                replayed.append(
                    dict(
                        uid=source.uid,
                        caster_id=source.caster_id,
                        target_id=source.target_id,
                        event_ids=list(source.event_ids),
                        channel=source.channel,
                        native_events_verified=source.native_events_verified,
                    )
                )
            return outcome

        with patch.object(NativeEventReplay, "__call__", observe):
            packets = provider.commit(
                RuntimeMessages(fight),
                dict(
                    type="cast",
                    spellId=attacker_spell,
                    level=ability["spell_level"],
                    target=list(caster.position),
                    targetId=caster_id,
                ),
                serialize,
            )
        proof = verify_subscribed_damage(
            before,
            hp_and_shields(caster),
            fight.events[offset:],
            attacker_id=attacker_id,
            caster_id=caster_id,
            packets=packets,
            native_events=replayed,
            before_uid=uid,
            after_uid=fight.native_effect_uid_next,
            state_verified=any(
                e.reference == recipe["required_state"]
                for e in caster.state_ledger.entries
            ),
        )
        if fight.native_effect_uid_next <= uid:
            raise ValueError("Actual attack omitted fresh native UID")
        proofs.append(
            dict(
                proof,
                effect_uid_before=uid,
                effect_uid_after=fight.native_effect_uid_next,
            )
        )
        if any(
            e.reference == recipe["required_state"] for e in caster.state_ledger.entries
        ):
            break
        finish_current_turn(fight)
    advance_to(fight, caster_id)
    require_state(fight, caster_id, recipe["required_state"])
    return dict(
        discovery=DISCOVERY,
        preparations=proofs,
        state_verified=True,
        state_injection=False,
    )


_SOURCE_AUDIT = None


def configure_source_audit(document):
    """Explicit caller-provided native source index; disabled by default."""
    global _SOURCE_AUDIT
    if document is not None and (
        not isinstance(document, dict)
        or document.get("schema") != "native-owned-state-producer-audit-v1"
        or not isinstance(document.get("rows"), list)
        or not isinstance(document.get("native_records"), dict)
    ):
        raise ValueError("Missing native initial subscription source authority")
    _SOURCE_AUDIT = deepcopy(document)


def recovery_recipes(reference, level, spell, criterion, native_source):
    if _SOURCE_AUDIT is None:
        return []
    from monster_pending_scenarios import simple_required_caster_states
    from owned_state_stack import required_caster_state_levels

    required = set(simple_required_caster_states(criterion)) | set(
        required_caster_state_levels(criterion, maximum_grade=32767)
    )
    source = native_source.get(reference)
    if not source or not source["min_level"] <= level <= source["max_level"]:
        return []
    rows = [r for r in _SOURCE_AUDIT["rows"] if r["ref"] == reference]
    if not rows:
        return []
    if any(
        row["owned_abilities"] != source["native_abilities"]
        or row["native_initial_state_triples"] != source["initial_state_triples"]
        for row in rows
    ):
        raise ValueError("Initial subscription audit differs from native constructor")
    recipes = []
    for state in sorted(required):
        for recipe in plans(_SOURCE_AUDIT, reference, spell, state):
            if not recipe["executable"]:
                continue
            recipe.update(kind="owned_spell_sequence", actions=[])
            if recipe["mode"] == "incoming_owned_direct_damage":
                witness = _SOURCE_AUDIT.get("incoming_attack_witness")
                if not isinstance(witness, dict):
                    continue
                native = native_source.get(witness.get("reference"))
                if (
                    not native
                    or type(witness.get("level")) is not int
                    or not native["min_level"]
                    <= witness["level"]
                    <= native["max_level"]
                    or witness.get("spell")
                    not in {a["spell_id"] for a in native["native_abilities"]}
                ):
                    raise ValueError(
                        "Incoming witness lacks actual native owned constructor"
                    )
                recipe.update(
                    kind="native_opponent",
                    opponent=dict(
                        reference=witness["reference"], level=witness["level"], team=0
                    ),
                    attacker_spell=witness["spell"],
                )
            recipes.append(recipe)
    return recipes[:4]


def prepare(fight, character, monsters, deck, *, recipe, caster_id=-200):
    from wakfu_server.combat_native_spell_casting import catalog
    from wakfu_server.monsters import native_abilities

    spell = recipe.get("qualification_spell")
    source = monsters[caster_id]["ref"]
    actor = fight.actors[caster_id]
    if source != recipe.get("reference") or spell not in {
        a["spell_id"] for a in native_abilities(source, actor.effective_level)
    }:
        raise ValueError("Initial subscription recipe does not match actual ownership")
    from monster_pending_scenarios import simple_required_caster_states
    from owned_state_stack import required_caster_state_levels

    criterion = catalog().get(str(spell), {}).get("cast_criterion_raw", "")
    necessary_states = set(simple_required_caster_states(criterion)) | set(
        required_caster_state_levels(criterion, maximum_grade=32767)
    )
    if recipe.get("required_state") not in necessary_states:
        raise ValueError(
            "Initial subscription is not a necessary native caster criterion"
        )
    if _SOURCE_AUDIT is None:
        raise ValueError("Missing configured native subscription source authority")
    expected = plans(_SOURCE_AUDIT, source, spell, recipe.get("required_state"))
    if not any(
        all(
            recipe.get(k) == p.get(k)
            for k in (
                "discovery",
                "reference",
                "qualification_spell",
                "required_state",
                "mode",
                "executable",
                "source_producer",
                "event_masks",
            )
        )
        for p in expected
    ):
        raise ValueError("Preparation differs from its authenticated native path")
    if recipe.get("mode") == "normal_owned_turn_cycles":
        return prepare_turn_cycles(
            fight,
            recipe=recipe,
            caster_id=caster_id,
            criterion=catalog().get(str(spell), {}).get("cast_criterion_raw", ""),
        )
    if recipe.get("mode") == "normal_fight_start":
        return prepare_started(fight, recipe=recipe, caster_id=caster_id)
    return prepare_incoming(
        fight,
        character,
        monsters,
        deck,
        recipe=recipe,
        attacker_id=-201,
        attacker_spell=recipe.get("attacker_spell"),
        caster_id=caster_id,
    )


def build_source_audit(queries, native_source, state_roots, effect_records):
    """Index any native initial-state paths for explicit (ref, spell, state) queries.

    Inputs are caller-supplied authenticated native tables. No actor, event,
    resources or missing definition is manufactured by this pure exporter.
    Only constant state producers are indexed; evaluated formulas need their
    own exact native context evidence rather than a guessed parameter zero.
    """
    rows = []
    indexed = set()
    for reference, spell, required_state in sorted(set(queries)):
        if (reference, required_state) in indexed:
            continue
        native = native_source.get(reference)
        if native is None or spell not in {
            a["spell_id"] for a in native["native_abilities"]
        }:
            continue
        indexed.add((reference, required_state))
        triples = native["initial_state_triples"]
        if len(triples) % 3:
            raise ValueError("Malformed native initial-state constructor")
        producers = []
        for offset in range(0, len(triples), 3):
            initial = triples[offset]
            todo = [(int(e), [int(e)]) for e in state_roots.get(str(initial), ())]
            seen = set()
            while todo:
                identity, path = todo.pop()
                if identity in seen:
                    continue
                seen.add(identity)
                record = effect_records.get(str(identity))
                if record is None:
                    raise ValueError("Missing native initial-state effect definition")
                levels = record.get("parameter0_by_level")
                if (
                    record.get("effect_class") == 304
                    and record.get("parameters", [None])[0] == required_state
                    and (levels is None or set(levels) == {required_state})
                ):
                    producers.append(
                        dict(initial_state=initial, producer_effect=identity, path=path)
                    )
                todo.extend(
                    (int(e), path + [int(e)])
                    for e in record.get("children", ())
                    if int(e) not in seen
                )
        rows.append(
            dict(
                ref=reference,
                blocked_spell=spell,
                required_caster_state=required_state,
                owned_abilities=deepcopy(native["native_abilities"]),
                native_initial_state_triples=list(triples),
                initial_state_producer_paths=producers,
            )
        )
    used = {
        str(e)
        for row in rows
        for producer in row["initial_state_producer_paths"]
        for e in producer["path"]
    }
    return dict(
        schema="native-owned-state-producer-audit-v1",
        rows=rows,
        native_records={key: deepcopy(effect_records[key]) for key in sorted(used)},
        state_injection_permitted=False,
        execution_validated=False,
    )


def verify_subscribed_damage(
    before,
    after,
    events,
    *,
    attacker_id,
    caster_id,
    packets,
    native_events,
    before_uid,
    after_uid,
    state_verified
):
    """eXt event2 exists for an actual zero-damage cast as well as HP loss.

    This is not the wounded-caster HP recipe: its contract is actual owned
    damage delivery plus the separately checked native state replay outcome.
    combat_damage_events.damage_event_ids unconditionally includes event2.
    """
    damage = [
        e
        for e in events
        if e.get("kind") == "damage"
        and e.get("source_id") == attacker_id
        and e.get("target_id") == caster_id
        and type(e.get("amount")) is int
        and e["amount"] >= 0
    ]
    actual = [
        e
        for e in native_events
        if e.get("caster_id") == attacker_id
        and e.get("target_id") == caster_id
        and 2 in e.get("event_ids", ())
        and e.get("channel") == 3
        and e.get("native_events_verified") is True
        and type(e.get("uid")) is int
        and before_uid <= e["uid"] < after_uid
    ]
    if (
        not packets
        or not damage
        or not actual
        or state_verified is not True
        or after_uid <= before_uid
        or after["hp"] <= 0
        or after["hp"] > before["hp"]
        or after["max_hp"] != before["max_hp"]
    ):
        raise ValueError("Missing living actual subscribed damage/event/state delivery")
    return dict(
        before=before,
        after=after,
        damage_events=damage,
        native_event2_sources=actual,
        packet_ids=[p[0] for p in packets],
    )


def prepare_turn_cycles(fight, *, recipe, caster_id, criterion, maximum_cycles=30):
    """Reach a native counter through real owner start/end boundaries only."""
    from owned_state_stack import required_caster_state_levels
    from monster_spell_scenarios import advance_to, finish_current_turn

    required = required_caster_state_levels(criterion, maximum_grade=32767).get(
        recipe.get("required_state")
    )
    if (
        recipe.get("mode") != "normal_owned_turn_cycles"
        or recipe.get("executable") is not True
        or type(required) is not int
        or required <= 0
    ):
        raise ValueError("Missing necessary native turn-counter requirement")
    if type(maximum_cycles) is not int or not 1 <= maximum_cycles <= 30:
        raise ValueError("Invalid native turn-cycle bound")
    actor = fight.actors[caster_id]

    def grade():
        return max(
            (
                entry.level
                for entry in actor.state_ledger.entries
                if entry.reference == recipe["required_state"]
            ),
            default=0,
        )

    advance_to(fight, caster_id)
    observed = [grade()]
    for _ in range(maximum_cycles):
        if grade() >= required:
            break
        if actor.hp <= 0:
            raise ValueError("Turn-counter caster is no longer alive")
        finish_current_turn(fight)
        advance_to(fight, caster_id)
        observed.append(grade())
    if actor.hp <= 0 or grade() < required:
        raise ValueError(
            "Genuine native turn boundaries did not reach required counter"
        )
    return dict(
        discovery=DISCOVERY,
        mode="normal_owned_turn_cycles",
        state_injection=False,
        required_state=recipe["required_state"],
        required_level=required,
        observed_levels=observed,
        actual_turn_cycles=len(observed) - 1,
        source_producer=deepcopy(recipe["source_producer"]),
        state_verified=True,
    )
