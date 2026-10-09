#!/usr/bin/env python3
"""Bulk class-owned summon creation and reaction audit over the shared runtime.

Mechanic dispatch intentionally does not attest client cast permission. Native
criteria, initial state triples, owner class and effect containers are preserved.
"""
from contextlib import contextmanager
import argparse
import copy
import hashlib
import json
import random
import struct
from pathlib import Path

import audit_active_spells as audit
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_server_spell import (
    server_runtime,
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from class_summon_parent_casts import execute_native_parent_roots
from wakfu_server.spells import SPELLS, encode_deck
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_los import authoritative_visible

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ancestors(graph, key, ownership):
    """Prefer the nearest actual native spell container, then grant ancestry."""
    pending, distances, spells = [(key, 0)], {}, {}
    while pending:
        node, distance = pending.pop(0)
        if node in distances:
            continue
        distances[node] = distance
        if node.startswith("spell:"):
            reference = int(node.split(":")[1])
            if reference in ownership:
                spells[reference] = distance
        pending.extend(
            (graph["edges"][index]["source"], distance + 1)
            for index in graph["reverse_index"].get(node, [])
        )
    return sorted(spells, key=lambda reference: (spells[reference], reference))


def actor_summary(actor):
    return dict(
        id=actor.id,
        hp=actor.hp,
        position=list(actor.position),
        states=[
            dict(
                reference=state.reference,
                level=state.level,
                uid=state.uid,
                effect_ids=list(state.effect_ids),
                caster_id=state.caster_id,
                target_id=state.target_id,
            )
            for state in actor.state_ledger.entries
        ],
    )


def retention_summary(retention):
    rows = []
    for entry in retention.view().entries:
        record = {
            key: getattr(entry, key, None)
            for key in ("uid", "generic_effect", "manager_id", "effect_class")
        }
        runner = retention.fight.native_owned_group_effects.get(entry.uid)
        record["native_runner_present"] = runner is not None
        if runner is not None:
            record.update(
                {
                    key: runner.get(key)
                    for key in (
                        "invocation",
                        "native_subscription_masks",
                        "native_effect_flags",
                    )
                }
            )
            reference = runner["invocation"]["reference"]
        else:
            reference = entry.generic_effect
        definition = retention.metadata["effects"].get(str(reference), {})
        record["definition"] = {
            key: definition.get(key)
            for key in (
                "subscription",
                "event_global_subscription",
                "event_reverse_subscription",
                "effect_class",
            )
        }
        rows.append(record)
    return rows


@contextmanager
def native_event_trace(events, activations):
    """Observe actual replay sources and clone calls without changing authority."""
    from wakfu_server.combat_event_replay import NativeEventReplay
    from wakfu_server.combat_effect_dispatch import EffectDispatcher

    replay = NativeEventReplay.__call__
    activation = EffectDispatcher.execute_activation

    def observed_replay(self, source, *, authority):
        event = {
            key: getattr(source, key, None)
            for key in (
                "uid",
                "generic_effect",
                "caster_id",
                "target_id",
                "event_ids",
                "channel",
                "manager_actor_id",
                "value",
            )
        }
        event["retained_population"] = retention_summary(self.retention)
        events.append(event)
        result = replay(self, source, authority=authority)
        event["outcome"] = repr(result)
        return result

    def observed_activation(self, invocation, **kwargs):
        entry = dict(
            reference=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            base_uid=invocation.base_uid,
            executable=kwargs.get("executable"),
        )
        activations.append(entry)
        result = activation(self, invocation, **kwargs)
        entry["outcome"] = repr(result)
        return result

    NativeEventReplay.__call__ = observed_replay
    EffectDispatcher.execute_activation = observed_activation
    try:
        yield
    finally:
        NativeEventReplay.__call__ = replay
        EffectDispatcher.execute_activation = activation


def run(args):
    hashes = audit.init.source_hashes()
    with open(args.graph, "rt") as stream:
        graph = json.load(stream)
    components_path = (
        ROOT
        / "docs/reports/combat-inventory/class-native-mechanic-components-20261007.json"
    )
    with open(components_path, "rt") as stream:
        components = json.load(stream)
    ownership = {}
    for component in components["classes"]:
        for reference in component["class_spell_ids"] + component["class_extra_ids"]:
            ownership.setdefault(reference, []).append(component["breed"])
    descriptors = json.loads(args.native.read_text())
    initial = json.loads(
        (ROOT / "server/protocol/native-class-summon-initial-states.json").read_text()
    )["profiles"]
    rows = []
    selected = set(
        args.profiles
        or [
            int(key) for key, value in initial.items() if value["initial_state_triples"]
        ]
    )
    candidates = {}
    for reference, effect in descriptors["effects"].items():
        parents = ancestors(graph, "effect:" + reference, ownership)
        for sample in effect["evaluations"]:
            if not sample["descriptor_created"] or not parents:
                continue
            profile = sample["descriptor"]["reference"]
            if profile not in selected:
                continue
            level = sample["context"]["caster_level"]
            if not 1 <= level <= 200:
                continue
            rank = (
                level != 200,
                bool(sample["native_property_counters"].get("101")),
                int(reference),
            )
            if profile not in candidates or rank < candidates[profile][0]:
                candidates[profile] = rank, int(reference), sample, parents[0]
    origin, enemy = (-8, -7, -1), (-7, -7, -1)
    terrain = audit.bounded_arena(audit.map_geometry(1134), origin, [enemy], radius=12)
    cell = min(
        (c for c in terrain["cells"] if c not in (origin, enemy)),
        key=lambda c: (abs(c[0] - origin[0]) + abs(c[1] - origin[1]), c),
    )
    for profile in sorted(selected):
        row = dict(
            profile=profile,
            initial_state_triples=initial[str(profile)]["initial_state_triples"],
            scope="creation mechanic dispatch; reaction stimuli use actual owned cast transactions",
            reactions=[],
        )
        rows.append(row)
        if profile not in candidates:
            row.update(
                status="unknown_class_source",
                reason="No actual class spell ancestor of sampled creator",
            )
            continue
        _, reference, sample, parent = candidates[profile]
        breed = ownership[parent][0]
        level = sample["context"]["caster_level"]
        row.update(
            breed=breed,
            source_spell=parent,
            source_effect=reference,
            level=level,
            descriptor_level=sample["descriptor"]["level"],
        )
        probes = {}
        for key, effect in graph["nodes"].items():
            family = effect.get("family")
            if not key.startswith("effect:") or family not in (1, 2, 3, 4, 5):
                continue
            parents = ancestors(graph, key, ownership)
            owned = [ref for ref in parents if breed in ownership[ref]]
            if not owned:
                continue
            shape = effect.get("native_metadata", {}).get("area_native")
            probe_key = family, shape
            if probe_key not in probes:
                probes[probe_key] = int(key.split(":")[1]), owned[0]
        records, creation_events, creation_activations = [], [], []
        try:
            character, creature, fight = audit.fixture(
                breed, level, enemy, terrain, origin, ready=False
            )
            fight.actors[7].direction = sample["context"]["caster_direction"]
            deck_references = list(
                dict.fromkeys(
                    reference
                    for _, reference in probes.values()
                    if reference in SPELLS
                    and SPELLS[reference]["kind"] == "active"
                    and SPELLS[reference]["breed"] == breed
                    and SPELLS[reference]["unlock_level"] <= level
                )
            )[:12]
            deck = encode_deck(deck_references)
            row["actual_deck"] = deck_references

            def initialize(preview, action_id):
                return prepare_server_initialization(
                    character,
                    {-7: creature},
                    preview,
                    3,
                    deck,
                    action_id=action_id,
                    rng=random.Random(0),
                    fight_start=True,
                )

            def stats(actor):
                if actor.controlled:
                    return actual_actor_stats(
                        character,
                        actor,
                        fight.id,
                        wp_current=actor.effect_stats[4],
                        wp_maximum=audit.BREEDS[breed]["resources"]["WP"],
                    )
                return actual_monster_actor_stats(
                    creature,
                    actor,
                    fight.id,
                    wp_current=creature["wp"],
                    wp_maximum=creature["wp"],
                )

            fight, ready_runtime, ready_packets = prepare_ready(
                fight,
                3,
                True,
                initialize=initialize,
                stats_serializer=stats,
                effects_serializer=actor_effects,
                turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                    character,
                    {-7: creature},
                    preview,
                    deck,
                    rng=random.Random(0),
                    **boundary
                ),
                turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                    character,
                    {-7: creature},
                    preview,
                    deck,
                    rng=random.Random(0),
                    native_events=True,
                    area_callbacks=True,
                    **boundary
                ),
            )
            row["first_turn_stages"] = []
            # Ready initialization already delivers the opening event. Advance
            # only when the actual owner is not current; never replay opening.
            for _ in range(len(fight.order) + 1):
                current = ready_runtime.fight.current
                if current.id == character["id"]:
                    break
                extra = (
                    ready_runtime.end_turn(
                        current.owner_id, current.id, current.turn_count
                    )
                    if current.controlled
                    else ready_runtime.end_server_turn(
                        current.id, ready_runtime.fight.turn_id
                    )
                )
                pending = ready_runtime.awaiting_ack
                if pending is not None:
                    extra += ready_runtime.acknowledge_turn(struct.pack(">i", pending))
                row["first_turn_stages"].append(
                    dict(
                        actor_id=current.id,
                        acknowledgement=pending,
                        packet_count=len(extra),
                    )
                )
                fight = ready_runtime.fight
                if fight.current.id == character["id"]:
                    break
            if fight.current.id != character["id"]:
                raise ValueError(
                    "Actual owner turn was not reached through production lifecycle"
                )
            marker = getattr(fight, "native_class_initializations", None)
            if marker is None or character["id"] not in marker:
                raise ValueError(
                    "Production Ready did not attest actual owner initialization"
                )
            row.update(
                production_ready_packet_count=len(ready_packets),
                native_class_initializations=repr(marker),
                owner_before_creation=actor_summary(fight.actors[character["id"]]),
            )
            factory, adapter = server_runtime(
                character,
                {-7: creature},
                deck,
                action_id=1,
                critical=False,
                rng=random.Random(0),
            )
            records = []
            dispatcher, packets = audit.observed(factory, records)(
                fight, dict(spell_id=parent, evaluation_level=level)
            )
            previous = set(fight.actors)
            with native_event_trace(
                creation_events, creation_activations
            ), fight.effect_resolution():
                outcome = dispatcher.execute(
                    EffectInvocation(reference, level, 7, None, cell)
                )
            created = set(fight.actors) - previous
            row.update(
                creation_trace=records,
                creation_packet_count=len(packets),
                outcome=repr(outcome),
                creation_events=creation_events,
                creation_activations=creation_activations,
            )
            if not created:
                row.update(
                    status="guarded_no_creation",
                    reason="Original runtime did not create an actor",
                )
                continue
            if len(created) != 1:
                raise ValueError(
                    "Native single descriptor created an unexpected actor count"
                )
            actor_id = next(iter(created))
            actor = fight.actors[actor_id]
            row.update(
                status="created",
                actor=actor_summary(actor),
                post_creation_retained_population=retention_summary(
                    dispatcher.native_retention
                ),
            )
            expected = initial[str(profile)]["initial_state_triples"][::3]
            actual = [state.reference for state in actor.state_ledger.entries]
            row["initial_states_present"] = all(state in actual for state in expected)
            for (family, shape), (damage_reference, damage_spell) in sorted(
                probes.items(), key=lambda p: repr(p[0])
            ):
                preview = copy.deepcopy(fight)
                trace, events, activations = [], [], []
                probe = dict(
                    family=family,
                    area_native=shape,
                    source_spell=damage_spell,
                    source_effect=damage_reference,
                    source_actor=7,
                    target_actor=actor_id,
                    before=actor_summary(preview.actors[actor_id]),
                )
                row["reactions"].append(probe)
                try:
                    grant = granted_spells(preview, character["id"]).get(damage_spell)
                    if damage_spell not in deck_references and grant is None:
                        raise ValueError(
                            "Actual owner has no deck or native grant for probe spell"
                        )
                    uid = (
                        grant["uid"]
                        if grant
                        else (character["id"] << 32) | damage_spell
                    )
                    target_cell = enemy if args.target_mode == "enemy" else cell

                    def los(source, target, context):
                        return authoritative_visible(
                            context.map_id,
                            source,
                            target,
                            context,
                            blocking_footprints={
                                value.id: {value.position[:2]}
                                for value in context.actors.values()
                                if value.hp > 0
                            },
                        )

                    with native_event_trace(events, activations):
                        transaction = prepare_spell_transaction(
                            struct.pack(">qqiih", character["id"], uid, *target_cell),
                            character,
                            preview,
                            3,
                            deck,
                            wp_current=preview.actors[character["id"]].effect_stats[4],
                            action_id=2,
                            line_of_sight=los,
                            runtime_factory=audit.observed(factory, trace),
                            conditional_context=lambda request, context: adapter.cast_condition(
                                context, request
                            ),
                            critical=False,
                        )
                    preview = transaction.fight
                    result = dict(
                        roots=transaction.plan["effect_ids"],
                        outcomes=transaction.outcomes,
                        packets=transaction.packets,
                        scope="actual_owned_cast_transaction",
                    )
                    primary_roots = set(result["roots"])
                    probe["target_cell"] = list(target_cell)
                    probe["owner_after"] = actor_summary(
                        preview.actors[character["id"]]
                    )
                    probe.update(
                        status="executed",
                        outcome=repr(result["outcomes"]),
                        native_roots=list(result["roots"]),
                        dispatch_scope=result["scope"],
                        packet_count=len(result["packets"]),
                        after=actor_summary(preview.actors[actor_id]),
                        trace=trace,
                        native_events=events,
                        retained_activations=activations,
                        executed_retained_activation_count=sum(
                            entry["executable"] is True for entry in activations
                        ),
                        non_root_effect_references=sorted(
                            {
                                entry[0]
                                for entry in trace
                                if entry[0] not in primary_roots
                            }
                        ),
                        no_retained_activations=not activations,
                    )
                except Exception as error:
                    probe.update(
                        status="blocked",
                        reason=str(error),
                        error_type=type(error).__name__,
                        trace=trace,
                        native_events=events,
                        retained_activations=activations,
                    )
        except Exception as error:
            row.update(
                status="blocked",
                reason=str(error),
                error_type=type(error).__name__,
                creation_trace=records,
                creation_events=creation_events,
                creation_activations=creation_activations,
                failing_reference=getattr(error, "audit_reference", None),
                failing_level=getattr(error, "audit_level", None),
            )
        print(
            json.dumps(
                dict(profile=profile, status=row["status"], reason=row.get("reason"))
            ),
            flush=True,
        )
    report = dict(
        scope="class-owned static summon mechanic fixtures",
        rows=rows,
        source_hashes=hashes,
        sources_stable=hashes == audit.init.source_hashes(),
        inputs={str(args.graph): sha(args.graph), str(args.native): sha(args.native)},
        limitations=[
            "Creation remains mechanic dispatch; alternate-controller negative control is pending.",
            "Damage effect selection does not assert that each original criterion is reachable.",
            "Dynamic captured and copied summon profiles are separate source-dependent mechanisms.",
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=repr) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native",
        type=Path,
        default=ROOT
        / ".runtime/combat-review-20261007/controlled-summon-proof/descriptors/native-descriptors.json",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=ROOT
        / "docs/reports/combat-inventory/class-native-mechanic-graph-20261007.json",
    )
    parser.add_argument("--profiles", type=int, nargs="*")
    parser.add_argument("--target-mode", choices=("enemy", "summon"), default="enemy")
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
